# WhisperLiveKit + Live Translation — Setup Guide

Real-time speech-to-text with live translation. Captures audio from meetings (Teams, Zoom, etc.), transcribes English speech, and translates to Vietnamese — all running locally.

## How it works

```
Meeting app audio
      |
Virtual audio device (VB-Cable / BlackHole)
      |
Browser mic input --> WhisperLiveKit (Whisper model, local CPU/GPU)
                              |
                         English text
                              |
                    ProxyPal --> Gemini API (translation)
                              |
                        Vietnamese text
                              |
                    Browser UI (shows both)
```

---

## Prerequisites

### 1. Python 3.11–3.13

- **Windows:** https://www.python.org/downloads/ — check "Add to PATH" during install
- **Mac:** `brew install python@3.12` or download from python.org

Verify: `python --version`

### 2. FFmpeg

- **Windows:** Download from https://www.gyan.dev/ffmpeg/builds/ (essentials build), extract, add `bin/` to PATH
- **Mac:** `brew install ffmpeg`

Verify: `ffmpeg -version`

### 3. ProxyPal (for LLM translation via Gemini)

ProxyPal is a free desktop app that gives you an OpenAI-compatible API endpoint backed by Google Gemini — no API key purchase needed, just your Google account.

1. Download and install **ProxyPal** from https://proxypal.dev
2. Open ProxyPal and sign in with your Google account
3. ProxyPal starts a local API server at `http://localhost:8317`
4. Leave ProxyPal running whenever you use the translate server

**Find your API key** (needed for the run command):
- Windows: `%APPDATA%\ProxyPal\config.json` → look for `proxyApiKey` field (default: `proxypal-local`)
- Mac: `~/Library/Application Support/ProxyPal/config.json` → same field

Verify ProxyPal is working:
```bash
curl -s -H "Authorization: Bearer proxypal-local" http://localhost:8317/v1/models
```
You should see a list of available models (Gemini, Claude, etc.).

### 4. Virtual Audio Device (for meeting audio capture)

WhisperLiveKit captures audio from your browser's microphone input. To transcribe meeting audio, you need to route the meeting app's audio output through a virtual device.

- **Windows:** [VB-Cable](https://vb-audio.com/Cable/) (free) — restart required after install
- **Mac:** [BlackHole](https://existential.audio/blackhole/) (free) or [Loopback](https://rogueamoeba.com/loopback/) (paid, easier)

**Setup in Teams/Zoom:**
1. Set your meeting app's **speaker output** to the virtual cable (e.g. "CABLE Input")
2. Open System Sound settings → find the virtual cable → enable **"Listen to this device"** → route output to your real headset so you still hear the meeting
3. In the WhisperLiveKit browser UI, select the virtual cable as the **microphone**

---

## Installation

### Windows

Run this once to set up the Python environment:

```
setup_and_run.bat
```

This script:
- Checks Python, FFmpeg, and ProxyPal prerequisites
- Creates a virtual environment (`venv/`)
- Installs WhisperLiveKit (CPU mode) + OpenAI SDK

After setup completes, use `run_translate.bat` to start the server.

### Mac (Apple Silicon M1/M2/M3)

```bash
# Clone if you haven't already
git clone https://github.com/daominhsangvn/WhisperLiveKit.git
cd WhisperLiveKit

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install WhisperLiveKit with MLX backend (uses Apple Neural Engine — fastest on M-series)
pip install -e ".[mlx-whisper]"

# Install OpenAI SDK (for ProxyPal)
pip install openai anthropic
```

### Mac (Intel)

Same as Apple Silicon but use the CPU backend:

```bash
pip install -e ".[cpu]"
pip install openai anthropic
```

---

## Running

### Windows

Make sure ProxyPal is running, then:

```
run_translate.bat
```

Open **http://localhost:8000** in your browser.

### Mac (Apple Silicon)

```bash
source venv/bin/activate

python translate_server.py \
    --backend mlx-whisper \
    --model small \
    --language en \
    --pcm-input \
    --min-chunk-size 0.5 \
    --translator openai \
    --llm-base-url http://localhost:8317/v1 \
    --llm-api-key proxypal-local \
    --llm-model gemini-2.5-flash \
    --source-lang English \
    --target-lang Vietnamese
```

Open **http://localhost:8000** in your browser.

### Mac (Intel)

Same as above but omit `--backend mlx-whisper` (defaults to faster-whisper CPU).

---

## Model Selection

| Model | Quality | Speed (CPU) | Speed (M2 MLX) | RAM |
|-------|---------|-------------|-----------------|-----|
| `tiny` | Low | Fastest | Fastest | ~1 GB |
| `base` | OK | Very fast | Very fast | ~1.5 GB |
| `small` | Good | Fast | Fast | ~2.5 GB |
| `medium` | Very good | Moderate | Fast | ~5 GB |
| `large-v3` | Best | Slow | Moderate | ~10 GB |

**Recommendation:** Start with `small`. On Mac M2 with MLX the `medium` model is also very usable.

---

## Flags Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--translator` | `openai` (ProxyPal), `claude`, or `gemini` | `claude` |
| `--llm-base-url` | API endpoint | `LLM_BASE_URL` env var |
| `--llm-api-key` | API key | `LLM_API_KEY` env var |
| `--llm-model` | Model name | `gemini-2.5-flash` |
| `--source-lang` | Source language name | `English` |
| `--target-lang` | Target language name | `Vietnamese` |
| `--backend` | Whisper backend: `faster-whisper`, `mlx-whisper` | auto |
| `--model` | Whisper model size | `small` |
| `--min-chunk-size` | Seconds of audio per inference chunk | `1` |

---

## Alternative Translation APIs

Instead of ProxyPal you can use:

**Anthropic Claude:**
```bash
export ANTHROPIC_API_KEY=sk-ant-your-key   # Mac/Linux
set ANTHROPIC_API_KEY=sk-ant-your-key      # Windows

python translate_server.py --translator claude --model small --language en --pcm-input --min-chunk-size 1 --source-lang English --target-lang Vietnamese
```

**Google Gemini (native SDK):**
```bash
export GEMINI_API_KEY=your-key   # Mac/Linux
set GEMINI_API_KEY=your-key      # Windows

python translate_server.py --translator gemini --model small --language en --pcm-input --min-chunk-size 1 --source-lang English --target-lang Vietnamese
```

---

## Diagnostics

Run the full diagnostic script to check all prerequisites:

```bash
python diagnose.py
```

---

## Troubleshooting

**No audio captured / silence in UI**
- Restart after installing VB-Cable or BlackHole — the driver needs a reboot to activate
- Check the browser has microphone permission
- In the WhisperLiveKit UI microphone selector, choose the virtual cable device

**Translation not appearing**
- Make sure ProxyPal is running and the API key matches (`proxypal-local` by default)
- Check the terminal for errors — model capacity errors mean the Gemini model is overloaded, try switching to `gemini-2.5-flash` or `gemini-3-flash`

**High latency on Windows CPU**
- Use a smaller model (`base` instead of `small`)
- Reduce `--min-chunk-size` to `0.5`

**ProxyPal API key mismatch**
- Check `%APPDATA%\ProxyPal\config.json` (Windows) or `~/Library/Application Support/ProxyPal/config.json` (Mac) for the `proxyApiKey` value and use that in `--llm-api-key`
