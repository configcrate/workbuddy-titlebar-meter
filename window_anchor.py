"""WorkBuddy window discovery and positioning of our own overlay (Win32)."""
import ctypes as C
from ctypes import wintypes as W
import os
import time
from dataclasses import dataclass
from meter_core import is_main_candidate, variant_for_path

u = C.WinDLL("user32", use_last_error=True)
k = C.WinDLL("kernel32", use_last_error=True)
dwm = C.WinDLL("dwmapi", use_last_error=True)
LONG_PTR = C.c_ssize_t
WNDENUM = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)


def api(dll, name, args, result):
    func = getattr(dll, name)
    func.argtypes, func.restype = args, result
    return func


api(u, "EnumWindows", [WNDENUM, W.LPARAM], W.BOOL)
for name in ("IsWindow", "IsWindowVisible", "IsIconic", "IsZoomed"):
    api(u, name, [W.HWND], W.BOOL)
api(u, "GetWindow", [W.HWND, W.UINT], W.HWND)
api(u, "GetAncestor", [W.HWND, W.UINT], W.HWND)
api(u, "GetForegroundWindow", [], W.HWND)
api(u, "GetWindowRect", [W.HWND, C.POINTER(W.RECT)], W.BOOL)
api(u, "GetWindowThreadProcessId", [W.HWND, C.POINTER(W.DWORD)], W.DWORD)
api(u, "GetClassNameW", [W.HWND, W.LPWSTR, C.c_int], C.c_int)
api(u, "GetWindowTextLengthW", [W.HWND], C.c_int)
api(u, "GetDpiForWindow", [W.HWND], W.UINT)
api(u, "ShowWindow", [W.HWND, C.c_int], W.BOOL)
api(u, "SetWindowPos", [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT], W.BOOL)
api(u, "ReleaseCapture", [], W.BOOL)
api(u, "PostMessageW", [W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.BOOL)
api(u, "SetForegroundWindow", [W.HWND], W.BOOL)
getlong_name = "GetWindowLongPtrW" if C.sizeof(C.c_void_p) == 8 else "GetWindowLongW"
setlong_name = "SetWindowLongPtrW" if C.sizeof(C.c_void_p) == 8 else "SetWindowLongW"
getlong = api(u, getlong_name, [W.HWND, C.c_int], LONG_PTR)
setlong = api(u, setlong_name, [W.HWND, C.c_int, LONG_PTR], LONG_PTR)
api(k, "OpenProcess", [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
api(k, "QueryFullProcessImageNameW", [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL)
api(k, "CloseHandle", [W.HANDLE], W.BOOL)
api(k, "CreateMutexW", [C.c_void_p, W.BOOL, W.LPCWSTR], W.HANDLE)
api(k, "CreateEventW", [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR], W.HANDLE)
api(k, "OpenEventW", [W.DWORD, W.BOOL, W.LPCWSTR], W.HANDLE)
api(k, "SetEvent", [W.HANDLE], W.BOOL)
api(k, "ResetEvent", [W.HANDLE], W.BOOL)
api(k, "WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD)
api(dwm, "DwmGetWindowAttribute", [W.HWND, W.DWORD, C.c_void_p, W.DWORD], C.c_long)
MUTEX = "Local\\ConfigCrate.WorkBuddyTitlebarMeter.v2"
STOP_EVENT = MUTEX + ".Stop"
INSTANCE_HANDLE = None


def dpi_aware():
    try:
        api(u, "SetProcessDpiAwarenessContext", [C.c_void_p], W.BOOL)(C.c_void_p(-4))
    except (AttributeError, OSError):
        u.SetProcessDPIAware()


def single_instance():
    global INSTANCE_HANDLE
    handle = k.CreateMutexW(None, False, MUTEX)
    error = C.get_last_error()
    if not handle:
        raise C.WinError(error)
    if error == 183:
        k.CloseHandle(handle)
        return False
    INSTANCE_HANDLE = handle
    return True


def request_stop():
    handle = k.OpenEventW(2, False, STOP_EVENT)
    if handle:
        k.SetEvent(handle)
        k.CloseHandle(handle)


class StopSignal:
    def __init__(self):
        self.handle = k.CreateEventW(None, True, False, STOP_EVENT)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        k.ResetEvent(self.handle)

    def is_set(self):
        return k.WaitForSingleObject(self.handle, 0) == 0

    def close(self):
        k.CloseHandle(self.handle)


def process_path(hwnd):
    pid = W.DWORD()
    u.GetWindowThreadProcessId(hwnd, C.byref(pid))
    handle = k.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return ""
    try:
        size = W.DWORD(32768)
        buffer = C.create_unicode_buffer(size.value)
        return buffer.value if k.QueryFullProcessImageNameW(handle, 0, buffer, C.byref(size)) else ""
    finally:
        k.CloseHandle(handle)


def bounds_for(hwnd):
    rect = W.RECT()
    if not u.GetWindowRect(hwnd, C.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)


def is_cloaked(hwnd):
    value = W.DWORD()
    return dwm.DwmGetWindowAttribute(hwnd, 14, C.byref(value), C.sizeof(value)) == 0 and value.value != 0


@dataclass
class Host:
    hwnd: int
    path: str
    bounds: tuple
    dpi: int
    minimized: bool
    cloaked: bool


class WindowFinder:
    def __init__(self):
        self.path_cache = {}

    def find(self, preferred=0, variant=None):
        candidates = []
        now = time.monotonic()

        @WNDENUM
        def collect(hwnd, _):
            if not u.IsWindowVisible(hwnd) or not u.GetWindowTextLengthW(hwnd):
                return True
            cls = C.create_unicode_buffer(128)
            u.GetClassNameW(hwnd, cls, len(cls))
            if not cls.value.startswith("Chrome_WidgetWin_"):
                return True
            rect = bounds_for(hwnd)
            if not rect:
                return True
            iconic = bool(u.IsIconic(hwnd))
            pid = W.DWORD()
            u.GetWindowThreadProcessId(hwnd, C.byref(pid))
            cached = self.path_cache.get(pid.value)
            if cached and now - cached[0] < 3:
                path = cached[1]
            else:
                path = process_path(hwnd)
                self.path_cache[pid.value] = (now, path)
            if variant is not None and variant_for_path(path) != variant:
                return True
            check_rect = (0, 0, 800, 600) if iconic and preferred == hwnd else rect
            if is_main_candidate(path, cls.value, check_rect, bool(u.GetWindow(hwnd, 4)),
                                 bool(getlong(hwnd, -20) & 0x80)):
                candidates.append(Host(hwnd, path, rect, u.GetDpiForWindow(hwnd) or 96,
                                       iconic, bool(is_cloaked(hwnd))))
            return True

        u.EnumWindows(collect, 0)
        self.path_cache = {pid: item for pid, item in self.path_cache.items() if now - item[0] < 10}
        foreground = u.GetForegroundWindow()
        for hwnd in (foreground, preferred):
            for host in candidates:
                if host.hwnd == hwnd:
                    return host
        return next((host for host in candidates if not host.minimized), candidates[0] if candidates else None)


def native_hwnd(widget):
    widget.update_idletasks()
    return u.GetAncestor(widget.winfo_id(), 2)


def is_our_window(hwnd):
    if not hwnd or not u.IsWindow(hwnd):
        return False
    pid = W.DWORD()
    u.GetWindowThreadProcessId(hwnd, C.byref(pid))
    return pid.value == os.getpid()


def configure_overlay(hwnd, owner):
    if not is_our_window(hwnd):
        return
    style = getlong(hwnd, -20)
    setlong(hwnd, -20, (style | 0x80 | 0x08000000) & ~0x40000 & ~0x8)
    setlong(hwnd, -8, owner)


def host_is_active(host, overlay_hwnd):
    foreground = u.GetForegroundWindow()
    if foreground in (host.hwnd, overlay_hwnd):
        return True
    return bool(foreground and u.GetAncestor(foreground, 3) == host.hwnd)


def place_overlay(hwnd, owner, placement):
    if not is_our_window(hwnd):
        return False
    if getlong(hwnd, -8) != owner:
        setlong(hwnd, -8, owner)
    return bool(u.SetWindowPos(hwnd, 0, placement.x, placement.y, placement.width, placement.height,
                               0x10 | 0x40 | 0x200))


def hide_overlay(hwnd):
    if is_our_window(hwnd):
        u.ShowWindow(hwnd, 0)


def drag_host(hwnd, x, y):
    u.ReleaseCapture()
    u.SetForegroundWindow(hwnd)
    position = (int(x) & 0xffff) | ((int(y) & 0xffff) << 16)
    u.PostMessageW(hwnd, 0xA1, 2, position)


def toggle_maximize(hwnd):
    u.PostMessageW(hwnd, 0x112, 0xF120 if u.IsZoomed(hwnd) else 0xF030, 0)
