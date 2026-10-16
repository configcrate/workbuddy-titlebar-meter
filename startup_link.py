"""Per-user Startup shortcut; no elevation, scheduled task or client changes."""
import ctypes as C
import os
import subprocess
import uuid

DESCRIPTION = "ConfigCrate WorkBuddy Titlebar Meter"


def shortcut_path():
    return os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup", "ConfigCrate WorkBuddy Meter.lnk")


def _shell_link(path, target="", arguments="", directory="", write=False):
    # IShellLinkW + IPersistFile keep paths Unicode even on English Windows.
    # WScript.Shell's Save can corrupt non-ANSI shortcut paths on those systems.
    class GUID(C.Structure):
        _fields_ = [("data1", C.c_uint32), ("data2", C.c_uint16),
                    ("data3", C.c_uint16), ("data4", C.c_ubyte * 8)]

    guid = lambda value: GUID.from_buffer_copy(uuid.UUID(value).bytes_le)
    clsid = guid("00021401-0000-0000-c000-000000000046")
    iid = guid("000214f9-0000-0000-c000-000000000046")
    persist_iid = guid("0000010b-0000-0000-c000-000000000046")
    def check(hr):
        if hr < 0:
            raise OSError(f"Startup shortcut operation failed (HRESULT 0x{hr & 0xffffffff:08x})")

    def call(obj, slot, types, *values):
        table = C.cast(obj, C.POINTER(C.POINTER(C.c_void_p))).contents
        return C.WINFUNCTYPE(C.c_long, C.c_void_p, *types)(table[slot])(obj, *values)

    # WinDLL avoids OleDLL automatically raising before we can balance COM state.
    ole = C.WinDLL("ole32")
    ole.CoInitializeEx.argtypes = [C.c_void_p, C.c_uint32]
    ole.CoInitializeEx.restype = C.c_long
    ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, C.c_uint32,
                                     C.POINTER(GUID), C.POINTER(C.c_void_p)]
    ole.CoCreateInstance.restype = C.c_long
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    initialized = ole.CoInitializeEx(None, 2)
    if initialized != -2147417850:  # RPC_E_CHANGED_MODE: reuse caller's apartment.
        check(initialized)
    link, persist = C.c_void_p(), C.c_void_p()
    try:
        check(ole.CoCreateInstance(C.byref(clsid), None, 1, C.byref(iid), C.byref(link)))
        check(call(link, 0, [C.POINTER(GUID), C.POINTER(C.c_void_p)], C.byref(persist_iid), C.byref(persist)))
        if write:
            for slot, value in ((20, target), (11, arguments), (9, directory), (7, DESCRIPTION)):
                check(call(link, slot, [C.c_wchar_p], value))
            check(call(link, 15, [C.c_int], 7))
            check(call(persist, 6, [C.c_wchar_p, C.c_int], path, True))
        else:
            check(call(persist, 5, [C.c_wchar_p, C.c_uint32], path, 0))
        info = {}
        for key, slot in (("target", 3), ("arguments", 10), ("directory", 8), ("description", 6)):
            buffer = C.create_unicode_buffer(32768)
            types, values = [C.c_wchar_p, C.c_int], [buffer, len(buffer)]
            if slot == 3:
                types += [C.c_void_p, C.c_uint32]
                values += [None, 0]
            check(call(link, slot, types, *values))
            info[key] = buffer.value
        return info
    finally:
        if persist:
            call(persist, 2, [])
        if link:
            call(link, 2, [])
        if initialized >= 0:
            ole.CoUninitialize()


def details():
    path = shortcut_path()
    if not os.path.isfile(path):
        return None
    try:
        return _shell_link(path)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def arguments(script):
    return subprocess.list2cmdline([os.path.abspath(script), "--autostart"])


def matches(info, executable, script):
    return bool(info and info.get("description") == DESCRIPTION
                and os.path.normcase(info.get("target", "")) == os.path.normcase(os.path.abspath(executable))
                and info.get("arguments") == arguments(script)
                and os.path.normcase(info.get("directory", "")) == os.path.normcase(os.path.dirname(os.path.abspath(script))))


def install(executable, script):
    path = shortcut_path()
    if os.path.exists(path):
        info = details()
        if not info or info.get("description") != DESCRIPTION:
            raise OSError("Startup shortcut exists but is not owned by this tool")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    info = _shell_link(path, os.path.abspath(executable), arguments(script),
                       os.path.dirname(os.path.abspath(script)), write=True)
    if not matches(info, executable, script):
        raise OSError("Startup shortcut verification failed")


def remove(executable, script):
    if matches(details(), executable, script):
        os.remove(shortcut_path())
