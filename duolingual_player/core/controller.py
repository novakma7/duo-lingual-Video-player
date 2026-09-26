from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal

from .audio import AudioPipeline
from .clock import PlaybackClock
from .devices import find_device, list_output_devices
from .media import DecodeWorker, probe_media
from .models import DeviceInfo, MediaInfo, PlaybackState, SubtitleCue
from .selection import choose_default_outputs, choose_default_tracks, validate_routes
from .subtitles import cue_at, load_embedded, load_srt


class PlaybackController(QObject):
    media_loaded = Signal(object)
    devices_changed = Signal(object)
    frame_ready = Signal(object, float)
    subtitle_changed = Signal(str)
    position_changed = Signal(float, float)
    state_changed = Signal(object)
    diagnostics_changed = Signal(str)
    error_occurred = Signal(str)
    routes_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.clock = PlaybackClock()
        self.pipeline_a = AudioPipeline("A", self.clock)
        self.pipeline_b = AudioPipeline("B", self.clock)
        self.pipeline_a.set_error_callback(self._audio_error)
        self.pipeline_b.set_error_callback(self._audio_error)
        self.info: MediaInfo | None = None
        self.devices: list[DeviceInfo] = []
        self.track_a: Optional[int] = None
        self.track_b: Optional[int] = None
        self.device_a: Optional[int] = None
        self.device_b: Optional[int] = None
        self.subtitle_cues: list[SubtitleCue] = []
        self.subtitle_source = "off"
        self.worker: DecodeWorker | None = None
        self.state = PlaybackState.STOPPED
        self._eof = False
        self._last_subtitle = ""
        self._last_diagnostics_at = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(15)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.refresh_devices()

    def refresh_devices(self) -> None:
        try:
            previous_a, previous_b = self.device_a, self.device_b
            self.devices = list_output_devices()
            available = {device.index for device in self.devices}
            defaults = choose_default_outputs(self.devices)
            self.device_a = previous_a if previous_a in available else defaults[0]
            self.device_b = previous_b if previous_b in available else defaults[1]
            self.devices_changed.emit(self.devices)
            self._emit_routes()
        except Exception as exc:
            self.devices = []
            self.device_a = self.device_b = None
            self.devices_changed.emit([])
            self.error_occurred.emit(str(exc))

    def open_media(self, path: str) -> None:
        self.stop()
        try:
            self.info = probe_media(path)
            if not self.info.video_tracks:
                raise ValueError("The file does not contain a video track.")
            self.track_a, self.track_b = choose_default_tracks(self.info.audio_tracks)
            self.subtitle_cues = []
            self.subtitle_source = "off"
            self.media_loaded.emit(self.info)
            self._emit_routes()
            self.position_changed.emit(0.0, self.info.duration)
        except Exception as exc:
            self.info = None
            self.error_occurred.emit(f"The file could not be opened: {exc}")

    def set_tracks(self, track_a: Optional[int], track_b: Optional[int]) -> None:
        changed = (track_a, track_b) != (self.track_a, self.track_b)
        self.track_a, self.track_b = track_a, track_b
        self._emit_routes()
        if changed and self.worker is not None:
            self._restart_at(self.clock.current(), self.state == PlaybackState.PLAYING)

    def set_devices(self, device_a: Optional[int], device_b: Optional[int]) -> None:
        changed = (device_a, device_b) != (self.device_a, self.device_b)
        self.device_a, self.device_b = device_a, device_b
        self._emit_routes()
        if changed and self.worker is not None:
            self._restart_at(self.clock.current(), self.state == PlaybackState.PLAYING)

    def set_volume(self, channel: str, value: float) -> None:
        pipeline = self.pipeline_a if channel == "A" else self.pipeline_b
        pipeline.volume = max(0.0, min(1.5, float(value)))

    def set_offset(self, channel: str, milliseconds: int) -> None:
        pipeline = self.pipeline_a if channel == "A" else self.pipeline_b
        pipeline.offset_ms = int(milliseconds)

    def toggle_mute(self) -> bool:
        muted = not (self.pipeline_a.muted and self.pipeline_b.muted)
        self.pipeline_a.muted = muted
        self.pipeline_b.muted = muted
        return muted

    def play_pause(self) -> None:
        if self.state == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        if self.info is None:
            self.error_occurred.emit("Open an MKV file first.")
            return
        errors = validate_routes(self.track_a, self.track_b, self.device_a, self.device_b)
        if errors:
            self.error_occurred.emit("\n".join(errors))
            return
        if self.worker is None:
            if not self._start_outputs():
                return
            self._start_worker(self.clock.current())
        self.pipeline_a.paused = False
        self.pipeline_b.paused = False
        self.clock.play()
        self._set_state(PlaybackState.PLAYING)

    def pause(self) -> None:
        self.clock.pause()
        self.pipeline_a.paused = True
        self.pipeline_b.paused = True
        if self.info is not None:
            self._set_state(PlaybackState.PAUSED)

    def stop(self) -> None:
        self._stop_worker()
        self.pipeline_a.close()
        self.pipeline_b.close()
        self.clock.stop()
        self._eof = False
        self.subtitle_changed.emit("")
        self._set_state(PlaybackState.STOPPED)
        if self.info is not None:
            self.position_changed.emit(0.0, self.info.duration)

    def seek(self, seconds: float) -> None:
        if self.info is None:
            return
        target = max(0.0, min(float(seconds), self.info.duration))
        was_playing = self.state == PlaybackState.PLAYING
        self._restart_at(target, was_playing)

    def jump(self, delta_seconds: float) -> None:
        self.seek(self.clock.current() + delta_seconds)

    def set_subtitle_off(self) -> None:
        self.subtitle_cues = []
        self.subtitle_source = "off"
        self.subtitle_changed.emit("")

    def load_external_subtitle(self, path: str) -> None:
        try:
            self.subtitle_cues = load_srt(path)
            self.subtitle_source = Path(path).name
            self._last_subtitle = ""
        except Exception as exc:
            self.error_occurred.emit(f"External subtitles could not be loaded: {exc}")

    def load_embedded_subtitle(self, stream_index: int) -> None:
        if self.info is None:
            return
        try:
            self.subtitle_cues = load_embedded(self.info.path, stream_index)
            self.subtitle_source = f"track #{stream_index}"
            self._last_subtitle = ""
        except Exception as exc:
            self.error_occurred.emit(f"Embedded subtitles could not be loaded: {exc}")

    def shutdown(self) -> None:
        self._timer.stop()
        self.stop()

    def _start_outputs(self) -> bool:
        device_a = find_device(self.devices, self.device_a)
        device_b = find_device(self.devices, self.device_b)
        if device_a is None or device_b is None:
            self.error_occurred.emit(
                "The selected device is no longer available. Refresh the list and select the outputs again."
            )
            return False
        try:
            self.pipeline_a.configure(device_a)
            self.pipeline_b.configure(device_b)
            self.pipeline_a.start()
            self.pipeline_b.start()
            return True
        except Exception as exc:
            self.pipeline_a.close()
            self.pipeline_b.close()
            self.error_occurred.emit(str(exc))
            return False

    def _start_worker(self, position: float) -> None:
        assert self.info is not None and self.info.video_tracks
        self._eof = False
        self.worker = DecodeWorker(
            self.info.path,
            self.info.video_tracks[0].index,
            self.track_a,
            self.track_b,
            self.pipeline_a,
            self.pipeline_b,
            self.clock,
            position,
            self._decoder_error,
            self._decoder_eof,
        )
        self.worker.start()

    def _stop_worker(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.stop()

    def _restart_at(self, position: float, resume: bool) -> None:
        self.clock.pause()
        self._stop_worker()
        self.pipeline_a.close()
        self.pipeline_b.close()
        self.clock.seek(position)
        if self.info is None:
            return
        if not self._start_outputs():
            self._set_state(PlaybackState.ERROR)
            return
        self._start_worker(position)
        if resume:
            self.pipeline_a.paused = False
            self.pipeline_b.paused = False
            self.clock.play()
            self._set_state(PlaybackState.PLAYING)
        else:
            self.pipeline_a.paused = True
            self.pipeline_b.paused = True
            self._set_state(PlaybackState.PAUSED)

    def _tick(self) -> None:
        if self.info is None:
            return
        position = min(self.clock.current(), self.info.duration)
        if self.worker is not None:
            frame = self.worker.pop_due_video(position)
            if frame is not None:
                self.frame_ready.emit(frame[1], frame[0])
        subtitle = cue_at(self.subtitle_cues, position)
        if subtitle != self._last_subtitle:
            self._last_subtitle = subtitle
            self.subtitle_changed.emit(subtitle)
        self.position_changed.emit(position, self.info.duration)
        now = time.monotonic()
        if now - self._last_diagnostics_at >= 0.25:
            self._last_diagnostics_at = now
            self._emit_diagnostics(position)
        if self.state == PlaybackState.PLAYING and self.info.duration > 0 and position >= self.info.duration:
            self.stop()

    def _emit_diagnostics(self, position: float) -> None:
        audio_a = self.pipeline_a.diagnostics()
        audio_b = self.pipeline_b.diagnostics()
        video_pts = self.worker.video_pts if self.worker else None
        video_buffer = self.worker.video_buffered if self.worker else 0
        fmt = lambda value: "—" if value is None else f"{value:.3f} s"
        lines = [
            f"State: {self.state.value}",
            f"Master clock: {position:.3f} s",
            f"Video PTS: {fmt(video_pts)}  | queue: {video_buffer} frames",
            f"Audio A PTS: {fmt(audio_a.pts)}  | buffer: {audio_a.buffered_seconds:.2f} s",
            f"Device A: {audio_a.device_name}",
            f"Audio B PTS: {fmt(audio_b.pts)}  | buffer: {audio_b.buffered_seconds:.2f} s",
            f"Device B: {audio_b.device_name}",
            f"Error A: {audio_a.error or '—'}",
            f"Error B: {audio_b.error or '—'}",
        ]
        self.diagnostics_changed.emit("\n".join(lines))

    def _set_state(self, state: PlaybackState) -> None:
        self.state = state
        self.state_changed.emit(state)

    def _emit_routes(self) -> None:
        self.routes_changed.emit((self.track_a, self.track_b, self.device_a, self.device_b))

    def _audio_error(self, _channel: str, message: str) -> None:
        self.error_occurred.emit(message)

    def _decoder_error(self, message: str) -> None:
        self._set_state(PlaybackState.ERROR)
        self.error_occurred.emit(message)

    def _decoder_eof(self) -> None:
        self._eof = True

