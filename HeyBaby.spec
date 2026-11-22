# Build from the workspace with the project Python environment.
from pathlib import Path
from importlib.util import find_spec
from heybaby.integrations.speech import DEFAULT_MODEL

packages = Path(find_spec("vosk").origin).parent.parent
analysis = Analysis(
    ["hey_saran.py"],
    pathex=[str(Path(SPECPATH))],
    datas=[(str(DEFAULT_MODEL), "models/" + DEFAULT_MODEL.name)],
    binaries=[
        (str(packages / "vosk/libvosk.dyld"), "vosk"),
        (str(packages / "_sounddevice_data/portaudio-binaries/libportaudio.dylib"),
         "_sounddevice_data/portaudio-binaries"),
    ],
    hiddenimports=["pynput.keyboard._darwin", "pynput._util.darwin", "_cffi_backend"],
)
archive = PYZ(analysis.pure)
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True,
                 name="HeyBaby", console=False)
collection = COLLECT(executable, analysis.binaries, analysis.datas, name="HeyBaby")
app = BUNDLE(collection, name="Hey Baby.app", bundle_identifier="com.saran.heybaby",
             info_plist={"CFBundleDisplayName": "Hey Baby",
                         "LSUIElement": True,
                         "NSMicrophoneUsageDescription": "Hey Baby listens for your wake phrase, commands and dictation on this Mac."})
