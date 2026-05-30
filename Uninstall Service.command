#!/bin/zsh
set -e

LABEL="org.propresenter.notescontroller"
TARGET="/Library/Application Support/ProPresenterNotesController"
PLIST="/Library/LaunchDaemons/${LABEL}.plist"
LOG_DIR="/Library/Logs/ProPresenterNotesController"

echo "Uninstalling ProPresenter Notes Controller system service..."
echo "You may be prompted for your Mac administrator password."

if sudo launchctl print system/$LABEL >/dev/null 2>&1; then
  sudo launchctl bootout system "$PLIST" >/dev/null 2>&1 || true
fi

sudo rm -f "$PLIST"

echo ""
echo "Service removed."
echo "The installed app folder was left in place so your config is preserved:"
echo "$TARGET"
echo ""
echo "To remove app files and logs too, run:"
echo "sudo rm -rf '$TARGET' '$LOG_DIR'"
echo ""
read "?Press Return to close."
