#!/bin/zsh
set -e

LABEL="org.propresenter.notescontroller"
TARGET="/Library/Application Support/ProPresenterNotesController"
PLIST="/Library/LaunchDaemons/${LABEL}.plist"
LOG_DIR="/Library/Logs/ProPresenterNotesController"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required before installing the service."
  echo "Install Python 3 from python.org or with Homebrew, then run this installer again."
  read "?Press Return to close."
  exit 1
fi

echo "Installing ProPresenter Notes Controller as a system service..."
echo "You may be prompted for your Mac administrator password."

sudo mkdir -p "$TARGET" "$LOG_DIR"

if [ -f "$TARGET/config.json" ]; then
  sudo cp "$TARGET/config.json" /tmp/propresenter-notes-controller-config.json
fi

sudo rsync -a --delete \
  --exclude '.DS_Store' \
  --exclude 'Install Service.command' \
  --exclude 'Uninstall Service.command' \
  --exclude 'Service Status.command' \
  "$SRC_DIR/" "$TARGET/"

if [ -f /tmp/propresenter-notes-controller-config.json ]; then
  sudo mv /tmp/propresenter-notes-controller-config.json "$TARGET/config.json"
fi

sudo chmod +x "$TARGET/run-service.sh" "$TARGET/server.py"
sudo chown -R root:wheel "$TARGET" "$LOG_DIR"
sudo chmod 755 "$TARGET" "$LOG_DIR"

if sudo launchctl print system/$LABEL >/dev/null 2>&1; then
  sudo launchctl bootout system "$PLIST" >/dev/null 2>&1 || true
fi

sudo tee "$PLIST" >/dev/null <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>${TARGET}/run-service.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>${TARGET}</string>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/out.log</string>

  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/err.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
</dict>
</plist>
PLIST_EOF

sudo chown root:wheel "$PLIST"
sudo chmod 644 "$PLIST"
sudo launchctl bootstrap system "$PLIST"
sudo launchctl enable system/$LABEL
sudo launchctl kickstart -k system/$LABEL

echo ""
echo "Installed and started."
echo "Open http://127.0.0.1:3000 on this Mac."
echo ""
echo "Config file: $TARGET/config.json"
echo "Logs: $LOG_DIR/out.log and $LOG_DIR/err.log"
echo ""
read "?Press Return to close."
