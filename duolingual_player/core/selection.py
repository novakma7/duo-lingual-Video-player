from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from .models import DeviceInfo, TrackInfo


def choose_default_tracks(tracks: Sequence[TrackInfo]) -> tuple[Optional[int], Optional[int]]:
    """Vybere dvě různé stopy, pokud existují; jinak dostupnou stopu pouze pro A."""
    if not tracks:
        return None, None
    if len(tracks) == 1:
        return tracks[0].index, None
    return tracks[0].index, tracks[1].index


def choose_default_outputs(devices: Sequence[DeviceInfo]) -> tuple[Optional[int], Optional[int]]:
    """Preferuje dvě různá výstupní zařízení."""
    if not devices:
        return None, None
    first = devices[0].index
    second = next((device.index for device in devices if device.index != first), None)
    return first, second


def validate_routes(
    track_a: Optional[int],
    track_b: Optional[int],
    device_a: Optional[int],
    device_b: Optional[int],
) -> list[str]:
    errors: list[str] = []
    if track_a is None or track_b is None:
        errors.append("Vyberte zvukovou stopu pro výstup A i B.")
    elif track_a == track_b:
        errors.append("Pro dva jazyky zvolte dvě různé zvukové stopy.")
    if device_a is None or device_b is None:
        errors.append("Vyberte výstupní zařízení A i B.")
    elif device_a == device_b:
        errors.append("Pro oddělený poslech zvolte dvě různá výstupní zařízení.")
    return errors


def scheduled_audio_time(source_pts: float, offset_ms: int) -> float:
    """Čas na hlavních hodinách, kdy má zaznít vzorek se zadaným PTS."""
    return source_pts + offset_ms / 1000.0

