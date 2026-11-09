"""penmentor --daemon (Windows): the keys that start penmentor, which i3's bindsym gives you on Linux.

A small resident process with an icon in the tray. Each key runs `penmentor` (or `penmentor --ask MODE`) as its own
process, exactly like a window-manager binding would. The keys are in settings.json, "hotkeys":

  {"ctrl+alt+shift+a": [], "ctrl+alt+shift+m": ["--ask", "check"], "ctrl+alt+shift+s": ["--ask", "final"]}

Ctrl+Alt+Shift because xournal++'s plugin shortcut is Ctrl+Alt+Shift+F12: with those keys still held when penmentor
asks the plugin for the page, the shortcut reaches it all the same. Tablet pad buttons: map them to these keys in the
Wacom (or your tablet's) control panel.
"""
import ctypes
import os
import subprocess
import sys
import threading
from ctypes import wintypes
from pathlib import Path

from . import desktop_win as W
from .config import CACHE, CONF, SETTINGS

DEFAULT = {'ctrl+alt+shift+a': [], 'ctrl+alt+shift+m': ['--ask', 'check'], 'ctrl+alt+shift+s': ['--ask', 'final']}
MODS = {'alt': 0x1, 'ctrl': 0x2, 'control': 0x2, 'shift': 0x4, 'win': 0x8, 'super': 0x8}
NOREPEAT = 0x4000


def parse(combo):
    """'ctrl+alt+shift+a' -> (modifiers, virtual key)."""
    *mods, key = combo.lower().split('+')
    m = 0
    for k in mods:
        if k not in MODS:
            raise ValueError(f'unknown modifier in {combo!r}: {k}')
        m |= MODS[k]
    return m | NOREPEAT, W.vk(key)


def launch(args):
    """penmentor ARGS as its own process (from a checkout too), without a console window."""
    src = str(Path(__file__).resolve().parent.parent)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [src, os.environ.get('PYTHONPATH')])))
    pyw = Path(sys.executable).with_name('pythonw.exe')
    W.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: we just got the key, so we may pass the right to the focus on
    subprocess.Popen([str(pyw if pyw.exists() else sys.executable), '-m', 'penmentor', *args], env=env,
                     creationflags=W.NO_WINDOW, close_fds=True)


def listen(keys, failed):
    """RegisterHotKey belongs to the thread that calls it, so this thread registers the keys and waits for them."""
    table = {}
    for i, (combo, args) in enumerate(keys.items(), 1):
        try:
            mods, vk = parse(combo)
        except ValueError as ex:
            failed.append(str(ex))
            continue
        if W.user32.RegisterHotKey(None, i, mods, vk):
            table[i] = args
        else:
            failed.append(f'{combo} is taken by another program')
    msg = wintypes.MSG()
    while W.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312 and msg.wParam in table:  # WM_HOTKEY
            launch(table[msg.wParam])


def main():
    mutex = W.kernel32.CreateMutexW(None, False, 'penmentor-hotkeys')
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS: one daemon is enough
        W.notify('The penmentor keys are already on.', ms=3000)
        return
    keys = CONF.get('hotkeys') or DEFAULT
    failed = []
    threading.Thread(target=listen, args=(keys, failed), daemon=True).start()

    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    pix = QPixmap(64, 64)
    pix.fill(QColor(0, 0, 0, 0))
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor('#16161a'))
    p.setPen(QColor('#00DCFF'))
    p.drawEllipse(4, 4, 56, 56)
    f = p.font()
    f.setPixelSize(34)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), 0x84, 'p')  # AlignCenter
    p.end()
    tray = QSystemTrayIcon(QIcon(pix))
    first = next(iter(keys), '')
    tray.setToolTip(f'penmentor: {first.title()} to ask')
    menu = QMenu()
    menu.addAction('Ask (menu)', lambda: launch([]))
    menu.addAction('Show the last answer', lambda: launch(['--last']))
    menu.addAction('Settings folder', lambda: (SETTINGS.parent.mkdir(parents=True, exist_ok=True), os.startfile(SETTINGS.parent)))
    menu.addSeparator()
    menu.addAction('Quit penmentor keys', app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: reason == QSystemTrayIcon.ActivationReason.Trigger and launch([]))
    tray.show()
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / 'hotkeys.pid').write_text(str(os.getpid()))

    def report():
        (CACHE / 'hotkeys.log').write_text('\n'.join(failed) or 'all keys registered: ' + ', '.join(keys))
        if failed:
            tray.showMessage('penmentor', 'Some keys could not be set:\n' + '\n'.join(failed), QSystemTrayIcon.MessageIcon.Warning)
        else:
            tray.showMessage('penmentor', ', '.join(k.title() for k in keys) + ' are ready.', QSystemTrayIcon.MessageIcon.Information, 3000)
    QTimer.singleShot(800, report)
    app.exec()
    W.kernel32.CloseHandle(mutex)

