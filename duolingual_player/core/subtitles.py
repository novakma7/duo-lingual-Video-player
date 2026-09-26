from __future__ import annotations

import re
from pathlib import Path

from charset_normalizer import from_bytes

from .media import clean_subtitle_text
from .models import SubtitleCue


_TIMECODE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})"
)


def _seconds(value: str) -> float:
    match = _TIMECODE.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid subtitle timestamp: {value}")
    parts = {key: int(number) for key, number in match.groupdict().items()}
    return parts["h"] * 3600 + parts["m"] * 60 + parts["s"] + parts["ms"] / 1000


def load_srt(path: str | Path) -> list[SubtitleCue]:
    raw = Path(path).read_bytes()
    detected = from_bytes(raw).best()
    text = str(detected) if detected is not None else raw.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    cues: list[SubtitleCue] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [line.strip("\ufeff") for line in block.splitlines() if line.strip()]
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        start_text, end_text = [part.strip().split()[0] for part in lines[timing_index].split("-->", 1)]
        body = "\n".join(lines[timing_index + 1 :]).strip()
        if body:
            cues.append(SubtitleCue(_seconds(start_text), _seconds(end_text), body))
    return cues


def load_embedded(path: str | Path, stream_index: int) -> list[SubtitleCue]:
    import av

    cues: list[SubtitleCue] = []
    with av.open(str(path)) as container:
        stream = container.streams[stream_index]
        for packet in container.demux(stream):
            for subtitle in packet.decode():
                base_pts = float((subtitle.pts or packet.pts or 0) * stream.time_base)
                start = base_pts + float(getattr(subtitle, "start_display_time", 0)) / 1000
                end_ms = float(getattr(subtitle, "end_display_time", 0))
                end = base_pts + (end_ms / 1000 if end_ms > 0 else 4.0)
                texts: list[str] = []
                for rect in getattr(subtitle, "rects", []):
                    raw = getattr(rect, "ass", None) or getattr(rect, "text", None)
                    cleaned = clean_subtitle_text(raw)
                    if cleaned:
                        texts.append(cleaned)
                if texts:
                    cues.append(SubtitleCue(start, max(start + 0.1, end), "\n".join(texts)))
    return cues


def cue_at(cues: list[SubtitleCue], seconds: float) -> str:
    for cue in cues:
        if cue.start <= seconds <= cue.end:
            return cue.text
        if cue.start > seconds:
            break
    return ""
