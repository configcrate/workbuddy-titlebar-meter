import os
import runpy
import tempfile
import unittest
from unittest.mock import Mock, mock_open, patch

import startup_link as startup
import titlebar_meter as app
import window_anchor as native


class StartupTests(unittest.TestCase):
    def test_real_unicode_shortcut_round_trip(self):
        # Uses a temporary link only; never modifies the real Startup folder.
        with tempfile.TemporaryDirectory(prefix="积分 自启 ") as folder, \
                patch.object(startup, "shortcut_path", return_value=os.path.join(folder, "test.lnk")):
            script = os.path.join(folder, "meter.pyw")
            executable = app.pythonw_exe()
            startup.install(executable, script)
            self.assertTrue(startup.matches(startup.details(), executable, script))
            self.assertFalse(startup.matches(startup.details(), executable, script + ".other"))
            startup.remove(executable, script + ".other")
            self.assertTrue(os.path.exists(startup.shortcut_path()))
            startup.remove(executable, script)
            self.assertFalse(os.path.exists(startup.shortcut_path()))

    def test_foreign_shortcut_is_not_overwritten(self):
        with patch.object(startup.os.path, "exists", return_value=True), \
                patch.object(startup, "details", return_value={"description": "other app"}), \
                patch.object(startup, "_shell_link") as shell:
            with self.assertRaises(OSError):
                startup.install("pythonw.exe", "meter.pyw")
            shell.assert_not_called()

    def test_install_migrates_only_after_shortcut_is_verified(self):
        with patch.object(startup, "install", side_effect=OSError("failed")), \
                patch.object(app, "remove_run_entry") as remove:
            with self.assertRaises(OSError):
                app.install_autostart()
            remove.assert_not_called()

    def test_failed_gui_start_releases_single_instance_lock(self):
        with patch.object(app.sys, "argv", ["meter.pyw", "--autostart"]), \
                patch.object(native, "dpi_aware"), \
                patch.object(native, "single_instance", return_value=True), \
                patch.object(native, "release_instance") as release, \
                patch.object(app.tk, "Tk", side_effect=app.tk.TclError("desktop not ready")):
            with self.assertRaises(app.tk.TclError):
                app.run()
            release.assert_called_once()

    def test_login_bootstrap_retries_then_stops_on_success(self):
        launch = runpy.run_path(os.path.join(os.path.dirname(__file__), "meter.pyw"))["launch"]
        module = Mock(main=Mock(side_effect=[OSError("not ready"), None]))
        with patch.dict("sys.modules", {"titlebar_meter": module}), \
                patch("sys.argv", ["meter.pyw", "--autostart"]), \
                patch("os.chdir"), patch("builtins.open", mock_open()), patch("time.sleep") as sleep:
            self.assertEqual(launch(), 0)
            self.assertEqual(module.main.call_count, 2)
            sleep.assert_called_once_with(10)

    def test_login_bootstrap_retry_is_bounded(self):
        launch = runpy.run_path(os.path.join(os.path.dirname(__file__), "meter.pyw"))["launch"]
        module = Mock(main=Mock(side_effect=OSError("not ready")))
        with patch.dict("sys.modules", {"titlebar_meter": module}), \
                patch("sys.argv", ["meter.pyw", "--autostart"]), \
                patch("os.chdir"), patch("builtins.open", mock_open()), patch("time.sleep") as sleep:
            self.assertEqual(launch(), 1)
            self.assertEqual(module.main.call_count, 13)
            self.assertEqual(sleep.call_count, 12)

    def test_manual_launch_fails_promptly(self):
        launch = runpy.run_path(os.path.join(os.path.dirname(__file__), "meter.pyw"))["launch"]
        module = Mock(main=Mock(side_effect=ImportError("tkinter missing")))
        with patch.dict("sys.modules", {"titlebar_meter": module}), \
                patch("sys.argv", ["meter.pyw"]), \
                patch("os.chdir"), patch("builtins.open", mock_open()) as log, patch("time.sleep") as sleep:
            self.assertEqual(launch(), 1)
            module.main.assert_called_once()
            sleep.assert_not_called()
            self.assertLessEqual(len(log().write.call_args.args[0]), 8192)


if __name__ == "__main__":
    unittest.main()
