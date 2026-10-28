#!/usr/bin/env python3
"""Get the app running in front of you, in one command, on any machine.

    python scripts/try_it.py          (Windows)
    python3 scripts/try_it.py         (macOS, Linux)

Installs what is missing, starts the API and the client, waits for both, and
prints the URL. Ctrl-C stops everything.

There is a `try_it.sh` beside this. It does the same thing and it is a bash
script, which quietly assumed macOS or Linux -- Windows has no bash unless
you install one. This is the version that does not care: Python is already a
requirement, so the launcher may as well be written in it.

No GPU, no dataset, no trained model. The classifier is a stub returning
deterministic nonsense; everything around it -- the refusal, the questions,
the hazard display, the consent gate -- is real.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_PORT = int(os.environ.get("API_PORT", "8000"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8081"))
WINDOWS = os.name == "nt"

processes: list[subprocess.Popen] = []


# Where server/app/config.py looks for a trained model. Named here so the
# closing advice can point at an exact path rather than a description of one.
MODEL_PATH = ROOT / "ml" / "runs" / "baseline" / "model.onnx"


def say(text: str) -> None:
    print(f"\n{text}")


def note(text: str) -> None:
    print(f"  {text}")


def die(text: str) -> None:
    print(f"\nSTOPPED: {text}\n", file=sys.stderr)
    stop_everything()
    raise SystemExit(1)


def stop_everything() -> None:
    for p in processes:
        if p.poll() is None:
            p.terminate()
    for p in processes:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


def reachable(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=2)
        return True
    except urllib.error.HTTPError:
        return True  # it answered, which is all we are asking
    except Exception:
        return False


def wait_for(url: str, seconds: int, what: str, log: Path) -> None:
    for _ in range(seconds):
        if reachable(url):
            return
        time.sleep(1)
    die(f"{what} did not start within {seconds}s. Look in {log.name} for why.")


def npm_command() -> str:
    """npm is a .cmd shim on Windows, which subprocess will not find bare."""
    found = shutil.which("npm.cmd") if WINDOWS else shutil.which("npm")
    return found or shutil.which("npm") or ""


def closing_advice(health: dict) -> str:
    """What to try, given which backend actually answered /health.

    Step 2 is the reason this is a function. "The classifier is a stub, so
    whatever it names is meaningless" is true of the stub and is dangerous
    advice about a trained model -- it tells the reader to disregard a real
    identification. The launcher already reads /health, so it can simply
    not say the wrong one.
    """
    out = ["  What to do when it loads:", "",
           "    1. Tick all six boxes and continue. There is no accept-all, "
           "on purpose."]

    if health["model_loaded"]:
        out.append(
            "    2. Add a photograph of a real mushroom as the cap. This is the\n"
            "       trained model: the name it gives you is a real identification,\n"
            "       on 244 British species. Then try a photograph of something\n"
            "       that is NOT a mushroom -- a chair, a pavement, your hand. It\n"
            "       should decline, and that refusal is a different one from\n"
            '       "I\'m not sure what this is".'
        )
        if not health["calibrated"]:
            out.append(
                "       No calibration is loaded, so every percentage on screen is\n"
                "       an uncalibrated softmax output. Rule 4: the app says so\n"
                "       rather than presenting it as confidence. Put\n"
                "       calibration.json beside model.onnx to fix it."
            )
    else:
        out.append(
            "    2. Add any photograph as the cap -- a real mushroom, a chair,\n"
            "       anything. The classifier is a stub, so whatever it names is\n"
            "       meaningless."
        )

    out.append(
        "    3. Look at what happens AROUND the name. That is the whole product:\n"
        "       whether it refuses, what it asks you to check next, and what it\n"
        "       declines to say about eating anything.\n"
        "    4. Try the red cross, top right. That screen is hardcoded and works\n"
        "       offline, and it sits above the consent gate."
    )

    if health["model_loaded"]:
        out += ["", '  The verdict worth hunting for is "I can\'t safely narrow '
                'this down" --\n  a lethal pair in play and the app refusing to '
                'choose. Anything small\n  and tawny on wood is a good bet.']
    else:
        out += ["", "  Different photographs give different (fake) verdicts. Keep "
                'going until\n  you get "I can\'t safely narrow this down" -- that '
                "is the one worth\n  seeing, and the one no competitor will ever "
                "show you."]
        out += ["", "  No model is loaded. If you have model.onnx from a training "
                f"run, put\n  it at {MODEL_PATH},\n  with labels.json and "
                "calibration.json beside it, and run this again --\n  nothing "
                "else changes."]

    out += ["", "  Press Ctrl-C here to stop both."]
    return "\n".join(out)


def main() -> int:
    if sys.version_info < (3, 11):
        die(f"Python 3.11 or newer is needed. This is {sys.version.split()[0]}.")

    npm = npm_command()
    if not npm:
        die(
            "Node is not installed, or not on your PATH.\n"
            "Get the LTS installer from https://nodejs.org and run this again.\n"
            "On Windows you must close and reopen the terminal afterwards."
        )

    # --- The API ------------------------------------------------------------
    say("1/3  The API")
    try:
        import fastapi  # noqa: F401
        import numpy  # noqa: F401
        import PIL  # noqa: F401

        note("dependencies already installed")
    except ImportError:
        note("installing server dependencies (a minute or two)")
        install = [sys.executable, "-m", "pip", "install", "--quiet",
                   "-r", str(ROOT / "server" / "requirements.txt")]
        if subprocess.run(install).returncode != 0:
            # Debian and friends refuse to install outside a venv without this.
            subprocess.run(install + ["--break-system-packages"], check=True)

    api_log = ROOT / ".try_it_api.log"
    with api_log.open("w") as log:
        processes.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "127.0.0.1", "--port", str(API_PORT)],
            cwd=ROOT / "server", stdout=log, stderr=subprocess.STDOUT,
        ))

    wait_for(f"http://127.0.0.1:{API_PORT}/health", 90, "The API", api_log)
    note(f"running on http://127.0.0.1:{API_PORT}")
    health = json.load(urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/health"))
    note(
        f"{health['n_classes']} species  |  "
        f"model_loaded={health['model_loaded']}  "
        f"calibrated={health['calibrated']}  "
        f"taxonomy_reviewed={health['taxonomy_reviewed']}"
    )

    # --- The client ---------------------------------------------------------
    say("2/3  The client")
    if (ROOT / "app" / "node_modules").is_dir():
        note("dependencies already installed")
    else:
        note("installing client dependencies -- several minutes the first time")
        subprocess.run([npm, "install", "--no-audit", "--no-fund"],
                       cwd=ROOT / "app", check=True)

    env = dict(os.environ, EXPO_PUBLIC_API_URL=f"http://127.0.0.1:{API_PORT}")
    web_log = ROOT / ".try_it_web.log"
    with web_log.open("w") as log:
        processes.append(subprocess.Popen(
            [npm, "exec", "--", "expo", "start", "--web", "--port", str(WEB_PORT)],
            cwd=ROOT / "app", env=env, stdout=log, stderr=subprocess.STDOUT,
        ))

    note("starting the client -- up to a minute the first time")
    wait_for(f"http://localhost:{WEB_PORT}", 240, "The client", web_log)

    # --- Over to you --------------------------------------------------------
    say("3/3  Open this in your browser")
    print(f"\n      http://localhost:{WEB_PORT}\n")
    print(closing_advice(health))

    try:
        while all(p.poll() is None for p in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n  stopping...")
        stop_everything()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
