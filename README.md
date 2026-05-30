# ProPresenter Notes Controller for Mac

A local web app for a Mac Studio that controls ProPresenter through the ProPresenter public REST API. It does **not** require Docker or npm packages. It now runs as a Flask application.

## What it does

- Shows a selector for presentations found in ProPresenter libraries.
- Triggers the selected presentation at slide 1 when selected.
- Provides Previous and Next buttons.
- Supports keyboard navigation with Arrow Left, Arrow Right, Page Up, and Page Down.
- Shows slide notes when your ProPresenter API exposes notes in the slide/status/presentation payloads.
- Runs locally on the Mac Studio as a Flask web application.
- Can install as a macOS system service using `launchd`.

## Requirements

- macOS on the Mac Studio.
- Python 3 available as `python3`.
- ProPresenter running with its public/network API enabled.
- Administrator access for the system service installer.

No Docker, Node, or npm installation is needed. The startup scripts create a local Python virtual environment and install the Python dependencies from `requirements.txt`.

## Configure ProPresenter

In ProPresenter, open **Settings > Network** and enable the public/API network controls. Note the API port shown there. Common ProPresenter API ports include `1025`, but you should use the value shown on your machine.

## Configure this app

Before installing the service, edit `config.json` in this folder:

```json
{
  "app_host": "127.0.0.1",
  "app_port": 3000,
  "propresenter_scheme": "http",
  "propresenter_host": "127.0.0.1",
  "propresenter_port": 1025,
  "poll_timeout_ms": 2500
}
```

Use `127.0.0.1` when ProPresenter is running on the same Mac Studio.

Use the ProPresenter computer's LAN IP address when ProPresenter is running on another computer, for example:

```json
"propresenter_host": "192.168.1.50"
```

## Install as a macOS system service

Double-click:

```text
Install Service.command
```

The installer will ask for your Mac administrator password because it writes a LaunchDaemon to:

```text
/Library/LaunchDaemons/org.propresenter.notescontroller.plist
```

It installs the app to:

```text
/Library/Application Support/ProPresenterNotesController
```

It writes logs to:

```text
/Library/Logs/ProPresenterNotesController/out.log
/Library/Logs/ProPresenterNotesController/err.log
```

After installation, open:

```text
http://127.0.0.1:3000
```

The service starts at boot and restarts automatically if it exits.

## Changing config after service install

Edit this installed config file:

```text
/Library/Application Support/ProPresenterNotesController/config.json
```

Then restart the service:

```bash
sudo launchctl kickstart -k system/org.propresenter.notescontroller
```

Or rerun `Install Service.command`; it preserves the installed config file.

## Check service status

Double-click:

```text
Service Status.command
```

Or run:

```bash
sudo launchctl print system/org.propresenter.notescontroller
```

## Uninstall service

Double-click:

```text
Uninstall Service.command
```

This removes the LaunchDaemon and stops the service. It intentionally leaves the installed app folder and logs in place so your config is not deleted. The uninstall script prints the command to remove those files too.

## Manual testing without installing the service

Double-click:

```text
Start.command
```

Then open:

```text
http://127.0.0.1:3000
```

## Troubleshooting

### macOS says the command file cannot be opened

Control-click the `.command` file and choose **Open**. You may need to approve it in **System Settings > Privacy & Security**.

### Port 3000 is already in use

Change `app_port` in `config.json`, then restart the app or service.

### The UI loads but ProPresenter does not respond

- Confirm ProPresenter is open.
- Confirm the ProPresenter public/network API is enabled.
- Confirm `propresenter_host` and `propresenter_port` match the ProPresenter machine.
- Confirm both devices are on the same network if ProPresenter is not on the same Mac.

### Notes are blank

Different ProPresenter versions expose note text differently through the public API. This app scans common fields such as `notes`, `slideNotes`, `speakerNotes`, `presenterNotes`, and `stageNotes`. If your version exposes notes under a different field or endpoint, update the parsing helpers in `propresenter_notes/services.py`.
