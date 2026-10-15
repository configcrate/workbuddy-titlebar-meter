import AppKit
import CoreGraphics
import Darwin
import Foundation

// A separate, unsigned, agent-only overlay. Never changes or injects into WorkBuddy.
enum Variant: String {
    case cn, ai

    var bundleID: String {
        self == .cn ? "com.tencent.workbuddy.mac" : "com.workbuddy.workbuddy-ai"
    }
    var label: String { self == .cn ? "国内版" : "国际版" }
    var appName: String { self == .cn ? "WorkBuddy.app" : "WorkBuddy AI.app" }
    var agentID: String { "com.configcrate.workbuddy-titlebar-meter.\(rawValue)" }
}

struct Placement: Equatable {
    let frame: CGRect // Quartz global coordinates: origin at the main display's upper left.

    // Measured on 2026-10-15 from real screenshots (window-relative points):
    //   WorkBuddy 5.8.2 (cn): 3 title-bar buttons, leftmost starts 111pt from the right edge
    //   WorkBuddy AI 5.7.6 (ai): 5 title-bar buttons, leftmost starts 179pt from the right edge
    // The meter keeps an 18pt gap in front of that button, and its vertical centre
    // matches the title row (which sits ~30pt below the window's top edge).
    static let buttonGap: CGFloat = 18
    static let sidebarReserve: CGFloat = 300
    static let height: CGFloat = 26

    static func buttonReserve(for variant: Variant) -> CGFloat {
        (variant == .cn ? 111 : 179) + buttonGap
    }

    // Window-relative centre of the title row (traffic lights, icons and title
    // all sit on it). The two builds differ by 4pt.
    static func titleRowCentre(for variant: Variant) -> CGFloat {
        variant == .cn ? 31.5 : 27.5
    }

    static func forWindow(_ window: CGRect, variant: Variant) -> Placement? {
        // macOS traffic lights are on the LEFT, unlike Windows caption buttons.
        guard window.width >= 640, window.height >= 240 else { return nil }
        let reserve = buttonReserve(for: variant)
        let available = window.width - sidebarReserve - reserve
        guard available >= 160 else { return nil }
        let width = min(210, available)
        return Placement(frame: CGRect(x: window.maxX - reserve - width,
                                       y: window.minY + titleRowCentre(for: variant) - height / 2,
                                       width: width, height: height))
    }
}

struct Snapshot {
    let remain: Double
    let total: Double
    let plan: String
    let updatedAt: Date

    var percent: Double? { total > 0 ? min(100, max(0, remain / total * 100)) : nil }

    init?(json: [String: Any]) {
        guard json["ok"] as? Bool == true,
              let remain = json["remain"] as? Double, remain.isFinite, remain >= 0,
              let total = json["total"] as? Double, total.isFinite, total >= 0,
              let time = json["updatedAt"] as? Double, time.isFinite, time > 0 else { return nil }
        self.remain = remain
        self.total = total
        self.plan = String((json["plan"] as? String ?? "").prefix(80))
        self.updatedAt = Date(timeIntervalSince1970: time / 1000)
    }
}

func compactNumber(_ number: Double) -> String {
    if number >= 100_000_000 { return String(format: "%.2f亿", number / 100_000_000) }
    if number >= 100_000 { return String(format: "%.2f万", number / 10_000) }
    return number.rounded() == number ? String(format: "%.0f", number) : String(format: "%.2f", number)
}

let colors: [NSColor] = [
    NSColor(srgbRed: 0.25, green: 0.77, blue: 0.55, alpha: 1),
    NSColor(srgbRed: 0.37, green: 0.57, blue: 1.0, alpha: 1),
    NSColor(srgbRed: 0.68, green: 0.46, blue: 1.0, alpha: 1)
]

final class MeterView: NSView {
    weak var controller: MeterController?
    var label = "正在读取积分…" { didSet { needsDisplay = true } }
    var percent: Double? { didSet { needsDisplay = true } }
    var tint = colors[0] { didSet { needsDisplay = true } }
    var palette = 0 { didSet { needsDisplay = true } }

    override var isFlipped: Bool { true }

    override func draw(_ dirtyRect: NSRect) {
        // #141414 is the measured WorkBuddy title-bar colour, so the panel blends in.
        NSColor(srgbRed: 20 / 255.0, green: 20 / 255.0, blue: 20 / 255.0, alpha: 1).setFill()
        NSBezierPath(roundedRect: bounds, xRadius: 5, yRadius: 5).fill()
        let font = NSFont.systemFont(ofSize: 11, weight: .medium)
        let textRect = NSRect(x: 8, y: 4, width: bounds.width - 31, height: 17)
        NSGraphicsContext.saveGraphicsState()
        NSBezierPath(rect: textRect).addClip()
        (label as NSString).draw(in: textRect, withAttributes: [
            .font: font, .foregroundColor: NSColor(srgbRed: 0.84, green: 0.86, blue: 0.88, alpha: 1)
        ])
        NSGraphicsContext.restoreGraphicsState()
        NSColor(srgbRed: 0.24, green: 0.25, blue: 0.27, alpha: 1).setFill()
        NSBezierPath(rect: NSRect(x: 8, y: 22, width: bounds.width - 36, height: 2)).fill()
        if let percent {
            tint.setFill()
            NSBezierPath(rect: NSRect(x: 8, y: 22, width: (bounds.width - 36) * percent / 100, height: 2)).fill()
        }
        colors[palette].setFill()
        NSBezierPath(roundedRect: NSRect(x: bounds.width - 18, y: 9, width: 8, height: 8),
                     xRadius: 2, yRadius: 2).fill()
    }

    override func mouseUp(with event: NSEvent) {
        if convert(event.locationInWindow, from: nil).x >= bounds.width - 26 {
            controller?.cyclePalette()
        }
    }
    override func rightMouseDown(with event: NSEvent) { controller?.showMenu(event: event, in: self) }
}

final class MeterController: NSObject {
    let variant: Variant
    let panel: NSPanel
    let view: MeterView
    let helper: URL
    var timer: Timer?
    var snapshot: Snapshot?
    var phase = "loading"
    var palette = 0
    var interval: TimeInterval = 300
    // Keep the meter on screen while another app is in front (default), matching
    // the requested behaviour; the menu can switch back to front-most only.
    var alwaysVisible = UserDefaults.standard.object(forKey: "alwaysVisible") as? Bool ?? true
    var nextRefresh = Date.distantPast
    var process: Process?
    var generation = 0
    var hostPID: pid_t = 0
    var lastPlacement: Placement?
    let lockFD: Int32

    init(variant: Variant, helper: URL, lockFD: Int32) {
        self.variant = variant
        self.helper = helper
        self.lockFD = lockFD
        view = MeterView(frame: NSRect(x: 0, y: 0, width: 210, height: 26))
        panel = NSPanel(contentRect: view.bounds, styleMask: [.borderless, .nonactivatingPanel],
                        backing: .buffered, defer: false)
        super.init()
        view.controller = self
        panel.contentView = view
        panel.level = .floating
        // Do not hide when this helper app is deactivated; the panel is placed on
        // whichever Space currently shows the host window.
        panel.collectionBehavior = [.ignoresCycle]
        panel.hidesOnDeactivate = false
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.isReleasedWhenClosed = false
        panel.orderOut(nil)
    }

    func start() {
        timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] _ in self?.tick() }
        tick()
    }

    // Quartz reports windows front-to-back across all apps. Use the host app's
    // frontmost window, and refuse to attach when that window is a dialog.
    func hostWindow(for pid: pid_t) -> CGRect? {
        let entries = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID)
        let windows = entries as? [[String: Any]] ?? []
        for entry in windows {
            guard (entry[kCGWindowOwnerPID as String] as? Int) == Int(pid),
                  (entry[kCGWindowLayer as String] as? Int) == 0,
                  let bounds = entry[kCGWindowBounds as String] as? [String: Any],
                  let x = bounds["X"] as? Double, let y = bounds["Y"] as? Double,
                  let width = bounds["Width"] as? Double, let height = bounds["Height"] as? Double else { continue }
            let rect = CGRect(x: x, y: y, width: width, height: height)
            return Placement.forWindow(rect, variant: variant) == nil ? nil : rect
        }
        return nil
    }

    func isFullScreen(_ rect: CGRect) -> Bool {
        for display in NSScreen.screens {
            guard let number = display.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber else { continue }
            let screen = CGDisplayBounds(CGDirectDisplayID(number.uint32Value))
            if abs(rect.minX - screen.minX) < 3 && abs(rect.minY - screen.minY) < 3 &&
               abs(rect.width - screen.width) < 5 && abs(rect.height - screen.height) < 5 { return true }
        }
        return false
    }

    func hide() {
        if panel.isVisible { panel.orderOut(nil) }
        lastPlacement = nil
    }

    func tick() {
        let running = NSRunningApplication.runningApplications(withBundleIdentifier: variant.bundleID)
            .filter { $0.bundleURL?.lastPathComponent == variant.appName }
        // Switching apps is not a host exit: preserve the refresh timer.
        if hostPID != 0 && !running.contains(where: { $0.processIdentifier == hostPID }) {
            generation += 1
            if process?.isRunning == true { process?.terminate() }
            hostPID = 0
        }
        let frontmost = NSWorkspace.shared.frontmostApplication
        let target = running.first { $0.processIdentifier == frontmost?.processIdentifier } ?? running.first
        // The meter stays attached while another app is in front, so the host
        // window only has to exist on screen — not be the active window.
        guard let app = target, alwaysVisible || app.isActive, !app.isHidden,
              let rect = hostWindow(for: app.processIdentifier),
              !isFullScreen(rect), let placement = Placement.forWindow(rect, variant: variant) else {
            hide()
            return
        }
        if hostPID != app.processIdentifier {
            generation += 1
            if process?.isRunning == true { process?.terminate() }
            hostPID = app.processIdentifier
            nextRefresh = .distantPast
        }
        if placement != lastPlacement {
            let mainTop = NSScreen.screens.first?.frame.maxY ?? CGDisplayBounds(CGMainDisplayID()).height
            let frame = placement.frame
            panel.setFrame(NSRect(x: frame.minX, y: mainTop - frame.maxY,
                                  width: frame.width, height: frame.height), display: true)
            lastPlacement = placement
        }
        if !panel.isVisible { panel.orderFrontRegardless() }
        if process == nil && Date() >= nextRefresh { refresh(executable: app.bundleURL!) }
        updateView()
    }

    func updateView() {
        let old = snapshot.map { Date().timeIntervalSince($0.updatedAt) > max(120, 2 * interval) } ?? false
        let stale = phase == "error" || old
        if let data = snapshot {
            let suffix = data.percent.map { String(format: " · %.0f%%", $0) } ?? ""
            view.label = stale ? "上次积分 \(compactNumber(data.remain)) · 待更新" : "剩余积分 \(compactNumber(data.remain))\(suffix)"
            view.percent = data.percent
            view.tint = stale ? .gray : (data.percent ?? 100) <= 10 ? .systemRed : (data.percent ?? 100) <= 20 ? .systemOrange : colors[palette]
        } else {
            view.label = phase == "error" ? "积分暂不可用 · 待更新" : "正在读取积分…"
            view.percent = nil
            view.tint = .gray
        }
        view.palette = palette
    }

    func refresh(executable bundle: URL? = nil) {
        guard process == nil, hostPID != 0 else { return }
        let url = bundle ?? NSRunningApplication.runningApplications(withBundleIdentifier: variant.bundleID)
            .first(where: { $0.processIdentifier == hostPID })?.bundleURL
        guard let url, url.lastPathComponent == variant.appName else { return }
        let executable = url.appendingPathComponent("Contents/MacOS/Electron")
        guard FileManager.default.isExecutableFile(atPath: executable.path) else { return }
        let child = Process()
        child.executableURL = executable
        child.arguments = [helper.path, "--variant", variant.rawValue]
        child.environment = ProcessInfo.processInfo.environment.merging(["ELECTRON_RUN_AS_NODE": "1"]) { _, new in new }
        let output = Pipe()
        child.standardOutput = output
        child.standardError = FileHandle.nullDevice // never print client diagnostics or credentials
        let currentGeneration = generation
        process = child
        phase = snapshot == nil ? "loading" : "refreshing"
        nextRefresh = Date().addingTimeInterval(interval)
        do {
            try child.run()
        } catch {
            process = nil
            phase = "error"
            return
        }
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let bytes = output.fileHandleForReading.readDataToEndOfFile()
            child.waitUntilExit()
            let result = (try? JSONSerialization.jsonObject(with: bytes)) as? [String: Any]
            DispatchQueue.main.async {
                guard let self else { return }
                if self.process === child { self.process = nil }
                guard self.generation == currentGeneration, self.hostPID != 0 else { return }
                if let result, let data = Snapshot(json: result) {
                    self.snapshot = data
                    self.phase = "ok"
                } else {
                    self.phase = "error"
                    self.nextRefresh = Date().addingTimeInterval(min(60, self.interval))
                }
                self.updateView()
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 45) { [weak self] in
            guard let self, self.process === child, child.isRunning else { return }
            child.terminate() // only terminate our helper, never the WorkBuddy UI process
        }
    }

    func cyclePalette() {
        palette = (palette + 1) % colors.count
        updateView()
    }

    func agentURL() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents/\(variant.agentID).plist")
    }

    func runLaunchctl(_ arguments: [String]) -> Bool {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        task.arguments = arguments
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus == 0
        } catch { return false }
    }

    func hasAutostart() -> Bool {
        let url = agentURL()
        guard let data = try? Data(contentsOf: url),
              let plist = try? PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any],
              let args = plist["ProgramArguments"] as? [String] else { return false }
        return args == [Bundle.main.executablePath ?? "", "--variant", variant.rawValue]
    }

    func toggleAutostart() {
        let url = agentURL()
        let name = "gui/\(getuid())"
        if hasAutostart() {
            // File removal prevents future logins even if launchd has already unloaded it.
            _ = runLaunchctl(["bootout", name, url.path])
            do { try FileManager.default.removeItem(at: url) }
            catch { NSLog("无法关闭登录自启：%@", error.localizedDescription) }
        } else if !FileManager.default.fileExists(atPath: url.path) {
            let plist: [String: Any] = ["Label": variant.agentID,
                                        "ProgramArguments": [Bundle.main.executablePath ?? "", "--variant", variant.rawValue],
                                        "RunAtLoad": true, "KeepAlive": false]
            do {
                let folder = url.deletingLastPathComponent()
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                let data = try PropertyListSerialization.data(fromPropertyList: plist, format: .xml, options: 0)
                try data.write(to: url, options: .atomic)
                if !runLaunchctl(["bootstrap", name, url.path]) {
                    NSLog("已写入登录自启配置，但 launchctl 加载失败；下次登录时会再尝试启动")
                }
            } catch { NSLog("无法设置登录自启：%@", error.localizedDescription) }
        }
    }

    func showMenu(event: NSEvent, in view: NSView) {
        let menu = NSMenu()
        menu.addItem(withTitle: "\(variant.label) · 立即刷新", action: #selector(refreshAction), keyEquivalent: "").target = self
        if let data = snapshot {
            let age = DateFormatter()
            age.dateFormat = "MM-dd HH:mm:ss"
            let percent = data.percent.map { String(format: "%.1f%%", $0) } ?? "未提供总额度"
            let detail = "积分 \(compactNumber(data.remain)) / \(compactNumber(data.total)) · \(percent) · \(age.string(from: data.updatedAt))"
            menu.addItem(withTitle: detail, action: nil, keyEquivalent: "")
            if !data.plan.isEmpty { menu.addItem(withTitle: "套餐：\(data.plan)", action: nil, keyEquivalent: "") }
        }
        menu.addItem(withTitle: "切换颜色", action: #selector(colorAction), keyEquivalent: "").target = self
        let submenu = NSMenu()
        for minutes in [1, 3, 5, 10, 30] {
            let item = NSMenuItem(title: "\(minutes) 分钟", action: #selector(intervalAction(_:)), keyEquivalent: "")
            item.target = self
            item.tag = minutes
            item.state = interval == TimeInterval(minutes * 60) ? .on : .off
            submenu.addItem(item)
        }
        let intervalItem = NSMenuItem(title: "刷新间隔", action: nil, keyEquivalent: "")
        intervalItem.submenu = submenu
        menu.addItem(intervalItem)
        let always = NSMenuItem(title: "切换到其他软件时仍显示",
                                action: #selector(alwaysVisibleAction), keyEquivalent: "")
        always.target = self
        always.state = alwaysVisible ? .on : .off
        menu.addItem(always)
        menu.addItem(.separator())
        menu.addItem(withTitle: hasAutostart() ? "关闭登录自启" : "开启登录自启",
                     action: #selector(autostartAction), keyEquivalent: "").target = self
        menu.addItem(withTitle: "退出\(variant.label)积分条", action: #selector(exitAction), keyEquivalent: "").target = self
        NSMenu.popUpContextMenu(menu, with: event, for: view)
    }

    @objc func refreshAction() { nextRefresh = .distantPast; refresh() }
    @objc func colorAction() { cyclePalette() }
    @objc func autostartAction() { toggleAutostart() }
    @objc func alwaysVisibleAction() {
        alwaysVisible.toggle()
        UserDefaults.standard.set(alwaysVisible, forKey: "alwaysVisible")
    }
    @objc func exitAction() { process?.terminate(); NSApp.terminate(nil) }
    @objc func intervalAction(_ item: NSMenuItem) { interval = TimeInterval(item.tag * 60); nextRefresh = Date().addingTimeInterval(interval) }
}

func main() {
    let args = CommandLine.arguments
    if args.contains("--self-test") {
        precondition(Placement.forWindow(CGRect(x: 0, y: 0, width: 969, height: 700), variant: .cn)?.frame.minX == 630)
        precondition(Placement.forWindow(CGRect(x: 0, y: 0, width: 500, height: 700), variant: .cn) == nil)
        precondition(Variant.cn.bundleID != Variant.ai.bundleID)
        precondition(Variant.cn.agentID != Variant.ai.agentID)
        precondition(Placement.forWindow(CGRect(x: -1200, y: -500, width: 1100, height: 700), variant: .cn)?.frame.minX == -439)
        // Real measured windows: the meter must end 18pt before the leftmost
        // title-bar button (cn window 948..1920 with buttons at 1809; ai window
        // 0..947 with buttons at 768), and sit on the title row.
        let cn = Placement.forWindow(CGRect(x: 948, y: 30, width: 972, height: 1014), variant: .cn)!
        precondition(cn.frame.maxX == 1791 && cn.frame.minY == 48.5)
        let ai = Placement.forWindow(CGRect(x: 0, y: 30, width: 947, height: 1014), variant: .ai)!
        precondition(ai.frame.maxX == 750 && ai.frame.minY == 44.5)
        precondition(Snapshot(json: ["ok": true, "remain": 2.0, "total": 0.0, "updatedAt": 1000.0])?.percent == nil)
        precondition(Snapshot(json: ["ok": true, "remain": -1.0, "total": 2.0, "updatedAt": 1000.0]) == nil)
        print("macOS layout, variants and snapshot: OK")
        return
    }
    guard let index = args.firstIndex(of: "--variant"), args.indices.contains(index + 1),
          let variant = Variant(rawValue: args[index + 1]) else {
        fputs("用法: meter --variant cn|ai [--diagnose]\n", stderr)
        exit(2)
    }
    if args.contains("--diagnose") {
        let clients = NSRunningApplication.runningApplications(withBundleIdentifier: variant.bundleID)
        print("\(variant.label): running=\(!clients.isEmpty) bundle=\(variant.bundleID)")
        return
    }
    let lock = (NSTemporaryDirectory() as NSString).appendingPathComponent("configcrate.titlebar-meter.\(getuid()).\(variant.rawValue).lock")
    let isConfigCommand = args.contains("--install-autostart") || args.contains("--uninstall-autostart")
    let fd = Darwin.open(lock, O_CREAT | O_RDWR, 0o600)
    guard fd >= 0 else { return }
    if !isConfigCommand && flock(fd, LOCK_EX | LOCK_NB) != 0 { return }
    let helper = Bundle.main.resourceURL?.appendingPathComponent("wb_credits_helper.cjs")
    guard let helper, FileManager.default.fileExists(atPath: helper.path) else {
        fputs("缺少取数助手，请重新构建 macOS 包\n", stderr)
        exit(1)
    }
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let controller = MeterController(variant: variant, helper: helper, lockFD: fd)
    if args.contains("--install-autostart") {
        if !controller.hasAutostart() { controller.toggleAutostart() }
        print("\(variant.label)登录自启：\(controller.hasAutostart() ? "已启用" : "未启用")")
        return
    }
    if args.contains("--uninstall-autostart") {
        if controller.hasAutostart() { controller.toggleAutostart() }
        print("\(variant.label)登录自启：\(controller.hasAutostart() ? "仍启用" : "已关闭")")
        return
    }
    controller.start()
    // Timer/view closures intentionally hold only weak references; retain the
    // controller explicitly for the entire AppKit event loop.
    withExtendedLifetime(controller) { app.run() }
}

main()
