"""Exercise our own temporary windows only; never close/move the user's WorkBuddy."""
import os
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import titlebar_meter as app
import window_anchor as native
from meter_core import titlebar_layout


class NativeLifecycleTest(unittest.TestCase):
    def test_owned_overlay_survives_host_replacement(self):
        native.dpi_aware()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(app, "CONFIG_PATH", os.path.join(folder, "config.json")), \
                patch.object(app, "STATE_PATH", os.path.join(folder, "state.json")), \
                patch.object(native, "STOP_EVENT", native.STOP_EVENT + ".Test." + str(os.getpid())), \
                patch.object(native, "host_is_active", return_value=True) as active:
            root = tk.Tk()
            root.withdraw()
            failures = []
            root.report_callback_exception = lambda *error: failures.append(error)
            host = tk.Toplevel(root)
            host.title("Meter lifecycle test — self-closing")
            host.geometry("900x500+150+150")
            root.update()
            host_hwnd = native.native_hwnd(host)
            scale = native.u.GetDpiForWindow(host_hwnd) / 96
            host.geometry(f"{round(950 * scale)}x{round(500 * scale)}+150+150")
            root.update()
            current = [host_hwnd]

            def find(_):
                hwnd = current[0]
                if not hwnd or not native.u.IsWindow(hwnd):
                    return None
                return native.Host(hwnd, "test-only", native.bounds_for(hwnd), native.u.GetDpiForWindow(hwnd),
                                   bool(native.u.IsIconic(hwnd)), False)

            meter = app.Meter(root)
            meter.finder.find = find
            meter.refresh_now = Mock()  # No credentials, network calls or real user data in this test.
            try:
                meter.tick()
                root.update()
                self.assertTrue(native.u.IsWindowVisible(meter.hwnd))
                self.assertEqual(native.getlong(meter.hwnd, -8), host_hwnd)
                self.assertTrue(native.getlong(meter.hwnd, -20) & 0x08000000)
                self.assertFalse(native.getlong(meter.hwnd, -20) & 0x8)

                host.geometry(f"{round(1000 * scale)}x{round(600 * scale)}+200+170")
                root.update()
                meter.tick()
                root.update()
                placement = titlebar_layout(native.bounds_for(host_hwnd), native.u.GetDpiForWindow(host_hwnd))
                self.assertEqual(native.bounds_for(meter.hwnd), (placement.x, placement.y,
                                 placement.x + placement.width, placement.y + placement.height))

                host.iconify()
                root.update()
                meter.tick()
                self.assertFalse(native.u.IsWindowVisible(meter.hwnd))
                host.deiconify()
                root.update()
                meter.tick()
                self.assertTrue(native.u.IsWindowVisible(meter.hwnd))

                active.return_value = False
                meter.tick()
                self.assertFalse(native.u.IsWindowVisible(meter.hwnd))
                active.return_value = True
                meter.tick()
                self.assertTrue(native.u.IsWindowVisible(meter.hwnd))

                host.destroy()
                current[0] = 0
                root.update()
                meter.tick()
                self.assertTrue(root.winfo_exists())
                self.assertFalse(meter.visible)

                host = tk.Toplevel(root)
                host.title("Meter lifecycle reopen test — self-closing")
                host.geometry(f"{round(950 * scale)}x{round(500 * scale)}+150+150")
                root.update()
                current[0] = native.native_hwnd(host)
                meter.tick()
                root.update()
                self.assertTrue(native.u.IsWindowVisible(meter.hwnd))
                self.assertEqual(native.getlong(meter.hwnd, -8), current[0])
                self.assertFalse(failures, failures)
            finally:
                meter.quit()


if __name__ == "__main__":
    unittest.main(verbosity=2)
