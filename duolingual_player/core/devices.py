from __future__ import annotations

from .models import DeviceInfo


class AudioDeviceError(RuntimeError):
    pass


def list_output_devices() -> list[DeviceInfo]:
    """Vrátí aktivní výstupy; WASAPI řadí na Windows před ostatní host API."""
    try:
        import sounddevice as sd

        host_apis = sd.query_hostapis()
        devices: list[DeviceInfo] = []
        for index, raw in enumerate(sd.query_devices()):
            channels = int(raw.get("max_output_channels", 0))
            if channels < 1:
                continue
            host_index = int(raw.get("hostapi", -1))
            host_name = (
                str(host_apis[host_index].get("name", "Neznámé API"))
                if 0 <= host_index < len(host_apis)
                else "Neznámé API"
            )
            devices.append(
                DeviceInfo(
                    index=index,
                    name=str(raw.get("name", f"Zařízení {index}")),
                    host_api=host_name,
                    max_output_channels=channels,
                    default_sample_rate=max(8_000, int(raw.get("default_samplerate", 48_000))),
                )
            )
        return sorted(
            devices,
            key=lambda item: ("wasapi" not in item.host_api.lower(), item.name.casefold(), item.index),
        )
    except Exception as exc:  # PortAudio může selhat už při výčtu zařízení.
        raise AudioDeviceError(f"Zvuková zařízení nelze načíst: {exc}") from exc


def find_device(devices: list[DeviceInfo], index: int | None) -> DeviceInfo | None:
    return next((device for device in devices if device.index == index), None)

