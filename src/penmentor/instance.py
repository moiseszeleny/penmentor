"""One penmentor at a time, and the penmentor key pressed again reaching the one whose marks are up.

Linux: an flock on ~/.cache/penmentor/lock, SIGUSR1, /proc/<pid>/cmdline.
Windows: a byte-range lock on the same file, a named pipe (QLocalServer), psutil (or just "is that pid alive").
"""
import os
import signal
import sys
import time
from pathlib import Path

WIN = sys.platform == 'win32'
PIPE = f'penmentor-{os.environ.get("USERNAME") or os.environ.get("USER") or "me"}'  # QLocalServer's name (\\.\pipe\...)


def lock(path):
    """The open lock file if we are the only penmentor (keep it open while running), else None."""
    f = open(path, 'a+')
    try:
        if WIN:
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:  # BlockingIOError on Linux, PermissionError on Windows
        f.close()
        return None
    return f


def is_ours(pid, needle):
    """Is process pid still running with `needle` (b'penmentor', b'penmentor.plot') on its command line?
    Never signal a stranger that reused the pid."""
    pid = int(pid)
    if not WIN:
        try:
            return needle in Path(f'/proc/{pid}/cmdline').read_bytes()
        except OSError:
            return False
    try:
        import psutil
        return needle.decode() in ' '.join(psutil.Process(pid).cmdline())
    except ImportError:
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            ctypes.windll.kernel32.CloseHandle(h)
        return bool(h)
    except Exception:  # psutil.NoSuchProcess, AccessDenied
        return False


def stop(pid):
    os.kill(int(pid), signal.SIGTERM)  # TerminateProcess on Windows


def nudge(pid):
    """Tell the penmentor whose marks are up that its key was pressed again (what for is in CACHE/poke)."""
    if not WIN:
        return os.kill(int(pid), signal.SIGUSR1)
    for _ in range(20):
        try:
            with open(rf'\\.\pipe\{PIPE}', 'wb') as f:
                f.write(b'poke\n')
            return
        except OSError:  # busy for a moment: the server is between two clients
            time.sleep(.05)
    raise OSError('penmentor did not answer')


_server = []


def listen(poked):
    """poked() in the Qt thread whenever nudge() reaches this process. Call it once a QApplication exists."""
    if not WIN:
        from PyQt6.QtCore import QTimer
        signal.signal(signal.SIGUSR1, lambda *a: QTimer.singleShot(0, poked))
        return
    if _server:
        _server[1] = poked  # the newest overlay answers
        return
    from PyQt6.QtNetwork import QLocalServer
    s = QLocalServer()
    QLocalServer.removeServer(PIPE)
    s.listen(PIPE)
    _server[:] = [s, poked]

    def accept():  # a connection is the whole message
        while (c := s.nextPendingConnection()) is not None:
            c.disconnected.connect(c.deleteLater)
            _server[1]()
    s.newConnection.connect(accept)
