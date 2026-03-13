"""
Pre-installation system check.
Verifies prerequisites BEFORE installing Python packages.
Returns exit code 0 if all good, 1 if critical issues found.

Usage:
    python precheck.py          # check before setup
    python precheck.py --pre-run # check before running server (includes package checks)
"""

import os
import shutil
import subprocess
import sys

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

failures = []
warnings = []


def check(label, passed, msg_pass="", msg_fail="", required=True):
    if passed:
        print(f"  {PASS} {label}" + (f" - {msg_pass}" if msg_pass else ""))
    elif required:
        print(f"  {FAIL} {label}" + (f" - {msg_fail}" if msg_fail else ""))
        failures.append(f"{label}: {msg_fail}")
    else:
        print(f"  {WARN} {label}" + (f" - {msg_fail}" if msg_fail else ""))
        warnings.append(f"{label}: {msg_fail}")


def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=True
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception:
        return -1, "", ""


def check_python():
    print()
    print("  Checking Python...")
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    check(
        f"Python {version_str}",
        v >= (3, 11) and v < (3, 14),
        msg_fail=f"Requires 3.11-3.13. Download from https://www.python.org/downloads/",
    )


def check_ffmpeg():
    print("  Checking FFmpeg...")
    found = shutil.which("ffmpeg") is not None
    check(
        "FFmpeg",
        found,
        msg_pass="found in PATH",
        msg_fail="not found. Download: https://www.gyan.dev/ffmpeg/builds/ (Windows) or 'brew install ffmpeg' (Mac)",
    )


def check_audio():
    print("  Checking audio devices...")
    if sys.platform != "win32":
        print(f"  {WARN} Audio check skipped (non-Windows)")
        return

    code, out, _ = run_cmd(
        'powershell.exe -Command "Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object -ExpandProperty FriendlyName"'
    )
    if code != 0:
        check("Audio devices", False, msg_fail="could not enumerate", required=False)
        return

    devices = [d.strip() for d in out.split("\n") if d.strip()]
    has_vbcable = any("vb-audio" in d.lower() for d in devices)
    has_voicemeeter = any("voicemeeter" in d.lower() for d in devices)
    has_stereo = False

    code2, out2, _ = run_cmd(
        'powershell.exe -Command "Get-PnpDevice -Class AudioEndpoint | Select-Object -ExpandProperty FriendlyName"'
    )
    if out2:
        has_stereo = "stereo mix" in out2.lower()

    has_any = has_vbcable or has_voicemeeter or has_stereo

    check(
        "Virtual audio device (VB-Cable / VoiceMeeter / Stereo Mix)",
        has_any,
        msg_pass="VB-Cable" if has_vbcable else ("VoiceMeeter" if has_voicemeeter else "Stereo Mix"),
        msg_fail="none found. Install VB-Cable (free): https://vb-audio.com/Cable/\n"
        "         Required to capture meeting audio from Teams/Zoom.",
    )


def check_llm_api():
    print("  Checking LLM API...")
    import urllib.request
    import json

    # Check ProxyPal
    proxy_ok = False
    try:
        req = urllib.request.Request("http://localhost:8317/v1/models")
        req.add_header("Authorization", "Bearer proxypal-local")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            count = len(data.get("data", []))
            check("ProxyPal / CLIProxyAPI", True, msg_pass=f"running ({count} models)")
            proxy_ok = True
    except Exception:
        check("ProxyPal / CLIProxyAPI", False, msg_fail="not running on localhost:8317", required=False)

    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

    if not proxy_ok and not has_anthropic and not has_gemini:
        check(
            "At least one LLM API",
            False,
            msg_fail="no translation API available.\n"
            "         Start ProxyPal, or set ANTHROPIC_API_KEY, or set GEMINI_API_KEY.",
            required=False,
        )


def check_packages():
    """Only used with --pre-run flag."""
    print("  Checking Python packages...")

    required = [
        ("faster_whisper", "faster-whisper"),
        ("torch", "torch"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("openai", "openai"),
        ("whisperlivekit", "whisperlivekit"),
    ]

    missing = []
    for import_name, pip_name in required:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        check(
            "Required packages",
            False,
            msg_fail=f"missing: {', '.join(missing)}. Run setup_and_run.bat first.",
        )
    else:
        check("Required packages", True, msg_pass="all installed")


def main():
    pre_run = "--pre-run" in sys.argv

    print()
    print("  ============================================")
    if pre_run:
        print("  Pre-run system check")
    else:
        print("  Pre-install system check")
    print("  ============================================")

    check_python()
    check_ffmpeg()
    check_audio()
    check_llm_api()

    if pre_run:
        check_packages()

    print()

    if failures:
        print("  ============================================")
        print(f"  {FAIL} {len(failures)} critical issue(s) found:")
        print("  ============================================")
        for f in failures:
            print(f"    - {f}")
        print()
        print("  Fix the issues above before continuing.")
        print()
        return 1

    if warnings:
        print(f"  {WARN} {len(warnings)} warning(s) (non-critical):")
        for w in warnings:
            print(f"    - {w}")
        print()

    print(f"  {PASS} System check passed!")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
