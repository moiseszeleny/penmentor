"""The whole current xournal++ page, not just the part on screen (the problem statement is often scrolled away).

penmentor's xournal++ plugin (xournalpp-plugin/penmentor) exports the current page from memory, so unsaved strokes count,
when it gets its shortcut; penmentor sends that shortcut and waits for page.png in its cache
(~/.cache/penmentor on Linux, %LOCALAPPDATA%/penmentor/cache on Windows).
"""
import os
import sys
import time
from pathlib import Path

from . import desktop
from .config import CACHE

if sys.platform == 'win32':  # xournal++ keeps its config, plugins included, in %LOCALAPPDATA%\xournalpp
    PLUGIN = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'xournalpp' / 'plugins' / 'penmentor'
else:
    PLUGIN = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'xournalpp' / 'plugins' / 'penmentor'
PAGE, INFO = CACHE / 'page.png', CACHE / 'page.txt'
MISS = CACHE / 'page.miss'  # pid of a xournal++ that didn't answer (started before the plugin was installed): don't wait on it again
KEY = 'ctrl+alt+shift+F12'  # the plugin's accelerator (main.lua)


def focused():
    """xournal++'s pid if it is the active window (only then does the shortcut reach it), else None."""
    cls, pid = desktop.focused_app()  # X11: the window class; Windows: the executable (xournalpp.exe)
    return (pid or '?') if cls and 'xournal' in cls.lower() else None


class PageRequest:
    """Ask the plugin for the page now (before rofi takes the keyboard); result() waits for it."""

    def __init__(self):
        self.pid = PLUGIN.is_dir() and focused()
        self.on = bool(self.pid) and not (MISS.exists() and MISS.read_text() == self.pid)
        if self.on:
            CACHE.mkdir(parents=True, exist_ok=True)
            PAGE.unlink(missing_ok=True)
            self.poke()

    @staticmethod
    def poke():
        desktop.press(KEY)

    def result(self, wait=1.5):
        """(PNG bytes, 'page 3 of 5'), or None without the plugin. Safe to call twice."""
        if not self.on:
            return None
        if not hasattr(self, '_page'):
            self._page = None
            for attempt, limit in enumerate((.5, wait)):
                end = time.monotonic() + limit
                while time.monotonic() < end and not PAGE.exists():
                    time.sleep(.05)
                if PAGE.exists():
                    try:
                        n, total = INFO.read_text().split()
                        label = f'page {n} of {total}'
                    except (OSError, ValueError):
                        label = 'current page'
                    self._page = PAGE.read_bytes(), label
                    MISS.unlink(missing_ok=True)
                    break
                if attempt == 0 and focused():  # the first key is lost while i3 still holds the hotkey; rofi has closed by now
                    self.poke()
            else:
                MISS.write_text(self.pid)
        return self._page
