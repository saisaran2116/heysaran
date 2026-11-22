# Hey Baby

Hey Baby is a local desktop voice assistant with a floating panel and a menu bar
or system tray icon. It recognizes **Hey Baby** and voice commands on the laptop.
After setup, voice recognition, spoken feedback, and built-in actions work
without internet. Web searches and optional Sarvam chat use the internet.

## Install and run

Install a standalone Python 3.12 (3.10–3.14 are accepted; use a build that your
platform's Qt and Vosk packages support). Don't copy the old `.venv` from another
laptop. Setup creates `.hey-baby-venv` and downloads the 36 MB speech model once.

| Platform | Setup | Start |
| --- | --- | --- |
| macOS | `python3.12 setup.py` | Double-click `Hey_Baby.command` or run `./start.sh` |
| Windows x64 | `py -3.12 setup.py` | Double-click `start.bat` |
| Linux x64 desktop | Install PortAudio (e.g. `libportaudio2` on Debian/Ubuntu) and optionally `espeak-ng` for spoken replies, then run `python3.12 setup.py` | `./start.sh` |

Use the system's microphone privacy settings if voice input is blocked. On
macOS, open **System Settings → Privacy & Security → Microphone** and allow the
launcher listed there (often Terminal). Allow **Input Monitoring / Accessibility**
if you want the optional global shortcut. Allow **Screen & System Audio Recording**
for screenshots and **Automation** if prompted for Music control. No administrator
access, Full Disk Access, or remote control is required.

## Use it

- Say **“Hey Baby, open calculator”**, or say **“Hey Baby”**, then speak when
  the panel says **Listening for a command**.
- Tap and release **Command (⌘)** by itself on your Mac to start listening.
  On Windows or Linux, use **F8**.
- In **Settings**, choose **Hold Right Command to talk** to record while held
  and process on release. Settings also reports microphone and shortcut status.
- Click **Start listening** in the panel or the menu bar to speak without
  saying “Hey Baby” first. Wait for **Listening for a command**, then speak.
  You can also use **Option+Space** (Alt+Space outside macOS) if available.
  Some desktops reserve that shortcut
  and Linux Wayland may restrict global shortcuts. You can also type commands.
- Say **“Hey Baby, stop”** or **“Hey Baby, cancel”** to end a request. During
  spoken output, use **Stop** or **Esc**; the microphone is closed during
  playback so the assistant doesn't hear itself.
- Say **“Hey Baby, pause listening”** or click **Pause mic** to release the
  microphone. Use **Resume mic** or type **resume listening** to turn it back on.
- Say **“Hey Baby, quit assistant”**, choose **Quit Hey Baby** from **More options**, or quit from the menu bar
  to close the app. **Hide** keeps wake detection running.

Open **Commands** in the panel for examples. Basic commands include time, date,
opening supported apps and folders, and web search. macOS also supports volume,
Apple Music, battery status, display sleep, and screenshots. Computer actions
are a fixed list; speech and cloud replies never run as shell code.

To use Command without starting Hey Baby in Terminal each time, quit any manually
started copy, then run `./install_service.sh` once on macOS. Hey Baby starts in
the menu bar immediately and at each sign-in. Tap Command or say “Hey Baby” to open
the panel and start listening. Use **Hide panel** to keep activation available.
The login service restarts Hey Baby if its process exits, so the shortcut
stays available. Use **Pause mic** to turn off voice input, or run
`./uninstall_service.sh` to stop the service and remove login launch.

### Dictation

Choose **Start dictation** from the menu or press **Option+Shift+D**. Speak,
then click **Finish dictation**. Review and edit the result before using
**Copy**. Dictation text never runs as a command.

On Mac, verified insertion is available with Accessibility permission. Focus
your editor before starting dictation with the keyboard shortcut. After reviewing
the preview, refocus the original editor and press **Option+Shift+I**.
Insertion requires a supported editable field and the same text and selection.
Use **Copy** for unsupported fields. Nothing is submitted automatically.

### Build the Mac app

After setup, run `.hey-baby-venv/bin/python -m pip install 'pyinstaller>=6.18,<7'`
and then `./build_mac.sh`. The build needs the macOS Command Line Tools or a
configured Xcode toolchain. Open `dist/Hey Baby.app` from Finder. The app includes
the local speech model and does not need a separate Python environment to run.
The build is signed locally for testing. Distribution to other Macs requires
your own release signing and notarization.

Run `./install_service.sh` after building to use the bundle for login launch.
Keep the bundle at the path used during installation. If an earlier Python
launcher already has permissions, grant the packaged **Hey Baby** app its own
Microphone and Input Monitoring access as needed.

Optional Sarvam text chat is off by default. Install `sarvamai` and
`python-dotenv` in the Hey Baby environment, set `HEY_BABY_CLOUD_CHAT=1`, and
provide `SARVAM_API_KEY`. Only unmatched commands are sent to Sarvam as text.
The legacy browser UI and local command server are not started by Hey Baby.

## Source layout

```text
heysaran/
├── heybaby/              # Desktop voice assistant
│   ├── core/             # Commands, sessions, and wake phrase parsing
│   ├── desktop/          # Qt panel, tray, and application lifecycle
│   └── integrations/     # Speech, shortcuts, dictation, and optional chat
├── studio/               # Independently runnable web companion
│   ├── src/              # React client and server rendering
│   └── server/           # API, persistence, auth, and web tests
├── tests/                # Desktop unit tests
├── legacy/               # Earlier browser prototype and diagnostics
├── models/               # Speech model setup instructions
├── .github/workflows/    # Automated checks
├── hey_saran.py          # Compatibility launcher
├── setup.py              # Local environment and speech model installer
└── requirements.txt      # Desktop dependencies
```

The existing launchers use `hey_saran.py`, which delegates to the package.
During development, run `.hey-baby-venv/bin/python -m heybaby` from the
workspace. Run `.hey-baby-venv/bin/python -m unittest discover` for the tests.

## Studio web companion

See [Studio setup](studio/README.md) and the [63-item assessment checklist](studio/RUBRIC.md).
Studio handles saved notes, command presets, and account services. Run it separately
from the local desktop assistant.
