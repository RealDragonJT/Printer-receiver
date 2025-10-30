#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PROJECT_DIR}/venv/bin/python"
RUN_SCRIPT="${PROJECT_DIR}/run_pi_server.py"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST_ID="dev.dragnai.discord-printer"
PLIST_FILE="${LAUNCH_AGENTS}/${PLIST_ID}.plist"

mkdir -p "$LAUNCH_AGENTS"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${PLIST_ID}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>${RUN_SCRIPT}</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>WorkingDirectory</key><string>${PROJECT_DIR}</string>
  <key>StandardOutPath</key><string>${PROJECT_DIR}/receiver.out.log</string>
  <key>StandardErrorPath</key><string>${PROJECT_DIR}/receiver.err.log</string>
</dict>
 </plist>
EOF

launchctl unload "$PLIST_FILE" >/dev/null 2>&1 || true
launchctl load "$PLIST_FILE"
launchctl start "$PLIST_ID" || true

echo "Installed and started launchd agent: ${PLIST_ID}"
echo "View logs at ${PROJECT_DIR}/receiver.*.log"



