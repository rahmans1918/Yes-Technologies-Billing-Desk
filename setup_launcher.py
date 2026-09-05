from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path


PROJECT_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
VENV_DIR = PROJECT_DIR / ".venv"
PYTHON_EXE = VENV_DIR / "Scripts" / "python.exe"


def run(command: list[str]) -> None:
    print(f"\n> {' '.join(command)}")
    subprocess.check_call(command, cwd=PROJECT_DIR)


def pause() -> None:
    try:
        input("Press Enter to close...")
    except EOFError:
        pass


def main() -> None:
    print("Yes Technologies Billing Desk setup")
    print(f"Project folder: {PROJECT_DIR}")

    if not PYTHON_EXE.exists():
        print("Creating Python virtual environment...")
        venv.create(VENV_DIR, with_pip=True)

    run([str(PYTHON_EXE), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(PYTHON_EXE), "-m", "pip", "install", "-r", "requirements.txt"])
    (PROJECT_DIR / "instance").mkdir(exist_ok=True)

    print("\nSetup complete.")
    print("Start the application with run.bat")
    pause()


if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, OSError) as error:
        print(f"\nSetup failed: {error}")
        pause()
        sys.exit(1)