import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import meter_core as core
import titlebar_meter as app
import window_anchor as native


def snapshot(**changes):
    raw = dict(ok=True, remain=4115.60, total=8756, updatedAt=1_000_000, plan="标准版")
    raw.update(changes)
    return core.normalize_snapshot(raw)


class LayoutTests(unittest.TestCase):
    def test_dpi_and_caption_buttons(self):
        for dpi in (96, 120, 144, 192, 240):
            with self.subTest(dpi=dpi):
                scale = dpi / 96
                p = core.titlebar_layout((0, 0, round(1200 * scale), round(800 * scale)), dpi)
                self.assertEqual(p.width, round(220 * scale))
                self.assertEqual(round(1200 * scale) - p.x - p.width, round(158 * scale))
                self.assertGreaterEqual(p.x, round(340 * scale))
                self.assertLessEqual(p.y + p.height, round(32 * scale))

    def test_too_narrow_hides_instead_of_covering_menus(self):
        self.assertIsNone(core.titlebar_layout((0, 0, 650, 800)))
        self.assertIsNotNone(core.titlebar_layout((0, 0, 700, 800)))

    def test_negative_monitor_coordinates(self):
        p = core.titlebar_layout((-1600, -900, -400, -100), 96)
        self.assertEqual(p.x, -778)
        self.assertEqual(p.y, -898)

    def test_small_window_height(self):
        self.assertIsNone(core.titlebar_layout((0, 0, 1200, 100)))


class DiscoveryTests(unittest.TestCase):
    def candidate(self, **changes):
        args = dict(path=r"D:\Program Files\WorkBuddy\WorkBuddy.exe", class_name="Chrome_WidgetWin_1",
                    bounds=(0, 0, 1200, 900))
        args.update(changes)
        return core.is_main_candidate(**args)

    def test_actual_app(self):
        self.assertTrue(self.candidate())

    def test_international_app_and_region(self):
        self.assertTrue(self.candidate(path=r"E:\Programs\WorkBuddyAI\WorkBuddyAI.exe"))
        self.assertEqual(core.variant_for_path("E:/WorkBuddyAI/WORKBUDDYAI.EXE"), "ai")
        self.assertEqual(core.variant_for_path("D:/WorkBuddy/WorkBuddy.exe"), "cn")
        self.assertIsNone(core.variant_for_path("E:/WorkBuddyAI/fake.exe"))

    def test_browser_mentioning_workbuddy_is_not_app(self):
        self.assertFalse(self.candidate(path=r"C:\Chrome\chrome.exe"))
        self.assertFalse(self.candidate(path=r"C:\WorkBuddyFake.exe"))

    def test_pet_is_not_main_window(self):
        self.assertFalse(self.candidate(bounds=(0, 0, 200, 160)))
        self.assertFalse(self.candidate(tool_window=True))

    def test_dialog_is_not_main_window(self):
        self.assertFalse(self.candidate(owned=True))
        self.assertFalse(self.candidate(class_name="#32770"))


class DataTests(unittest.TestCase):
    def test_region_cache_must_be_tagged_and_match(self):
        for region in ("cn", "ai"):
            self.assertIsNotNone(core.normalize_snapshot(snapshot(variant=region), region))
            self.assertIsNone(core.normalize_snapshot(snapshot(), region))
            other = "ai" if region == "cn" else "cn"
            self.assertIsNone(core.normalize_snapshot(snapshot(variant=other), region))

    def test_cache_removes_private_fields(self):
        data = snapshot(uid="private", nickname="private", tokenExpiresAt=123, accessToken="private")
        self.assertEqual(set(data), {"ok", "remain", "total", "percent", "updatedAt", "plan"})
        self.assertAlmostEqual(data["percent"], 4115.6 / 8756 * 100)

    def test_reject_malformed_data(self):
        for invalid in (None, [], "text", {}, {"ok": False}):
            self.assertIsNone(core.normalize_snapshot(invalid))
        for changes in ({"remain": float("nan")}, {"total": float("inf")}, {"remain": -1},
                        {"updatedAt": 0}, {"total": "bad"}):
            self.assertIsNone(snapshot(**changes))

    def test_no_total_is_not_fake_zero_percent(self):
        data = snapshot(total=0)
        self.assertIsNone(data["percent"])
        self.assertNotIn("%", core.meter_text(data, "ok", 1_000_010, 300_000))

    def test_values_and_percent_are_bounded(self):
        self.assertEqual(snapshot(remain=100, total=50)["percent"], 100)
        self.assertEqual(snapshot(remain=0)["percent"], 0)
        self.assertEqual(core.fmt_num(12.5), "12.50")
        self.assertEqual(core.fmt_num(1200), "1,200")

    def test_error_retains_cache_but_is_explicitly_stale(self):
        text = core.meter_text(snapshot(), "error", 1_000_010, 300_000)
        self.assertIn("上次", text)
        self.assertIn("待更新", text)
        self.assertEqual(core.meter_color(snapshot(), "error", 1_000_010, 300_000, 0), "#777e8a")

    def test_old_snapshot_turns_gray(self):
        self.assertIn("待更新", core.meter_text(snapshot(), "ok", 2_000_000, 300_000))

    def test_low_credit_alerts(self):
        for remain, color in ((9, "#e5534b"), (19, "#e8a33d"), (80, core.PALETTES[0])):
            self.assertEqual(core.meter_color(snapshot(remain=remain, total=100), "ok", 1_000_010, 300_000, 0), color)

    def test_old_card_settings_migrate_to_fixed_anchor(self):
        config = core.sanitize_config(dict(follow=False, x=120, y=80, intervalMs=60_000))
        self.assertEqual(config["intervalMs"], 60_000)
        self.assertNotIn("follow", config)
        self.assertNotIn("x", config)
        self.assertEqual(core.sanitize_config({"intervalMs": 1, "palette": "bad"})["intervalMs"], 300_000)

    def test_autostart_quotes_spaces(self):
        command = core.autostart_command(r"C:\Program Files\Python\pythonw.exe", r"E:\测试 路径\meter.pyw")
        self.assertIn('"C:\\Program Files\\Python\\pythonw.exe"', command)
        self.assertIn('"E:\\测试 路径\\meter.pyw"', command)


class LifecycleTests(unittest.TestCase):
    def fake_meter(self, host=None):
        meter = object.__new__(app.Meter)
        meter.root = Mock()
        meter.closed, meter.busy, meter.visible = False, False, False
        meter.stop_signal = Mock(is_set=lambda: False)
        import queue
        meter.results = queue.Queue()
        meter.host = host
        meter.finder = Mock(find=lambda _: host)
        meter.generation, meter.hwnd, meter.next_refresh = 0, 123, 0
        meter.placement = None
        meter.cfg = core.sanitize_config({})
        meter.data = snapshot()
        meter.phase, meter.menu_open = "ok", False
        meter.hide_tooltip = Mock()
        meter.hide = Mock()
        meter.ensure_overlay = Mock()
        meter.draw = Mock()
        meter.refresh_now = Mock()
        meter.cancel_helper = Mock()
        return meter

    def host(self, **changes):
        args = dict(hwnd=111, path=r"C:\WorkBuddy\WorkBuddy.exe", bounds=(0, 0, 1200, 900),
                    dpi=96, minimized=False, cloaked=False)
        args.update(changes)
        return native.Host(**args)

    def test_no_workbuddy_no_ui_and_no_requests(self):
        meter = self.fake_meter()
        meter.tick()
        meter.hide.assert_called_once()
        meter.refresh_now.assert_not_called()
        meter.ensure_overlay.assert_not_called()

    def test_minimized_or_other_desktop_hides(self):
        for changes in ({"minimized": True}, {"cloaked": True}):
            meter = self.fake_meter(self.host(**changes))
            meter.tick()
            meter.hide.assert_called_once()
            meter.refresh_now.assert_not_called()

    def test_unrelated_foreground_hides(self):
        meter = self.fake_meter(self.host())
        with patch.object(native, "host_is_active", return_value=False):
            meter.tick()
        meter.hide.assert_called_once()
        meter.refresh_now.assert_not_called()

    def test_active_host_attaches_and_fetches(self):
        meter = self.fake_meter(self.host())
        with patch.object(native, "host_is_active", return_value=True), patch.object(native, "place_overlay", return_value=True):
            meter.tick()
        meter.ensure_overlay.assert_called_once()
        meter.refresh_now.assert_called_once()
        self.assertTrue(meter.visible)

    def test_close_and_reopen_host_uses_fresh_generation(self):
        meter = self.fake_meter(self.host())
        meter.finder.find = lambda _: None
        meter.tick()
        self.assertIsNone(meter.host)
        meter.cancel_helper.assert_called_once()
        self.assertEqual(meter.generation, 1)
        meter.finder.find = lambda _: self.host(hwnd=222)
        with patch.object(native, "host_is_active", return_value=True), patch.object(native, "place_overlay", return_value=True):
            meter.tick()
        self.assertEqual(meter.host.hwnd, 222)
        self.assertEqual(meter.generation, 2)
        meter.refresh_now.assert_called_once()

    def test_stop_signal_exits(self):
        meter = self.fake_meter()
        meter.stop_signal.is_set = lambda: True
        meter.quit = Mock()
        meter.tick()
        meter.quit.assert_called_once()

    def test_snapshot_is_atomically_replaced_not_appended(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "state.json")
            app.save_json(path, {"value": 1})
            app.save_json(path, {"value": 2})
            self.assertEqual(app.load_json(path), {"value": 2})
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_region_switch_uses_only_matching_cache(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(app, "STATE_PATH", os.path.join(folder, "state.json")), \
                patch.object(native, "host_is_active", return_value=False):
            meter = self.fake_meter(self.host())
            meter.data = snapshot(variant="cn", remain=900)
            meter.busy = True
            app.save_json(app.state_path("ai"), snapshot(variant="ai", remain=42))
            meter.finder.find = lambda _: self.host(hwnd=222, path="E:/WorkBuddyAI/WorkBuddyAI.exe")
            meter.tick()
            self.assertEqual(meter.data["variant"], "ai")
            self.assertEqual(meter.data["remain"], 42)
            self.assertFalse(meter.busy)
            # An old request must not clear the busy flag of a newer request.
            meter.busy = True
            meter.results.put((0, snapshot(variant="cn", remain=800), ""))
            meter.tick()
            self.assertTrue(meter.busy)
            self.assertEqual(meter.data["remain"], 42)

    def test_legacy_or_wrong_region_cache_is_not_shown(self):
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(app, "STATE_PATH", os.path.join(folder, "state.json")), \
                patch.object(native, "host_is_active", return_value=False):
            app.save_json(app.STATE_PATH, snapshot(remain=999))
            for cached in (snapshot(), snapshot(variant="cn")):
                app.save_json(app.state_path("ai"), cached)
                meter = self.fake_meter()
                meter.finder.find = lambda _: self.host(path="E:/WorkBuddyAI/WorkBuddyAI.exe")
                meter.tick()
                self.assertIsNone(meter.data)

    def test_wrong_region_response_is_rejected_and_never_cached(self):
        meter = self.fake_meter(self.host(path="E:/WorkBuddyAI/WorkBuddyAI.exe"))
        meter.data = None
        meter.results.put((0, snapshot(variant="cn"), ""))
        with patch.object(app, "save_json") as save, patch.object(native, "host_is_active", return_value=False):
            meter.tick()
        save.assert_not_called()
        self.assertIsNone(meter.data)
        self.assertEqual(meter.phase, "error")

    def test_refresh_forces_host_region_not_old_config(self):
        for region, path in (("cn", "C:/WorkBuddy/WorkBuddy.exe"), ("ai", "E:/WorkBuddyAI/WorkBuddyAI.exe")):
            meter = self.fake_meter(self.host(path=path))
            meter.cfg["variant"] = "ai" if region == "cn" else "cn"
            meter.fetch = Mock()
            with patch.object(app.threading, "Thread") as thread:
                app.Meter.refresh_now(meter)
            self.assertEqual(thread.call_args.kwargs["args"], (0, path, region))

    def test_valid_response_saves_only_its_region(self):
        meter = self.fake_meter(self.host(path="E:/WorkBuddyAI/WorkBuddyAI.exe"))
        meter.results.put((0, snapshot(variant="ai"), ""))
        with patch.object(app, "save_json") as save, patch.object(native, "host_is_active", return_value=False):
            meter.tick()
        self.assertEqual(meter.data["variant"], "ai")
        self.assertEqual(save.call_args.args[0], app.state_path("ai"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
