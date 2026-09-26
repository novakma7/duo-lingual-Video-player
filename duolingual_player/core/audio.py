from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np

from .clock import PlaybackClock
from .models import AudioDiagnostics, DeviceInfo
from .selection import scheduled_audio_time

if TYPE_CHECKING:
    import av


@dataclass
class AudioChunk:
    pts: float
    samples: np.ndarray
    cursor: int = 0


class AudioPipeline:
    """Nezávislá fronta, převzorkovač a PortAudio/WASAPI výstup."""

    MAX_BUFFER_SECONDS = 4.0

    def __init__(self, name: str, clock: PlaybackClock) -> None:
        self.name = name
        self.clock = clock
        self.device: DeviceInfo | None = None
        self.volume = 1.0
        self.offset_ms = 0
        self.muted = False
        self.paused = True
        self._sample_rate = 48_000
        self._chunks: deque[AudioChunk] = deque()
        self._queued_frames = 0
        self._lock = threading.RLock()
        self._stream = None
        self._resampler = None
        self._last_pts: Optional[float] = None
        self._error = ""
        self._error_callback: Optional[Callable[[str, str], None]] = None
        self._error_reported = False

    def set_error_callback(self, callback: Callable[[str, str], None]) -> None:
        self._error_callback = callback

    def configure(self, device: DeviceInfo) -> None:
        self.close()
        self.device = device
        self._sample_rate = device.default_sample_rate
        try:
            import av

            self._resampler = av.AudioResampler(
                format="fltp", layout="stereo", rate=self._sample_rate
            )
        except Exception as exc:
            self._set_error(f"Nelze připravit převzorkování: {exc}")
            raise

    def start(self) -> None:
        if self.device is None:
            raise RuntimeError(f"Pro výstup {self.name} není vybrané zařízení.")
        if self._stream is not None:
            return
        try:
            import sounddevice as sd

            self._stream = sd.OutputStream(
                device=self.device.index,
                samplerate=self._sample_rate,
                channels=2,
                dtype="float32",
                latency="high",
                callback=self._audio_callback,
                finished_callback=self._stream_finished,
            )
            self._stream.start()
            self._error = ""
            self._error_reported = False
        except Exception as exc:
            self._stream = None
            message = (
                f"Výstup {self.name} nelze otevřít na zařízení „{self.device.name}“: {exc}. "
                "Zařízení mohlo být odpojeno; vyberte je znovu nebo zvolte jiné."
            )
            self._set_error(message)
            raise RuntimeError(message) from exc

    def close(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.abort()
                stream.close()
            except Exception:
                pass
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._queued_frames = 0
            self._last_pts = None

    def enqueue_frame(self, frame: "av.AudioFrame", pts: float) -> None:
        if self._resampler is None:
            return
        try:
            converted = self._resampler.resample(frame)
            frames = converted if isinstance(converted, list) else [converted]
            running_pts = pts
            for result in frames:
                if result is None or result.samples <= 0:
                    continue
                planar = result.to_ndarray().astype(np.float32, copy=False)
                samples = np.ascontiguousarray(planar.T)
                if samples.ndim != 2:
                    samples = samples.reshape(-1, 2)
                with self._lock:
                    if self._queued_frames / self._sample_rate >= self.MAX_BUFFER_SECONDS:
                        return
                    self._chunks.append(AudioChunk(running_pts, samples))
                    self._queued_frames += len(samples)
                running_pts += len(samples) / self._sample_rate
        except Exception as exc:
            self._set_error(f"Chyba dekódování zvuku {self.name}: {exc}")

    def _audio_callback(self, outdata, frames: int, _time_info, status) -> None:
        outdata.fill(0)
        if status:
            self._set_error(f"Zvukový výstup {self.name} hlásí: {status}")
        if self.paused or not self.clock.playing:
            return
        write_at = 0
        now = self.clock.current()
        with self._lock:
            while write_at < frames and self._chunks:
                chunk = self._chunks[0]
                chunk_time = scheduled_audio_time(
                    chunk.pts + chunk.cursor / self._sample_rate, self.offset_ms
                )
                delta = chunk_time - now - write_at / self._sample_rate
                if delta > 0:
                    silence = min(frames - write_at, max(1, int(delta * self._sample_rate)))
                    write_at += silence
                    continue
                if delta < -0.025:
                    skip = min(len(chunk.samples) - chunk.cursor, int(-delta * self._sample_rate))
                    chunk.cursor += skip
                    self._queued_frames -= skip
                    if chunk.cursor >= len(chunk.samples):
                        self._chunks.popleft()
                    continue
                available = len(chunk.samples) - chunk.cursor
                count = min(frames - write_at, available)
                gain = 0.0 if self.muted else self.volume
                outdata[write_at : write_at + count] = (
                    chunk.samples[chunk.cursor : chunk.cursor + count] * gain
                )
                chunk.cursor += count
                self._queued_frames -= count
                self._last_pts = chunk.pts + chunk.cursor / self._sample_rate
                write_at += count
                if chunk.cursor >= len(chunk.samples):
                    self._chunks.popleft()

    def _stream_finished(self) -> None:
        if self._stream is not None:
            self._set_error(
                f"Zvukový výstup {self.name} se neočekávaně ukončil. "
                "Zkontrolujte Bluetooth/WASAPI zařízení a vyberte výstup znovu."
            )

    def _set_error(self, message: str) -> None:
        self._error = message
        if self._error_callback is not None and not self._error_reported:
            self._error_reported = True
            self._error_callback(self.name, message)

    @property
    def buffered_seconds(self) -> float:
        with self._lock:
            return self._queued_frames / self._sample_rate

    def diagnostics(self) -> AudioDiagnostics:
        return AudioDiagnostics(
            pts=self._last_pts,
            buffered_seconds=self.buffered_seconds,
            device_name=self.device.name if self.device else "nevybráno",
            error=self._error,
        )
