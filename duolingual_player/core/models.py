from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    ERROR = "error"


@dataclass(frozen=True)
class TrackInfo:
    index: int
    kind: str
    codec: str
    language: str = "und"
    title: str = ""
    channels: Optional[int] = None
    sample_rate: Optional[int] = None

    @property
    def label(self) -> str:
        name = self.title.strip() or self.language.upper()
        details = [f"#{self.index}", name, self.codec]
        if self.channels:
            details.append(f"{self.channels} channels")
        return " · ".join(details)


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    host_api: str
    max_output_channels: int
    default_sample_rate: int

    @property
    def label(self) -> str:
        return f"{self.name} [{self.host_api}] · {self.default_sample_rate} Hz"


@dataclass
class MediaInfo:
    path: Path
    duration: float
    video_tracks: list[TrackInfo] = field(default_factory=list)
    audio_tracks: list[TrackInfo] = field(default_factory=list)
    subtitle_tracks: list[TrackInfo] = field(default_factory=list)


@dataclass(frozen=True)
class SubtitleCue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class AudioDiagnostics:
    pts: Optional[float]
    buffered_seconds: float
    device_name: str
    error: str = ""

