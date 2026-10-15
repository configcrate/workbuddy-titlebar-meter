"""Compact WorkBuddy titlebar companion; no independent desktop card or tray UI."""
import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
import winreg

from meter_core import (INTERVALS, PALETTES, autostart_command, fmt_num, meter_color,
                        meter_text, normalize_snapshot, sanitize_config, titlebar_layout, variant_for_path)
import window_anchor as native

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(APP_DIR, "meter.pyw")
CONFIG_PATH = os.path.join(APP_DIR, "meter_config.json")
STATE_PATH = os.path.join(APP_DIR, "meter_state.json")
HELPER = os.path.join(APP_DIR, "wb_credits_helper.cjs")
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "WorkBuddyCredits"
BACKGROUND = "#1f1f1f"


def state_path(variant):
    if variant not in ("cn", "ai"):
        raise ValueError("Unknown WorkBuddy variant")
    return os.path.splitext(STATE_PATH)[0] + "_" + variant + ".json"


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    except (OSError, ValueError):
        try:
            os.remove(temporary)
        except OSError:
            pass


def pythonw_exe():
    candidate = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return candidate if os.path.isfile(candidate) else sys.executable


def legacy_startup():
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup", "WorkBuddyCredits.cmd")


def remove_legacy_startup():
    path = legacy_startup()
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as stream:
            text = stream.read(16384)
        if APP_DIR.casefold() in text.casefold() and "meter.pyw" in text:
            os.remove(path)
    except OSError:
        pass


def install_autostart():
    command = autostart_command(pythonw_exe(), SCRIPT)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, RUN_NAME, 0, winreg.REG_SZ, command)
    remove_legacy_startup()


def is_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, RUN_NAME)[0] == autostart_command(pythonw_exe(), SCRIPT)
    except OSError:
        return False


def uninstall_autostart():
    if is_autostart():
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, RUN_NAME)
    remove_legacy_startup()


class Meter:
    def __init__(self, root):
        self.root = root
        root.withdraw()
        self.cfg = sanitize_config(load_json(CONFIG_PATH, {}))
        # Legacy untagged cache cannot safely be assigned to either account.
        self.data = None
        self.phase = "loading"
        self.error = ""
        self.finder = native.WindowFinder()
        self.stop_signal = native.StopSignal()
        self.host = None
        self.overlay = None
        self.hwnd = 0
        self.placement = None
        self.visible = False
        self.closed = False
        self.busy = False
        self.next_refresh = 0
        self.last_draw = None
        self.results = queue.Queue()
        self.process = None
        self.process_lock = threading.Lock()
        self.generation = 0
        self.tooltip = None
        self.tooltip_job = None
        self.menu_open = False
        self.context_menu = None
        self.press = None
        self._font_scale = None
        save_json(CONFIG_PATH, self.cfg)
        root.after(50, self.tick)

    def ensure_overlay(self):
        if native.is_our_window(self.hwnd):
            return
        # The hidden root must survive the host destroying its owned popup on exit.
        if self.overlay:
            try:
                self.overlay.destroy()
            except tk.TclError:
                pass
        self.overlay = tk.Toplevel(self.root)
        self.overlay.withdraw()
        self.overlay.title("WorkBuddy 标题栏积分")
        self.overlay.overrideredirect(True)
        self.overlay.configure(bg=BACKGROUND)
        p = self.placement
        self.overlay.geometry(f"{p.width}x{p.height}{p.x:+d}{p.y:+d}")
        self.canvas = tk.Canvas(self.overlay, bg=BACKGROUND, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.hwnd = native.native_hwnd(self.overlay)
        native.configure_overlay(self.hwnd, self.host.hwnd)
        self._font_scale = None
        self.last_draw = None
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double)
        self.canvas.bind("<Button-3>", self.show_menu)
        self.canvas.bind("<Enter>", self.tooltip_enter)
        self.canvas.bind("<Leave>", lambda event: self.hide_tooltip())
        self.overlay.deiconify()
        native.configure_overlay(self.hwnd, self.host.hwnd)
        native.hide_overlay(self.hwnd)

    def tick(self):
        if self.closed:
            return
        if self.stop_signal.is_set():
            self.quit()
            return
        while True:
            try:
                generation, result, error = self.results.get_nowait()
            except queue.Empty:
                break
            if generation == self.generation and self.host:
                self.busy = False
                variant = variant_for_path(self.host.path)
                snapshot = normalize_snapshot(result, expected_variant=variant)
                if snapshot:
                    self.data, self.phase, self.error = snapshot, "ok", ""
                    save_json(state_path(variant), snapshot)
                else:
                    self.phase = "error"
                    self.error = error or str((result or {}).get("error", "积分接口暂不可用"))[:160]
                    self.next_refresh = time.monotonic() + min(60, self.cfg["intervalMs"] / 1000)
        old_host = self.host.hwnd if self.host else 0
        host = self.finder.find(old_host)
        if (old_host, self.host.path if self.host else None) != (host.hwnd if host else 0, host.path if host else None):
            self.generation += 1
            self.cancel_helper()
            self.busy = False
            self.next_refresh = 0
            self.hide_tooltip()
            variant = variant_for_path(host.path) if host else None
            self.data = normalize_snapshot(load_json(state_path(variant)), expected_variant=variant) if variant else None
            self.phase, self.error = "loading", ""
            self.last_draw = None
        self.host = host
        if not host:
            self.hide()
            self.root.after(1200, self.tick)
            return
        placement = titlebar_layout(host.bounds, host.dpi)
        show = bool(placement and not host.minimized and not host.cloaked
                    and native.host_is_active(host, self.hwnd))
        if show:
            changed = placement != self.placement or not self.visible
            self.placement = placement
            self.ensure_overlay()
            if changed:
                self.hide_tooltip()
            if native.place_overlay(self.hwnd, host.hwnd, placement):
                self.visible = True
                self.draw()
            if time.monotonic() >= self.next_refresh and not self.busy:
                self.refresh_now()
        elif not self.menu_open:
            self.hide()
        self.root.after(160 if show else 450, self.tick)

    def hide(self):
        native.hide_overlay(self.hwnd)
        self.visible = False
        self.hide_tooltip()

    def refresh_now(self):
        if self.busy or not self.host or self.host.minimized or self.closed:
            return
        self.busy = True
        self.phase = "refreshing" if self.data else "loading"
        self.next_refresh = time.monotonic() + self.cfg["intervalMs"] / 1000
        generation, executable, variant = self.generation, self.host.path, variant_for_path(self.host.path)
        threading.Thread(target=self.fetch, args=(generation, executable, variant), daemon=True).start()

    def fetch(self, generation, executable, variant):
        result, error, proc = None, "", None
        try:
            env = dict(os.environ, ELECTRON_RUN_AS_NODE="1", ELECTRON_NO_ATTACH_CONSOLE="1")
            with self.process_lock:
                if self.closed or generation != self.generation:
                    return
                proc = subprocess.Popen([executable, HELPER, "--variant", variant], cwd=APP_DIR,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        env=env, creationflags=0x08000000)
                self.process = proc
            stdout, _ = proc.communicate(timeout=45)
            for line in reversed(stdout.decode("utf-8", errors="replace").splitlines()):
                start = line.find('{"ok"')
                if start >= 0:
                    try:
                        candidate = json.loads(line[start:])
                        if isinstance(candidate, dict):
                            result = candidate
                            break
                    except ValueError:
                        pass
            if result is None:
                error = "助手未返回积分，请确认 WorkBuddy 已登录"
        except subprocess.TimeoutExpired:
            if proc:
                proc.kill()
                proc.communicate()
            error = "读取超时，将自动重试"
        except OSError:
            error = "无法启动积分助手，请重新打开 WorkBuddy"
        finally:
            with self.process_lock:
                if self.process is proc:
                    self.process = None
            self.results.put((generation, result, error))

    def cancel_helper(self):
        # Only our own helper child, never the user's main WorkBuddy process.
        with self.process_lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                except OSError:
                    pass

    def draw(self):
        p = self.placement
        if not p:
            return
        if self._font_scale != p.scale:
            family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in tkfont.families() else "Segoe UI"
            self.font = tkfont.Font(family=family, size=-round(13 * p.scale))
            self.small_font = tkfont.Font(family=family, size=-round(11 * p.scale))
            self._font_scale = p.scale
        now_ms = time.time() * 1000
        label = meter_text(self.data, self.phase, now_ms, self.cfg["intervalMs"])
        color = meter_color(self.data, self.phase, now_ms, self.cfg["intervalMs"], self.cfg["palette"])
        signature = (p, label, color, self.data.get("percent") if self.data else None)
        if signature == self.last_draw:
            return
        self.last_draw = signature
        c = self.canvas
        c.delete("all")
        c.configure(width=p.width, height=p.height)
        px = lambda n: round(n * p.scale)
        right = p.width - px(25)
        while label and self.font.measure(label) > right - px(10):
            label = label[:-2] + "…"
        c.create_text(px(8), px(10), anchor="w", text=label, font=self.font,
                      fill="#c9cdd3" if color != "#777e8a" else "#92969d")
        c.create_rectangle(px(8), px(22), right - px(3), px(24), fill="#3b3e43", outline="")
        if self.data and self.data["percent"] is not None:
            end = px(8) + (right - px(11)) * self.data["percent"] / 100
            if end > px(8):
                c.create_rectangle(px(8), px(22), end, px(24), fill=color, outline="")
        c.create_rectangle(p.width - px(16), px(8), p.width - px(8), px(16),
                           fill=PALETTES[self.cfg["palette"]], outline="")

    def save_config(self):
        save_json(CONFIG_PATH, self.cfg)
        self.last_draw = None

    def cycle_palette(self):
        self.cfg["palette"] = (self.cfg["palette"] + 1) % len(PALETTES)
        self.save_config()

    def on_press(self, event):
        self.hide_tooltip()
        self.press = (event.x_root, event.y_root, event.x)
        return "break"

    def on_drag(self, event):
        if self.press and self.host and self.placement:
            x, y, local_x = self.press
            if local_x < self.placement.width - round(25 * self.placement.scale) and abs(x - event.x_root) + abs(y - event.y_root) > 4:
                self.press = None
                native.drag_host(self.host.hwnd, event.x_root, event.y_root)
        return "break"

    def on_release(self, event):
        if self.press and self.placement:
            if self.press[2] >= self.placement.width - round(25 * self.placement.scale):
                self.cycle_palette()
            self.press = None
        return "break"

    def on_double(self, event):
        if self.host and self.placement and event.x < self.placement.width - round(25 * self.placement.scale):
            native.toggle_maximize(self.host.hwnd)
        self.press = None
        return "break"

    def show_menu(self, event):
        self.hide_tooltip()
        if self.context_menu:
            try:
                self.context_menu.destroy()
            except tk.TclError:
                pass
        self.menu_open = True
        menu = tk.Menu(self.overlay, tearoff=False)
        self.context_menu = menu
        menu.add_command(label="立即刷新", command=self.refresh_now)
        menu.add_command(label="积分详情", command=self.show_details)
        menu.add_command(label="切换颜色", command=self.cycle_palette)
        sub = tk.Menu(menu, tearoff=False)
        for interval in INTERVALS:
            mark = "✓ " if interval == self.cfg["intervalMs"] else ""
            sub.add_command(label=f"{mark}{interval // 60000} 分钟",
                            command=lambda value=interval: self.set_interval(value))
        menu.add_cascade(label="刷新间隔", menu=sub)
        menu.add_separator()
        menu.add_command(label="关闭登录自启" if is_autostart() else "开启登录自启",
                         command=self.toggle_autostart)
        menu.add_command(label="退出积分条", command=self.quit)
        def dismiss(_event):
            self.menu_open = False
            self.context_menu = None
            if not self.closed:
                self.root.after_idle(menu.destroy)
        menu.bind("<Unmap>", dismiss)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
        return "break"

    def set_interval(self, value):
        self.cfg["intervalMs"] = value
        self.next_refresh = time.monotonic() + value / 1000
        self.save_config()

    def toggle_autostart(self):
        try:
            uninstall_autostart() if is_autostart() else install_autostart()
        except OSError:
            self.error = "无法修改登录自启，请检查当前用户权限"

    def details_text(self):
        if not self.data:
            return "正在读取 WorkBuddy 积分" if self.busy else self.error or "暂时没有积分数据"
        data = self.data
        date = time.strftime("%m月%d日 %H:%M:%S", time.localtime(data["updatedAt"] / 1000))
        percentage = f"{data['percent']:.1f}%" if data["percent"] is not None else "官方未返回总额度"
        text = f"剩余积分：{fmt_num(data['remain'])}\n总额度：{fmt_num(data['total'])}\n剩余比例：{percentage}"
        if data["plan"]:
            text += f"\n套餐：{data['plan']}"
        text += f"\n更新于：{date}\n右键可刷新；拖动可移动 WorkBuddy"
        if self.phase == "error":
            text += "\n上次成功数据；" + self.error
        return text

    def tooltip_enter(self, event):
        self.hide_tooltip()
        self.tooltip_job = self.root.after(650, self.show_details)

    def show_details(self):
        self.hide_tooltip()
        if not self.visible or not self.placement or not self.host:
            return
        tooltip = tk.Toplevel(self.root)
        tooltip.withdraw()
        tooltip.overrideredirect(True)
        tk.Label(tooltip, text=self.details_text(), justify="left", bg="#292b30", fg="#e8e9eb",
                 font=self.small_font, padx=12, pady=10, relief="solid", borderwidth=1).pack()
        tooltip.update_idletasks()
        p = self.placement
        width, height = tooltip.winfo_reqwidth(), tooltip.winfo_reqheight()
        tooltip.geometry(f"{width}x{height}{p.x:+d}{p.y + p.height + 5:+d}")
        hwnd = native.native_hwnd(tooltip)
        native.configure_overlay(hwnd, self.host.hwnd)
        tooltip.deiconify()
        native.configure_overlay(hwnd, self.host.hwnd)
        native.u.SetWindowPos(hwnd, 0, p.x, p.y + p.height + 5, width, height, 0x10 | 0x40 | 0x200)
        self.tooltip = tooltip
        self.tooltip_job = self.root.after(6500, self.hide_tooltip)

    def hide_tooltip(self):
        if self.tooltip_job:
            try:
                self.root.after_cancel(self.tooltip_job)
            except tk.TclError:
                pass
            self.tooltip_job = None
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except tk.TclError:
                pass
            self.tooltip = None

    def quit(self):
        if self.closed:
            return
        self.closed = True
        self.cancel_helper()
        self.hide_tooltip()
        self.stop_signal.close()
        save_json(CONFIG_PATH, self.cfg)
        self.root.destroy()


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args()
    native.dpi_aware()
    if args.uninstall or args.stop:
        if args.uninstall:
            uninstall_autostart()
        native.request_stop()
        return
    if args.diagnose:
        host = native.WindowFinder().find()
        placement = titlebar_layout(host.bounds, host.dpi) if host else None
        print(json.dumps({"host": host.__dict__ if host else None,
                          "placement": placement.__dict__ if placement else None,
                          "autostart": is_autostart()}, ensure_ascii=False))
        return
    if args.install:
        install_autostart()
    if not native.single_instance():
        return
    root = tk.Tk()
    root.withdraw()
    Meter(root)
    root.mainloop()


def main():
    try:
        run()
    except Exception:
        import traceback
        with open(os.path.join(APP_DIR, "meter_error.log"), "w", encoding="utf-8") as log:
            log.write(traceback.format_exc()[-8192:])
        raise
