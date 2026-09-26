from duolingual_player.core.models import DeviceInfo, TrackInfo
from duolingual_player.core.selection import (
    choose_default_outputs,
    choose_default_tracks,
    scheduled_audio_time,
    validate_routes,
)


def audio_track(index: int) -> TrackInfo:
    return TrackInfo(index=index, kind="audio", codec="aac", language="cs")


def device(index: int) -> DeviceInfo:
    return DeviceInfo(index, f"Zařízení {index}", "Windows WASAPI", 2, 48_000)


def test_default_tracks_are_distinct() -> None:
    assert choose_default_tracks([audio_track(2), audio_track(5)]) == (2, 5)
    assert choose_default_tracks([audio_track(2)]) == (2, None)
    assert choose_default_tracks([]) == (None, None)


def test_default_outputs_are_distinct() -> None:
    assert choose_default_outputs([device(4), device(9)]) == (4, 9)
    assert choose_default_outputs([device(4)]) == (4, None)


def test_route_validation_reports_same_track_and_device() -> None:
    errors = validate_routes(1, 1, 7, 7)
    assert len(errors) == 2
    assert "stopy" in errors[0]
    assert "zařízení" in errors[1]


def test_sync_offset_is_converted_from_milliseconds() -> None:
    assert scheduled_audio_time(10.0, 250) == 10.25
    assert scheduled_audio_time(10.0, -125) == 9.875
