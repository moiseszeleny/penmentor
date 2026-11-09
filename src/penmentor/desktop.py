"""The desktop penmentor draws on: screenshots, monitors, windows, menus, notifications, the pointer and Esc.

One interface, two backends: desktop_x11 (Linux, X11, best with i3) and desktop_win (Windows 10/11).
"""
import sys

if sys.platform == 'win32':
    from .desktop_win import *  # noqa: F401,F403
    from .desktop_win import Oops  # noqa: F401  (explicit, for linters)
else:
    from .desktop_x11 import *  # noqa: F401,F403
    from .desktop_x11 import Oops  # noqa: F401
