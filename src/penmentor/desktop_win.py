"""The Windows desktop (10/11): screenshots, monitors, windows, menus, notifications, the pointer and Esc.

Same interface as desktop_x11. Everything here is plain Win32 through ctypes; the menus, the region picker and the
notifications are small Qt windows in their own process (picker.py), the way rofi, slop and notify-send are on Linux.
Coordinates: the screenshot covers the whole virtual desktop, so its (0, 0) is the desktop's top-left corner
(origin(), negative when a monitor sits left of or above the main one). Monitors and windows come back in shot pixels.
"""
import ctypes
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
dwmapi = ctypes.WinDLL('dwmapi')

# Per-monitor DPI awareness (v2) before any window exists, so screenshot pixels, window rects, the cursor and Qt's
# pixels (QT_ENABLE_HIGHDPI_SCALING=0, see __init__) are all physical pixels, whatever the display scaling.
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
except (AttributeError, OSError):
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()

LRESULT, WPARAM, LPARAM = ctypes.c_ssize_t, ctypes.c_size_t, ctypes.c_ssize_t
HWND = wintypes.HWND
user32.GetForegroundWindow.restype = HWND
user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
user32.SetForegroundWindow.argtypes = [HWND]
user32.BringWindowToTop.argtypes = [HWND]
user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
user32.IsIconic.argtypes = user32.IsWindowVisible.argtypes = user32.IsWindow.argtypes = [HWND]
user32.GetWindowLongW.argtypes = [HWND, ctypes.c_int]
user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [HWND]
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
dwmapi.DwmGetWindowAttribute.argtypes = [HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: helpers never flash a console


class Oops(Exception):
    """A problem you can fix: shown as a plain notification, no traceback."""


def sh(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True, creationflags=NO_WINDOW).stdout


# ---------- helper processes: menus, region picker, notifications (picker.py) ----------

def helper_env():
    src = str(Path(__file__).resolve().parent.parent)  # works from a checkout too
    return dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [src, os.environ.get('PYTHONPATH')])), PYTHONIOENCODING='utf-8')


WARM = {}  # prompt -> a menu process started early by prewarm(), waiting for its rows


def prewarm(prompt):
    """Start the menu's process now, so it loads Python and Qt (0.8 s) while penmentor imports and takes the
    screenshot. It shows nothing until rofi() sends its rows, so it is not in the screenshot; if they never come
    (penmentor stopped, or its marks were already up) it goes away by itself."""
    WARM[prompt] = subprocess.Popen([sys.executable, '-m', 'penmentor.picker', 'menu', prompt, '--warm'], env=helper_env(),
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                    encoding='utf-8', creationflags=NO_WINDOW)


def helper(*args, stdin=None, wait=True):
    """Run `python -m penmentor.picker ARGS`: (returncode, stdout) or the Popen."""
    env = helper_env()
    exe = sys.executable
    if not wait:
        pyw = Path(exe).with_name('pythonw.exe')
        return subprocess.Popen([str(pyw if pyw.exists() else exe), '-m', 'penmentor.picker', *args], env=env,
                                creationflags=NO_WINDOW | 0x00000200, close_fds=True)  # CREATE_NEW_PROCESS_GROUP: outlives us
    user32.AllowSetForegroundWindow(-1)  # ASFW_ANY: the menu may take the focus from the app you were writing in
    p = subprocess.run([exe, '-m', 'penmentor.picker', *args], input=stdin, capture_output=True, text=True,
                       encoding='utf-8', env=env, creationflags=NO_WINDOW)
    return p.returncode, p.stdout


def notify(msg, ms=None, critical=False, title='penmentor'):
    """A small toast bottom right that fades by itself (or on a click); it outlives penmentor, like notify-send."""
    helper('toast', title, msg, str(ms or (9000 if critical else 5000)), '1' if critical else '0', wait=False)


def rofi(options, prompt):
    """The picked (or typed) row, None on Esc. No options: a plain text box."""
    warm = WARM.pop(prompt, None)
    if warm and options and warm.poll() is None:
        user32.AllowSetForegroundWindow(-1)
        out = warm.communicate('\n'.join(options))[0]
        return out.strip() if warm.returncode == 0 else None
    code, out = helper('menu', prompt, stdin='\n'.join(options))
    return out.strip() if code == 0 else None


def select_region(geom):
    """Drag a box on the screen: (x0, y0, x1, y1) relative to geom, None on Esc."""
    code, out = helper('region')
    if code or not out.strip():
        return None
    x, y, w, h = map(int, out.split())
    return (x - geom[0], y - geom[1], x - geom[0] + w, y - geom[1] + h)


# ---------- screens and windows ----------

def origin():
    """The virtual desktop's top-left corner: where the screenshot's (0, 0) sits."""
    return user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)  # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN


class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', wintypes.RECT), ('rcWork', wintypes.RECT), ('dwFlags', wintypes.DWORD)]


def monitors(work=True):
    """Monitors (x, y, w, h) in desktop pixels, left to right; work: without the taskbar (as i3's areas skip its bars)."""
    out = []
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), LPARAM)

    def each(hmon, hdc, rect, data):
        mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            r = mi.rcWork if work else mi.rcMonitor
            out.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True
    user32.EnumDisplayMonitors(None, None, proc(each), 0)
    return sorted(out)


def rect_of(hwnd):
    """A window's visible frame (no invisible resize borders), in desktop pixels: (x, y, w, h)."""
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)):  # DWMWA_EXTENDED_FRAME_BOUNDS
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top


SKIP = {'Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'Windows.UI.Core.CoreWindow', 'NotifyIconOverflowWindow'}


def windows():
    """Top-level app windows you can see, front to back: [(hwnd, (x, y, w, h))] in desktop pixels.
    Windows mostly covered by ones in front are left out (their pixels are someone else's)."""
    found, me = [], os.getpid()
    proc = ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, LPARAM)
    cls = ctypes.create_unicode_buffer(256)

    def each(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or not user32.GetWindowTextLengthW(hwnd):
            return True
        if user32.GetWindowLongW(hwnd, -20) & 0x80:  # GWL_EXSTYLE, WS_EX_TOOLWINDOW: tooltips, our own overlay
            return True
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))  # DWMWA_CLOAKED: other virtual desktops
        user32.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if cloaked.value or cls.value in SKIP or pid.value == me:
            return True
        r = rect_of(hwnd)
        if r and r[2] > 40 and r[3] > 40:
            found.append((hwnd, r))
        return True
    user32.EnumWindows(proc(each), 0)
    out = []
    for hwnd, (x, y, w, h) in found:
        cx, cy = x + w / 2, y + h / 2
        if not any(a <= cx < a + c and b <= cy < b + d for _, (a, b, c, d) in out):
            out.append((hwnd, (x, y, w, h)))
    return out


def capture():
    """Everything on screen: (desktop image, monitors left to right, index of the focused one, visible windows),
    monitors and windows in shot pixels."""
    from PIL import ImageGrab  # here: the menu, toasts and the keys import this module and never take a screenshot
    try:
        shot = ImageGrab.grab(all_screens=True).convert('RGB')  # the whole virtual desktop, no cursor
    except OSError:
        raise Oops('Could not take a screenshot.')
    ox, oy = origin()
    W, H = shot.size
    shift = lambda r: (r[0] - ox, r[1] - oy, r[2], r[3])
    screens = [shift(r) for r in monitors()] or [(0, 0, W, H)]
    wins = []
    for _, r in windows():
        x, y, w, h = shift(r)
        x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)  # maximised windows overhang their monitor
        if x1 - x0 > 40 and y1 - y0 > 40:
            wins.append((x0, y0, x1 - x0, y1 - y0))
    fg = user32.GetForegroundWindow()
    focus = fg and rect_of(fg)
    if not focus:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        focus = (pt.x, pt.y, 1, 1)
    focus = shift(focus)
    cx, cy = focus[0] + focus[2] / 2, focus[1] + focus[3] / 2
    main = next((i for i, (x, y, w, h) in enumerate(screens) if x <= cx < x + w and y <= cy < y + h), 0)
    return shot, screens, main, wins


# ---------- focus, pointer, keys ----------

def active_window():
    """The focused app's window handle (to hand the focus back later), or None."""
    return user32.GetForegroundWindow() or None


def force_foreground(hwnd):
    """Bring a window to the front with the keyboard focus. Windows only lets the foreground app do that, so
    borrow its input queue for a moment (and tap Alt, which lifts the foreground lock)."""
    if not hwnd or not user32.IsWindow(hwnd):
        return
    fg = user32.GetForegroundWindow()
    if fg == hwnd:
        return
    me, them = kernel32.GetCurrentThreadId(), user32.GetWindowThreadProcessId(fg, None) if fg else 0
    user32.keybd_event(0x12, 0, 0, 0), user32.keybd_event(0x12, 0, 2, 0)  # VK_MENU down, up
    if them and them != me:
        user32.AttachThreadInput(me, them, True)
    try:
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if them and them != me:
            user32.AttachThreadInput(me, them, False)


def activate(window):
    """Give the focus back to the app you were writing in, once the overlay or a menu has had the keyboard."""
    if window:
        force_foreground(window)


def pointer():
    """(x, y, held) of the mouse or pen anywhere on the desktop (held: a button or the pen tip is down), or None."""
    pt = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(pt)):
        return None
    held = any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))  # left, right, middle
    return pt.x, pt.y, held


def process_name(pid):
    """The executable's file name ('xournalpp.exe') of a process, or ''."""
    h = kernel32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf, n = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
        return Path(buf.value).name if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
    finally:
        kernel32.CloseHandle(h)


def focused_app():
    """(executable name, pid) of the active window, or (None, None)."""
    fg = user32.GetForegroundWindow()
    if not fg:
        return None, None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
    return process_name(pid.value) or None, str(pid.value)


VK = {'ctrl': 0x11, 'control': 0x11, 'alt': 0x12, 'shift': 0x10, 'super': 0x5B, 'win': 0x5B, 'escape': 0x1B, 'esc': 0x1B,
      'return': 0x0D, 'enter': 0x0D, 'space': 0x20, 'tab': 0x09, **{f'f{i}': 0x6F + i for i in range(1, 25)}}


def vk(name):
    name = name.lower()
    if name in VK:
        return VK[name]
    if len(name) == 1 and name.isalnum():
        return ord(name.upper())
    raise ValueError(f'unknown key: {name}')


def press(keys):
    """Type a key combination ('ctrl+alt+shift+F12') into the focused window."""
    codes = [vk(k) for k in keys.split('+')]
    for c in codes:
        user32.keybd_event(c, 0, 0, 0)
    for c in reversed(codes):
        user32.keybd_event(c, 0, 2, 0)  # KEYEVENTF_KEYUP


def on_escape(callback):
    """callback() on a thread whenever Escape is pressed, wherever the focus is; the key still reaches your apps
    (and penmentor's own menus), so Esc stops penmentor while the model thinks.
    Windows is asked 30 times a second rather than hooked: a keyboard hook would put every key you type through this
    Python process, slowing your typing whenever it is busy, and Windows silently drops hooks that answer late."""
    def loop():
        down = bool(user32.GetAsyncKeyState(0x1B) & 0x8000)  # still held from closing a menu: not a new press
        while True:
            time.sleep(.03)
            state = user32.GetAsyncKeyState(0x1B)  # high bit: down now; low bit: pressed since we last asked (a quick tap)
            now = bool(state & 0x8000)
            if (now or state & 1) and not down:
                threading.Thread(target=callback, daemon=True).start()
            down = now
    threading.Thread(target=loop, daemon=True).start()
