#!/bin/zsh
LABEL="org.propresenter.notescontroller"
LOG_DIR="/Library/Logs/ProPresenterNotesController"

echo "Service status for $LABEL"
echo ""
sudo launchctl print system/$LABEL 2>/dev/null || echo "Service is not loaded."
echo ""
echo "Recent error log:"
if [ -f "$LOG_DIR/err.log" ]; then
  tail -n 40 "$LOG_DIR/err.log"
else
  echo "No error log found."
fi

echo ""
read "?Press Return to close."
