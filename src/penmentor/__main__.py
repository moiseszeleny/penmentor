import sys

if sys.platform == 'win32' and len(sys.argv) == 1:  # the menu key: start the menu's process first, so it loads
    from .desktop_win import prewarm  # while the rest of penmentor imports and takes the screenshot
    prewarm('ask')

from .cli import run  # noqa: E402

run()
