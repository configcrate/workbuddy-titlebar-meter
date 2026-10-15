"""Pure, testable layout and data rules for the WorkBuddy titlebar meter."""
import math
import os
from dataclasses import dataclass

PALETTES = ("#40c48b", "#5f91ff", "#ad75ff")
INTERVALS = (60_000, 180_000, 300_000, 600_000, 1_800_000)


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    width: int
    height: int
    scale: float


def titlebar_layout(bounds, dpi=96):
    """Physical coordinates; preserve menus on the left and caption buttons on the right."""
    left, top, right, bottom = bounds
    scale = max(0.75, min(4.0, dpi / 96))
    px = lambda n: round(n * scale)
    available = right - left - px(340) - px(158)
    if bottom - top < px(160) or available < px(170):
        return None
    width = min(px(220), available)
    return Placement(right - px(158) - width, top + px(2), width, px(28), scale)


def is_main_candidate(path, class_name, bounds, owned=False, tool_window=False):
    # A browser page mentioning WorkBuddy is not WorkBuddy. Pets/tool windows are not hosts.
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    basename = path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return (basename == "workbuddy.exe" and class_name.startswith("Chrome_WidgetWin_")
            and not owned and not tool_window and width >= 480 and height >= 240)


def sanitize_config(raw):
    raw = raw if isinstance(raw, dict) else {}
    interval = raw.get("intervalMs", 300_000)
    if not isinstance(interval, int) or interval not in INTERVALS:
        interval = 300_000
    palette = raw.get("palette", 0)
    if not isinstance(palette, int):
        palette = 0
    variant = raw.get("variant", "auto")
    return {"version": 2, "intervalMs": interval, "palette": palette % len(PALETTES),
            "variant": variant if variant in ("auto", "cn", "ai") else "auto"}


def normalize_snapshot(raw):
    """Cache only display values, never account identifiers, nicknames or token metadata."""
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        return None
    try:
        remain, total, updated = (float(raw[key]) for key in ("remain", "total", "updatedAt"))
    except (ValueError, TypeError, KeyError):
        return None
    if not all(math.isfinite(v) for v in (remain, total, updated)):
        return None
    if remain < 0 or total < 0 or updated <= 0:
        return None
    percent = min(100.0, max(0.0, remain / total * 100)) if total > 0 else None
    return {"ok": True, "remain": remain, "total": total, "percent": percent,
            "updatedAt": updated, "plan": str(raw.get("plan") or "")[:80]}


def fmt_num(value):
    number = float(value)
    return f"{number:,.0f}" if number.is_integer() else f"{number:,.2f}"


def compact_num(value):
    value = float(value)
    if value >= 100_000_000:
        return f"{value / 100_000_000:.2f}亿"
    if value >= 100_000:
        return f"{value / 10_000:.2f}万"
    return fmt_num(value)


def meter_text(data, phase, now_ms, interval_ms):
    if not data:
        return "积分暂不可用" if phase == "error" else "正在读取积分…"
    old = phase == "error" or now_ms - data["updatedAt"] > max(120_000, 2 * interval_ms)
    if old:
        return f"上次积分 {compact_num(data['remain'])} · 待更新"
    pct = data["percent"]
    suffix = f" · {pct:.0f}%" if pct is not None else ""
    return f"剩余积分 {compact_num(data['remain'])}{suffix}"


def meter_color(data, phase, now_ms, interval_ms, palette):
    if not data or phase == "error" or now_ms - data["updatedAt"] > max(120_000, 2 * interval_ms):
        return "#777e8a"
    percent = data["percent"]
    if percent is None:
        return "#777e8a"
    return "#e5534b" if percent <= 10 else "#e8a33d" if percent <= 20 else PALETTES[palette]


def autostart_command(python_exe, script):
    import subprocess
    return subprocess.list2cmdline([os.path.abspath(python_exe), os.path.abspath(script)])
