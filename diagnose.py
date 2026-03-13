"""
WhisperLiveKit + Live Translation -Diagnostics
Checks all prerequisites and configuration.

Usage:
    python diagnose.py
    venv\Scripts\python diagnose.py   (if venv exists)
"""

import os
import shutil
import subprocess
import sys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

results = {"pass": 0, "fail": 0, "warn": 0}


def check(label, passed, msg_pass="", msg_fail="", warn=False):
    if passed:
        results["pass"] += 1
        print(f"  {PASS} {label}" + (f" -{msg_pass}" if msg_pass else ""))
    elif warn:
        results["warn"] += 1
        print(f"  {WARN} {label}" + (f" -{msg_fail}" if msg_fail else ""))
    else:
        results["fail"] += 1
        print(f"  {FAIL} {label}" + (f" -{msg_fail}" if msg_fail else ""))


def run_cmd(cmd, timeout=10):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=True
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -1, "", "timed out"
    except Exception as e:
        return -1, "", str(e)


def section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# 1. Python
# ---------------------------------------------------------------------------

def check_python():
    section("Python")

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    check(
        f"Python version: {version_str}",
        version >= (3, 11) and version < (3, 14),
        msg_fail=f"Requires Python 3.11-3.13. You have {version_str}. Download from https://www.python.org/downloads/",
    )

    # Check venv
    venv_active = sys.prefix != sys.base_prefix
    venv_exists = os.path.exists(os.path.join(os.path.dirname(__file__), "venv"))
    if venv_active:
        check("Virtual environment", True, msg_pass="active")
    elif venv_exists:
        check(
            "Virtual environment",
            False,
            warn=True,
            msg_fail="exists but not activated. Run: venv\\Scripts\\activate (Windows) or source venv/bin/activate (Mac/Linux)",
        )
    else:
        check(
            "Virtual environment",
            False,
            warn=True,
            msg_fail="not found. Run: python -m venv venv",
        )


# ---------------------------------------------------------------------------
# 2. FFmpeg
# ---------------------------------------------------------------------------

def check_ffmpeg():
    section("FFmpeg")

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        code, out, err = run_cmd("ffmpeg -version")
        version_line = out.split("\n")[0] if out else "unknown"
        check("FFmpeg installed", True, msg_pass=version_line)
    else:
        check(
            "FFmpeg installed",
            False,
            msg_fail="Not found in PATH. Download from https://www.gyan.dev/ffmpeg/builds/ (Windows) or 'brew install ffmpeg' (Mac)",
        )


# ---------------------------------------------------------------------------
# 3. Python packages
# ---------------------------------------------------------------------------

def check_package(name, install_hint=""):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def check_packages():
    section("Python Packages")

    packages = [
        ("faster_whisper", "faster-whisper", True),
        ("torch", "torch", True),
        ("torchaudio", "torchaudio", True),
        ("fastapi", "fastapi", True),
        ("uvicorn", "uvicorn", True),
        ("librosa", "librosa", True),
        ("tiktoken", "tiktoken", True),
        ("websockets", "websockets", True),
        ("openai", "openai", True),
        ("anthropic", "anthropic", False),
        ("google.generativeai", "google-generativeai", False),
    ]

    for import_name, pip_name, required in packages:
        installed = check_package(import_name)
        if required:
            check(
                pip_name,
                installed,
                msg_pass="installed",
                msg_fail=f"missing -run: pip install {pip_name}",
            )
        else:
            check(
                f"{pip_name} (optional)",
                installed,
                msg_pass="installed",
                msg_fail=f"not installed -run: pip install {pip_name}",
                warn=True,
            )

    # Check whisperlivekit itself
    installed = check_package("whisperlivekit")
    check(
        "whisperlivekit",
        installed,
        msg_pass="installed",
        msg_fail='missing -run: pip install -e ".[cpu]"',
    )


# ---------------------------------------------------------------------------
# 4. Whisper model cache
# ---------------------------------------------------------------------------

def check_whisper_models():
    section("Whisper Models (cached)")

    cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    if not os.path.exists(cache_dir):
        check("HuggingFace cache", False, warn=True, msg_fail="no models downloaded yet -will download on first run")
        return

    models_found = []
    for entry in os.listdir(cache_dir):
        if "faster-whisper" in entry.lower():
            model_name = entry.replace("models--Systran--faster-whisper-", "")
            models_found.append(model_name)
        elif "whisper" in entry.lower() and "models--" in entry:
            model_name = entry.split("models--")[-1]
            models_found.append(model_name)

    if models_found:
        check("Whisper models cached", True, msg_pass=", ".join(models_found))
    else:
        check(
            "Whisper models cached",
            False,
            warn=True,
            msg_fail="no models downloaded yet -will download on first run (~500 MB for 'small')",
        )


# ---------------------------------------------------------------------------
# 5. Virtual Audio Cable
# ---------------------------------------------------------------------------

def check_audio_devices():
    section("Audio Devices")

    if sys.platform != "win32":
        check("Audio device check", True, warn=True, msg_fail="skipped (non-Windows)")
        return

    code, out, err = run_cmd(
        'powershell.exe -Command "Get-PnpDevice -Class AudioEndpoint -Status OK | Select-Object -ExpandProperty FriendlyName"'
    )

    if code != 0:
        check("Audio device enumeration", False, warn=True, msg_fail="could not list audio devices")
        return

    devices = [d.strip() for d in out.split("\n") if d.strip()]

    # Check for VB-Cable
    vb_cable = any("vb-audio" in d.lower() or "vb cable" in d.lower() for d in devices)
    check(
        "VB-Audio Virtual Cable",
        vb_cable,
        msg_pass="installed",
        msg_fail="not found -download from https://vb-audio.com/Cable/",
    )

    # Check for VoiceMeeter
    voicemeeter = any("voicemeeter" in d.lower() for d in devices)
    check(
        "VoiceMeeter (optional)",
        voicemeeter,
        msg_pass="installed",
        msg_fail="not installed (optional, VB-Cable is sufficient)",
        warn=True,
    )

    # Check for Stereo Mix
    code2, out2, _ = run_cmd(
        'powershell.exe -Command "Get-PnpDevice -Class AudioEndpoint | Select-Object FriendlyName, Status"'
    )
    stereo_mix = "stereo mix" in out2.lower() if out2 else False
    check(
        "Stereo Mix",
        stereo_mix,
        msg_pass="available",
        msg_fail="not available on this PC (VB-Cable is the alternative)",
        warn=True,
    )

    # List all devices
    print(f"\n  {INFO} Audio devices found:")
    for d in devices:
        marker = ""
        dl = d.lower()
        if "vb-audio" in dl:
            marker = " <--virtual cable"
        elif "voicemeeter" in dl:
            marker = " <--voicemeeter"
        elif "microphone" in dl or "headset mic" in dl:
            marker = " <--microphone"
        elif "headset earphone" in dl or "headphone" in dl:
            marker = " <--headset output"
        elif "speaker" in dl and "vb" not in dl:
            marker = " <--speakers"
        print(f"       - {d}{marker}")


# ---------------------------------------------------------------------------
# 6. LLM API connectivity
# ---------------------------------------------------------------------------

def check_llm_apis():
    section("LLM API Connectivity")

    # Check CLIProxyAPI / ProxyPal
    import urllib.request
    import json

    proxy_url = "http://localhost:8317/v1/models"
    proxy_key = "proxypal-local"

    try:
        req = urllib.request.Request(proxy_url)
        req.add_header("Authorization", f"Bearer {proxy_key}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            models = [m["id"] for m in data.get("data", [])]
            check(
                f"CLIProxyAPI / ProxyPal (localhost:8317)",
                True,
                msg_pass=f"{len(models)} models available",
            )
            # Show a few translation-relevant models
            good_models = [m for m in models if any(k in m for k in ["flash", "gemini-2.5", "gemini-3", "claude"])]
            if good_models:
                print(f"  {INFO} Recommended models for translation:")
                for m in good_models[:6]:
                    print(f"       - {m}")
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            check(
                "CLIProxyAPI / ProxyPal (localhost:8317)",
                False,
                msg_fail=f"reachable but auth failed (HTTP {e.code}) -check API key in %APPDATA%/ProxyPal/config.json",
            )
        else:
            check(
                "CLIProxyAPI / ProxyPal (localhost:8317)",
                False,
                warn=True,
                msg_fail=f"HTTP error {e.code}",
            )
    except Exception:
        check(
            "CLIProxyAPI / ProxyPal (localhost:8317)",
            False,
            warn=True,
            msg_fail="not running -start ProxyPal app first",
        )

    # Check env vars for other providers
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    check(
        "ANTHROPIC_API_KEY (optional)",
        bool(anthropic_key),
        msg_pass="set",
        msg_fail="not set",
        warn=True,
    )

    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    check(
        "GEMINI_API_KEY (optional)",
        bool(gemini_key),
        msg_pass="set",
        msg_fail="not set",
        warn=True,
    )


# ---------------------------------------------------------------------------
# 7. GPU / Compute
# ---------------------------------------------------------------------------

def check_compute():
    section("Compute / GPU")

    if sys.platform == "darwin":
        # Check for Apple Silicon
        import platform
        is_arm = platform.machine() == "arm64"
        check(
            "Apple Silicon (MLX)",
            is_arm,
            msg_pass=f"{platform.machine()} -use --backend mlx-whisper for best performance",
            msg_fail=f"{platform.machine()} -Intel Mac, will use CPU",
            warn=not is_arm,
        )
        return

    # Check CUDA
    try:
        import torch
        cuda = torch.cuda.is_available()
        if cuda:
            gpu_name = torch.cuda.get_device_name(0)
            check("NVIDIA CUDA GPU", True, msg_pass=gpu_name)
        else:
            check(
                "NVIDIA CUDA GPU",
                False,
                warn=True,
                msg_fail="not available -will use CPU (slower but works fine with 'small' or 'base' model)",
            )
    except ImportError:
        check("NVIDIA CUDA GPU", False, warn=True, msg_fail="torch not installed, cannot check")

    # Check AMD GPU
    if sys.platform == "win32":
        code, out, _ = run_cmd(
            'powershell.exe -Command "Get-WmiObject Win32_VideoController | Select-Object -ExpandProperty Name"'
        )
        if out:
            gpus = [g.strip() for g in out.split("\n") if g.strip()]
            for gpu in gpus:
                is_nvidia = "nvidia" in gpu.lower()
                is_amd = "amd" in gpu.lower() or "radeon" in gpu.lower()
                label = f"GPU: {gpu}"
                if is_nvidia:
                    check(label, True, msg_pass="CUDA supported")
                elif is_amd:
                    check(label, True, warn=True, msg_pass="detected (no CUDA -Whisper runs on CPU)")
                else:
                    print(f"  {INFO} GPU: {gpu}")


# ---------------------------------------------------------------------------
# 8. Server port
# ---------------------------------------------------------------------------

def check_ports():
    section("Network")

    import socket

    # Check if port 8000 is available or already in use by our server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", 8000))
        if result == 0:
            check("Port 8000", True, msg_pass="in use (WhisperLiveKit server may already be running)")
        else:
            check("Port 8000", True, msg_pass="available")
    except Exception:
        check("Port 8000", True, msg_pass="available")
    finally:
        sock.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print()
    print("  WhisperLiveKit + Live Translation -Diagnostics")
    print("  ================================================")

    check_python()
    check_ffmpeg()
    check_packages()
    check_whisper_models()
    check_compute()
    check_audio_devices()
    check_llm_apis()
    check_ports()

    # Summary
    section("Summary")
    total = results["pass"] + results["fail"] + results["warn"]
    print(f"  {PASS} {results['pass']}/{total} checks passed")
    if results["warn"]:
        print(f"  {WARN} {results['warn']} warnings")
    if results["fail"]:
        print(f"  {FAIL} {results['fail']} checks failed -fix these before running")
        print()
        print("  Quick fix:")
        print("    1. Run setup_and_run.bat (installs all Python packages)")
        print("    2. Install VB-Cable from https://vb-audio.com/Cable/")
        print("    3. Start ProxyPal (or set ANTHROPIC_API_KEY)")
    else:
        print()
        print("  All good! Run the server:")
        print("    run_translate.bat")
        print("    or: python translate_server.py --model small --language en --pcm-input --min-chunk-size 1 --translator openai --llm-base-url http://localhost:8317/v1 --llm-api-key proxypal-local --llm-model gemini-2.5-flash")

    print()


if __name__ == "__main__":
    main()
