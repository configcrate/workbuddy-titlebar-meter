#!/bin/zsh
set -eu
ROOT="${0:A:h:h}"
DIST="$ROOT/dist"
STAGE="$DIST/workbuddy-titlebar-meter-macos"
APP="$STAGE/WorkBuddy Titlebar Meter.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
xcrun swiftc -O -framework Cocoa -o "$APP/Contents/MacOS/meter" "$ROOT/macos/Meter.swift"
cp "$ROOT/macos/Info.plist" "$APP/Contents/Info.plist"
cp "$ROOT/wb_credits_helper.cjs" "$APP/Contents/Resources/wb_credits_helper.cjs"
cp "$ROOT/macos/Start-Meter.command" "$STAGE/Start-Meter.command"
chmod 755 "$STAGE/Start-Meter.command"
"$APP/Contents/MacOS/meter" --self-test
/usr/bin/ditto --norsrc -c -k --keepParent "$STAGE" "$DIST/workbuddy-titlebar-meter-macos-arm64.zip"
print "已生成 $DIST/workbuddy-titlebar-meter-macos-arm64.zip"
