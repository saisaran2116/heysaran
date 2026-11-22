"""Install dependencies and the local speech model into this project folder."""

import shutil
import subprocess
import sys
import tempfile
import urllib.request
import venv
import zipfile
from pathlib import Path

from heybaby.integrations.speech import DEFAULT_MODEL

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".hey-baby-venv"
MODEL_URL = "https://alphacephei.com/vosk/models/" + DEFAULT_MODEL.name + ".zip"


def main():
    if not (3, 10) <= sys.version_info[:2] <= (3, 14):
        raise SystemExit("Run setup with Python 3.10–3.14. Python 3.12 is recommended.")
    if sys.platform == "win32":
        python = ENV / "Scripts" / "python.exe"
    else:
        python = ENV / "bin" / "python"
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(ENV)
    subprocess.run([str(python), "-m", "pip", "install", "-r",
                    str(ROOT / "requirements.txt")], check=True)
    if not (DEFAULT_MODEL / "conf" / "model.conf").is_file():
        print("Downloading the local English speech model (36 MB)…", flush=True)
        with tempfile.TemporaryDirectory(dir=DEFAULT_MODEL.parent) as tmp:
            temp = Path(tmp)
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
                with (temp / "model.zip").open("wb") as output:
                    shutil.copyfileobj(response, output)
            with zipfile.ZipFile(temp / "model.zip") as archive:
                for member in archive.infolist():
                    destination = (temp / member.filename).resolve()
                    if not destination.is_relative_to(temp) or Path(member.filename).parts[0] != DEFAULT_MODEL.name:
                        raise ValueError("Unexpected path in the model archive")
                    archive.extract(member, temp)
            model = temp / DEFAULT_MODEL.name
            if not (model / "conf" / "model.conf").is_file():
                raise ValueError("The downloaded archive does not contain the speech model")
            if not (DEFAULT_MODEL / "conf" / "model.conf").is_file():
                model.rename(DEFAULT_MODEL)
    print(f'Run Hey Baby with:\n"{python}" "{ROOT / "hey_saran.py"}"')


if __name__ == "__main__":
    main()
