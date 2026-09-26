from __future__ import annotations

import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from .audio import AudioPipeline
from .clock import PlaybackClock
from .models import MediaInfo, TrackInfo


def _metadata_text(metadata, key: str, fallback: str = "") -> str:
    value = metadata.get(key, fallback) if metadata else fallback
    return str(value or fallback)


def probe_media(path: str | Path) -> MediaInfo:
    import av

    source = Path(path)
    with av.open(str(source)) as container:
        duration = float(container.duration or 0) / float(av.time_base)
        info = MediaInfo(path=source, duration=max(0.0, duration))
        for stream in container.streams:
            codec = stream.codec_context.name or "unknown"
            language = _metadata_text(stream.metadata, "language", "und")
            title = _metadata_text(stream.metadata, "title")
            if stream.type == "video":
                info.video_tracks.append(
                    TrackInfo(stream.index, "video", codec, language, title)
                )
            elif stream.type == "audio":
                layout = getattr(stream.codec_context, "layout", None)
                channels = getattr(layout, "nb_channels", None)
                info.audio_tracks.append(
                    TrackInfo(
                        stream.index,
                        "audio",
                        codec,
                        language,
                        title,
                        channels=channels,
                        sample_rate=getattr(stream.codec_context, "sample_rate", None),
                    )
                )
            elif stream.type == "subtitle":
                info.subtitle_tracks.append(
                    TrackInfo(stream.index, "subtitle", codec, language, title)
                )
        if duration <= 0 and info.video_tracks:
            stream = container.streams[info.video_tracks[0].index]
            if stream.duration is not None and stream.time_base is not None:
                info.duration = float(stream.duration * stream.time_base)
        return info


class DecodeWorker:
    """Single demux thread routing each selected audio track to its own pipeline."""

    def __init__(
        self,
        path: Path,
        video_index: int,
        audio_a_index: Optional[int],
        audio_b_index: Optional[int],
        pipeline_a: AudioPipeline,
        pipeline_b: AudioPipeline,
        clock: PlaybackClock,
        start_at: float,
        on_error: Callable[[str], None],
        on_eof: Callable[[], None],
    ) -> None:
        self.path = path
        self.video_index = video_index
        self.audio_a_index = audio_a_index
        self.audio_b_index = audio_b_index
        self.pipeline_a = pipeline_a
        self.pipeline_b = pipeline_b
        self.clock = clock
        self.start_at = max(0.0, start_at)
        self.on_error = on_error
        self.on_eof = on_eof
        self.video_frames: deque[tuple[float, np.ndarray]] = deque()
        self._video_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.video_pts: Optional[float] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="mkv-decode", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.5)
        self._thread = None
        with self._video_lock:
            self.video_frames.clear()

    def pop_due_video(self, media_time: float) -> tuple[float, np.ndarray] | None:
        latest = None
        with self._video_lock:
            while self.video_frames and self.video_frames[0][0] <= media_time + 0.025:
                latest = self.video_frames.popleft()
        if latest is not None:
            self.video_pts = latest[0]
        return latest

    @property
    def video_buffered(self) -> int:
        with self._video_lock:
            return len(self.video_frames)

    def _run(self) -> None:
        try:
            import av

            with av.open(str(self.path)) as container:
                if self.start_at > 0:
                    container.seek(
                        int(self.start_at * av.time_base), any_frame=False, backward=True
                    )
                selected_indices = {
                    index
                    for index in (self.video_index, self.audio_a_index, self.audio_b_index)
                    if index is not None
                }
                streams = [stream for stream in container.streams if stream.index in selected_indices]
                for packet in container.demux(streams):
                    if self._stop.is_set():
                        return
                    for frame in packet.decode():
                        if self._stop.is_set():
                            return
                        if frame.pts is None:
                            continue
                        pts = float(frame.pts * frame.time_base)
                        if pts + 0.2 < self.start_at:
                            continue
                        if packet.stream.type == "video":
                            image = frame.to_ndarray(format="rgb24")
                            while not self._stop.is_set():
                                with self._video_lock:
                                    if len(self.video_frames) < 90:
                                        self.video_frames.append((pts, image))
                                        break
                                time.sleep(0.01)
                        elif packet.stream.type == "audio":
                            if packet.stream.index == self.audio_a_index:
                                self.pipeline_a.enqueue_frame(frame, pts)
                            if packet.stream.index == self.audio_b_index:
                                self.pipeline_b.enqueue_frame(frame, pts)
                        while pts - self.clock.current() > 4.0 and not self._stop.wait(0.02):
                            pass
                if not self._stop.is_set():
                    self.on_eof()
        except Exception as exc:
            if not self._stop.is_set():
                self.on_error(f"Media decoding error: {exc}")


_ASS_OVERRIDE = re.compile(r"\{[^}]*\}")


def clean_subtitle_text(value: object) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value or "")
    if text.startswith("Dialogue:"):
        fields = text.split(",", 9)
        text = fields[-1] if fields else text
    text = _ASS_OVERRIDE.sub("", text)
    return text.replace(r"\N", "\n").replace(r"\n", "\n").strip()

