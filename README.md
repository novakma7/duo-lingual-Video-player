# DuoLingual Player

DuoLingual Player is a Windows desktop media player designed to play two language tracks from a single MKV file at the same time. Video is shown in one window, while output A and output B each have their own decoding, resampling, buffer, volume, sync offset, and physical or virtual audio device.

The backend does not use VLC. PyAV/FFmpeg handles the container and codecs, PySide6 renders the interface and video, and PortAudio (`sounddevice`) sends audio to Windows devices, including WASAPI and virtual VoiceMeeter inputs.

## Requirements

- Windows 10 or Windows 11;
- Python 3.10–3.13 (64-bit Python 3.12 recommended);
- two audio output devices;
- an MKV file with two audio tracks for full dual-language playback.

PyAV wheels from PyPI normally include the required FFmpeg libraries. VLC does not need to be installed.

## Installation and startup

Open PowerShell in the project directory. Use a short path outside Google Drive for the virtual environment. PySide6 contains a deeply nested directory structure, and placing `.venv` inside this project may exceed the Windows path-length limit.

```powershell
$venv = "$env:LOCALAPPDATA\DuoLingualPlayer\venv"
py -3.12 -m venv $venv
& "$venv\Scripts\python.exe" -m pip install --upgrade pip
& "$venv\Scripts\python.exe" -m pip install -r requirements.txt
& "$venv\Scripts\python.exe" -m duolingual_player
```

Activating the environment is not required. For subsequent launches, run only the final command from the project directory. Alternatively:

```powershell
& "$env:LOCALAPPDATA\DuoLingualPlayer\venv\Scripts\python.exe" run_player.py
```

After installation, you can also start the application by double-clicking `start_player.bat`. Its console window closes automatically after the GUI starts.

If an incomplete `.venv` was already created inside the project, it is not used and can be removed after all terminals have been closed. Enabling Windows long-path support system-wide is another option, but it is not required for this project.

## Usage

1. Click **Open MKV** and select a video.
2. Select a different **Audio track** for output A and output B in the right-hand panel.
3. Select two different output devices. WASAPI devices are listed first.
4. Start playback with Space or the Play button.
5. Correct any Bluetooth latency difference independently for A and B. A positive offset delays the audio; a negative offset advances it.

If a Bluetooth device disconnects, the player displays an error. Reconnect the device, click **Refresh audio devices**, select the output again, and continue. Changing a track or device during playback rebuilds both audio pipelines from the current position.

### Keyboard and mouse controls

| Input | Action |
|---|---|
| Space | Play / pause |
| Left/right arrow | Jump 5 seconds |
| Shift + left/right arrow | Jump 30 seconds |
| F | Toggle fullscreen |
| Double-click video | Toggle fullscreen |
| Esc | Leave fullscreen |
| M | Mute / restore both outputs |
| Ctrl+O | Open a file |

Use **View → Video smoothing** to enable or disable smoother interpolation when the video is enlarged. It is enabled by default. It reduces hard pixel edges caused by scaling, but it cannot remove compression blocks already present in a heavily compressed source.

## Subtitles

The **Subtitles** panel supports compatible embedded text subtitle tracks and external SRT files. Bitmap subtitles such as PGS are not currently rendered. Loading a very large embedded subtitle track may take a moment.

## VoiceMeeter Banana

1. Install VoiceMeeter Banana and restart Windows.
2. In the top-right corner of VoiceMeeter, set **A1** and **A2** to the two physical headphones. The `WDM` driver is usually the most stable choice for Bluetooth; try `MME` if WDM causes problems.
3. In DuoLingual Player, select for example:
   - output A: **Voicemeeter Input (VB-Audio Voicemeeter VAIO)**;
   - output B: **Voicemeeter AUX Input (VB-Audio Voicemeeter AUX VAIO)**.
4. On the VAIO strip, enable only bus A1. On the AUX strip, enable only A2. This keeps the languages physically separate.
5. If a device is missing, make sure it is enabled in Windows sound settings, then refresh the device list in the player.

VoiceMeeter may introduce different latency than a direct Bluetooth output. Use the A/B millisecond offsets to compensate; adjustments of 10–20 ms are a useful starting point.

## Diagnostics

The Diagnostics panel displays the master clock, last rendered video PTS, both audio PTS values, queue sizes, selected devices, and device errors. When troubleshooting, check whether an audio buffer continuously drops to zero or a selected device disappears after being disconnected.

## Tests

```powershell
& "$env:LOCALAPPDATA\DuoLingualPlayer\venv\Scripts\python.exe" -m pytest -q
```

The tests cover default selection of distinct tracks and devices, route validation, and conversion of the sync offset from milliseconds.

## Architecture

- `core/clock.py` — shared monotonic playback clock;
- `core/media.py` — PyAV probing, demuxing, and decoding thread;
- `core/audio.py` — two independent audio pipeline instances and output callbacks;
- `core/devices.py` — output-device and host-API enumeration;
- `core/controller.py` — lifecycle, seeking, synchronization, and diagnostics;
- `core/subtitles.py` — SRT and embedded text subtitles;
- `ui/` — main window and video/subtitle rendering.

## Known limitations

- Final latency depends on the Bluetooth codec, driver, and hardware buffer size. The independent A/B offsets are intended for manual correction.
- Windows may expose one physical device through multiple host APIs. Prefer an entry marked `Windows WASAPI` for lower and more predictable latency.
- Some Bluetooth headphones switch to a narrow-band hands-free profile when their microphone is used at the same time. Disable or avoid the headset microphone for high-quality stereo playback.
- Text subtitles are supported; PGS/VobSub bitmap tracks are not.
- DRM-protected media and damaged containers are not supported.
- The application selects the first video track. Switching between multiple video tracks is not currently exposed in the interface.

## Safe shutdown

Closing the window stops the UI timer, decoding thread, and both audio streams in that order. Audio callbacks use locked queues and never perform GUI operations.
