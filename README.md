# ProPresenter Notes Controller for Mac

A local web app for a Mac Studio that controls ProPresenter through the ProPresenter public REST API. It does **not** require Docker or npm packages. It now runs as a Flask application.

## What it does

- Shows a selector for presentations found in ProPresenter libraries.
- Triggers the selected presentation at slide 1 when selected.
- Provides Previous and Next buttons, including a thumb-friendly sticky mobile control bar.
- Supports keyboard navigation with Arrow Left, Arrow Right, Page Up, and Page Down, plus swipe navigation on touch screens.
- Shows slide notes when your ProPresenter API exposes notes in the slide/status/presentation payloads.
- Adapts to phones and tablets with larger tap targets, responsive slide thumbnails, and simplified small-screen layout.
- Runs locally on the Mac Studio as a Flask web application.
- Can install as a macOS system service using `launchd`.

## Requirements

- macOS on the Mac Studio.
- Python 3 available as `python3`.
- ProPresenter running with its public/network API enabled.
- Administrator access for the system service installer.

Docker, Node, and npm are not needed for the macOS service path. The startup scripts create a local Python virtual environment and install the Python dependencies from `requirements.txt`. Docker is also available as an optional deployment path.

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
  "poll_timeout_ms": 2500,
  "ui_pin": ""
}
```

Use `127.0.0.1` when ProPresenter is running on the same Mac Studio.

Use the ProPresenter computer's LAN IP address when ProPresenter is running on another computer, for example:

```json
"propresenter_host": "192.168.1.50"
```


### Restrict UI access with a PIN

Set `ui_pin` in `config.json` to require a PIN before anyone can open the controller UI or call its API endpoints:

```json
"ui_pin": "1234"
```

Leave `ui_pin` empty to disable the lock screen. You can also set the `UI_PIN` environment variable, which takes precedence over `config.json`. After changing the PIN, restart the app or service.

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

## Run tests

Run the Python unit test suite locally with:

```bash
python -m unittest discover -s tests -v
```

Run the same test suite in Docker with the test build target used by CI:

```bash
docker build --target test -t propresenter-notes:test .
docker run --rm propresenter-notes:test
```

The test suite includes a local mock ProPresenter API server backed by the captured OpenAPI example payloads in `tests/propresenter_openapi_examples.json`. Those integration tests exercise the real `ProPresenterClient` over HTTP for `/version`, `/v1/libraries`, and `/v1/library/{library_id}` without requiring a running ProPresenter instance. As more Swagger examples are collected, add them to that fixture and extend `tests/mock_propresenter_api.py` so Docker and CI continue validating against the documented API contract.

To capture examples from a real ProPresenter system for review, run:

```bash
python scripts/capture_propresenter_examples.py --base-url http://127.0.0.1:1025 --output propresenter_examples_capture.json
```

The capture script reads `/version`, `/v1/libraries`, `/v1/library/{library_id}` using UUID/name/index forms, selected presentation details, the first slide thumbnail, and slide-status endpoints. It intentionally skips trigger endpoints because they mutate the live ProPresenter state. Review the generated file for sensitive presentation text before sharing it or copying examples into `tests/propresenter_openapi_examples.json`.

GitHub Actions runs the Dockerized test suite on pushes to `main`, pull requests, and manual workflow dispatches.

## Run with Docker

Docker is an optional deployment path; the macOS service scripts above remain supported. Build the image from this folder with:

```bash
docker build -t propresenter-notes .
```

When ProPresenter is running on the same Mac as Docker, run the container with `PROPRESENTER_HOST=host.docker.internal` and set `PROPRESENTER_PORT` to the API port shown in **Settings > Network**:

```bash
docker run --rm -p 3000:3000 -e APP_HOST=0.0.0.0 -e PROPRESENTER_HOST=host.docker.internal -e PROPRESENTER_PORT=<port> propresenter-notes
```

Then open the web UI at:

```text
http://127.0.0.1:3000
```

When ProPresenter is running on another machine, use that machine's LAN IP address for `PROPRESENTER_HOST` and set `PROPRESENTER_PORT` to its API port. For example:

```bash
docker run --rm -p 3000:3000 -e APP_HOST=0.0.0.0 -e PROPRESENTER_HOST=192.168.1.50 -e PROPRESENTER_PORT=<port> propresenter-notes
```

Inside Docker, `127.0.0.1` refers to the container itself, not the Mac host. Use `host.docker.internal` for ProPresenter on the same Mac, or the ProPresenter machine's LAN IP address for ProPresenter on another computer.

If you prefer Docker Compose, you can also run:

```bash
docker compose up --build
```

The compose file exposes the web UI on `http://127.0.0.1:3000`.

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
