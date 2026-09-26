from __future__ import annotations

import threading
import time


class PlaybackClock:
    """Monotónní hlavní čas přehrávače, bezpečný mezi vlákny."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._position = 0.0
        self._started_at = 0.0
        self._playing = False

    def current(self) -> float:
        with self._lock:
            if self._playing:
                return max(0.0, self._position + time.monotonic() - self._started_at)
            return self._position

    def play(self) -> None:
        with self._lock:
            if not self._playing:
                self._started_at = time.monotonic()
                self._playing = True

    def pause(self) -> None:
        with self._lock:
            if self._playing:
                self._position += time.monotonic() - self._started_at
                self._playing = False

    def seek(self, seconds: float) -> None:
        with self._lock:
            self._position = max(0.0, float(seconds))
            if self._playing:
                self._started_at = time.monotonic()

    def stop(self) -> None:
        with self._lock:
            self._position = 0.0
            self._playing = False

    @property
    def playing(self) -> bool:
        with self._lock:
            return self._playing

