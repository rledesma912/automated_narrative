"""Spinner ASCII para feedback visual durante llamadas LLM."""

import itertools
import sys
import threading
import time


class Spinner:
    """Spinner de terminal en hilo separado. Compatible con asyncio."""

    CHARS = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]
    INTERVAL = 0.12

    def __init__(self) -> None:
        self._message = ""
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, message: str) -> None:
        self._message = message
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self, final_line: str | None = None) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        sys.stdout.write("\r\033[K")
        if final_line:
            sys.stdout.write(final_line + "\n")
        sys.stdout.flush()

    def _spin(self) -> None:
        for char in itertools.cycle(self.CHARS):
            if self._stop_event.is_set():
                break
            sys.stdout.write(f"\r{char}  {self._message}")
            sys.stdout.flush()
            time.sleep(self.INTERVAL)
