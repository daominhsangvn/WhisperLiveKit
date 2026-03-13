"""
WhisperLiveKit + LLM Translation Server
Real-time English speech-to-text with Vietnamese translation via Claude, Gemini, or any OpenAI-compatible API.

Usage:
    # Claude (default)
    python translate_server.py --model small --language en --translator claude

    # OpenAI-compatible proxy (e.g. CLIProxyAPI)
    python translate_server.py --model small --language en \
        --translator openai \
        --llm-base-url http://localhost:8317/v1 \
        --llm-api-key your-key \
        --llm-model gemini-3-flash-preview

    # Gemini native SDK
    python translate_server.py --model small --language en --translator gemini

    # Custom languages
    python translate_server.py --model small --language en --source-lang English --target-lang Japanese

Environment variables (alternative to flags):
    ANTHROPIC_API_KEY  - Required if using Claude (default)
    GEMINI_API_KEY     - Required if using Gemini
    LLM_BASE_URL       - OpenAI-compatible endpoint URL
    LLM_API_KEY        - API key for OpenAI-compatible endpoint
    LLM_MODEL          - Model name for OpenAI-compatible endpoint
"""

import os
import ssl

# Bypass SSL certificate verification for model downloads.
# Needed when running in Docker behind a corporate proxy (e.g. ZScaler) that
# performs SSL inspection and presents a self-signed certificate in the chain.
if os.environ.get("PYTHONHTTPSVERIFY", "1") == "0":
    ssl._create_default_https_context = ssl._create_unverified_context

import asyncio
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger().setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Strip our custom args from sys.argv BEFORE importing parse_args,
# because WhisperLiveKit's ArgumentParser will reject unknown flags.
# ---------------------------------------------------------------------------

_translator_type = "claude"
_source_lang = "English"
_target_lang = "Vietnamese"
_llm_base_url = os.environ.get("LLM_BASE_URL", "")
_llm_api_key = os.environ.get("LLM_API_KEY", "")
_llm_model = os.environ.get("LLM_MODEL", "gemini-3-flash-preview")

_custom_flags = {"--translator", "--source-lang", "--target-lang", "--llm-base-url", "--llm-api-key", "--llm-model"}
_filtered_argv = []
_skip_next = False
for i, arg in enumerate(sys.argv):
    if _skip_next:
        _skip_next = False
        continue
    if arg == "--translator" and i + 1 < len(sys.argv):
        _translator_type = sys.argv[i + 1].lower()
        _skip_next = True
    elif arg == "--source-lang" and i + 1 < len(sys.argv):
        _source_lang = sys.argv[i + 1]
        _skip_next = True
    elif arg == "--target-lang" and i + 1 < len(sys.argv):
        _target_lang = sys.argv[i + 1]
        _skip_next = True
    elif arg == "--llm-base-url" and i + 1 < len(sys.argv):
        _llm_base_url = sys.argv[i + 1]
        _skip_next = True
    elif arg == "--llm-api-key" and i + 1 < len(sys.argv):
        _llm_api_key = sys.argv[i + 1]
        _skip_next = True
    elif arg == "--llm-model" and i + 1 < len(sys.argv):
        _llm_model = sys.argv[i + 1]
        _skip_next = True
    else:
        _filtered_argv.append(arg)

sys.argv = _filtered_argv

# Now safe to import and call parse_args
from whisperlivekit import (
    AudioProcessor,
    TranscriptionEngine,
    get_inline_ui_html,
    parse_args,
)

wlk_config = parse_args()

# ---------------------------------------------------------------------------
# Translation providers
# ---------------------------------------------------------------------------

class TranslatorBase:
    """Base class for translation providers."""
    async def translate(self, text: str) -> str:
        raise NotImplementedError


class ClaudeTranslator(TranslatorBase):
    def __init__(self, source_lang: str = "English", target_lang: str = "Vietnamese"):
        from anthropic import AsyncAnthropic
        self.client = AsyncAnthropic()
        self.system_prompt = (
            f"You are a real-time translator. Translate {source_lang} to {target_lang}. "
            "Return ONLY the translated text. No explanations, no quotes, no extra formatting. "
            "Keep the same tone, register, and meaning. If the input is a sentence fragment, "
            "translate it as-is without completing it."
        )

    async def translate(self, text: str) -> str:
        response = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=self.system_prompt,
            messages=[{"role": "user", "content": text}],
        )
        return response.content[0].text.strip()


class OpenAICompatibleTranslator(TranslatorBase):
    """Works with any OpenAI-compatible API: CLIProxyAPI, LiteLLM, Ollama, vLLM, etc."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        source_lang: str = "English",
        target_lang: str = "Vietnamese",
    ):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.system_prompt = (
            f"You are a real-time translator. Translate {source_lang} to {target_lang}. "
            "Return ONLY the translated text. No explanations, no quotes, no extra formatting. "
            "Keep the same tone, register, and meaning. If the input is a sentence fragment, "
            "translate it as-is without completing it."
        )

    async def translate(self, text: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": text},
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()


class GeminiTranslator(TranslatorBase):
    def __init__(self, source_lang: str = "English", target_lang: str = "Vietnamese"):
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        self.system_prompt = (
            f"You are a real-time translator. Translate {source_lang} to {target_lang}. "
            "Return ONLY the translated text. No explanations, no quotes, no extra formatting. "
            "Keep the same tone, register, and meaning. If the input is a sentence fragment, "
            "translate it as-is without completing it."
        )

    async def translate(self, text: str) -> str:
        response = await asyncio.to_thread(
            self.model.generate_content, f"{self.system_prompt}\n\nTranslate:\n{text}"
        )
        return response.text.strip()


# ---------------------------------------------------------------------------
# Translation cache with debounced buffer translation
# ---------------------------------------------------------------------------

class TranslationManager:
    def __init__(self, translator: TranslatorBase):
        self.translator = translator
        self.cache: dict[str, str] = {}
        self._last_buffer_text: str = ""
        self._last_buffer_result: str = ""
        self._last_buffer_time: float = 0
        self.buffer_debounce_sec: float = 1.5

    async def translate_line(self, text: str) -> str:
        """Translate a completed segment (cached)."""
        text = text.strip()
        if not text:
            return ""
        if text in self.cache:
            return self.cache[text]
        try:
            result = await self.translator.translate(text)
            self.cache[text] = result
            return result
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return ""

    async def translate_buffer(self, text: str) -> str:
        """Translate in-progress buffer text (debounced to avoid API spam)."""
        text = text.strip()
        if not text or len(text) < 5:
            return ""
        if text == self._last_buffer_text:
            return self._last_buffer_result
        if text in self.cache:
            return self.cache[text]

        now = time.time()
        if now - self._last_buffer_time < self.buffer_debounce_sec:
            return self._last_buffer_result

        try:
            result = await self.translator.translate(text)
            self._last_buffer_text = text
            self._last_buffer_result = result
            self._last_buffer_time = now
            return result
        except Exception as e:
            logger.error(f"Buffer translation failed: {e}")
            return self._last_buffer_result


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

transcription_engine = None
translation_mgr: TranslationManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global transcription_engine, translation_mgr

    transcription_engine = TranscriptionEngine(config=wlk_config)

    if _translator_type == "openai":
        logger.info(f"Using OpenAI-compatible API: {_llm_base_url} model={_llm_model}")
        translator = OpenAICompatibleTranslator(
            base_url=_llm_base_url,
            api_key=_llm_api_key or "no-key",
            model=_llm_model,
            source_lang=_source_lang,
            target_lang=_target_lang,
        )
    elif _translator_type == "gemini":
        logger.info("Using Gemini (gemini-2.0-flash) for translation")
        translator = GeminiTranslator(source_lang=_source_lang, target_lang=_target_lang)
    else:
        logger.info("Using Claude (haiku-4.5) for translation")
        translator = ClaudeTranslator(source_lang=_source_lang, target_lang=_target_lang)

    translation_mgr = TranslationManager(translator)
    logger.info(f"Translation: {_source_lang} -> {_target_lang}")
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def get():
    return HTMLResponse(get_inline_ui_html())


async def handle_websocket_results(websocket: WebSocket, results_generator):
    """Intercepts transcription results, adds LLM translations, sends to client."""
    try:
        async for response in results_generator:
            data = response.to_dict()
            lines = data.get("lines", [])

            # Translate all completed lines in parallel (cached lines return instantly)
            if lines:
                tasks = []
                for line in lines:
                    text = line.get("text", "")
                    if text and text.strip() and line.get("speaker") != -2:
                        tasks.append((line, translation_mgr.translate_line(text)))

                if tasks:
                    results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
                    for (line, _), result in zip(tasks, results):
                        if isinstance(result, str):
                            line["translation"] = result

            # Translate in-progress buffer (debounced)
            buffer_text = data.get("buffer_transcription", "")
            if buffer_text:
                data["buffer_translation"] = await translation_mgr.translate_buffer(buffer_text)

            await websocket.send_json(data)

        logger.info("Results generator finished.")
        await websocket.send_json({"type": "ready_to_stop"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected while handling results.")
    except Exception as e:
        logger.exception(f"Error in results handler: {e}")


@app.websocket("/asr")
async def websocket_endpoint(websocket: WebSocket):
    global transcription_engine
    audio_processor = AudioProcessor(transcription_engine=transcription_engine)
    await websocket.accept()
    logger.info("WebSocket connection opened.")

    try:
        await websocket.send_json({"type": "config", "useAudioWorklet": bool(wlk_config.pcm_input)})
    except Exception as e:
        logger.warning(f"Failed to send config: {e}")

    results_generator = await audio_processor.create_tasks()
    websocket_task = asyncio.create_task(handle_websocket_results(websocket, results_generator))

    try:
        while True:
            message = await websocket.receive_bytes()
            await audio_processor.process_audio(message)
    except KeyError as e:
        if "bytes" in str(e):
            logger.warning("Client closed connection.")
        else:
            logger.error(f"Unexpected KeyError: {e}", exc_info=True)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up...")
        if not websocket_task.done():
            websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"Exception awaiting websocket_task: {e}")
        await audio_processor.cleanup()
        logger.info("Cleanup complete.")


def main():
    import uvicorn

    uvicorn_kwargs = {
        "app": app,
        "host": wlk_config.host,
        "port": wlk_config.port,
        "reload": False,
        "log_level": "info",
        "lifespan": "on",
    }

    if wlk_config.ssl_certfile and wlk_config.ssl_keyfile:
        uvicorn_kwargs["ssl_certfile"] = wlk_config.ssl_certfile
        uvicorn_kwargs["ssl_keyfile"] = wlk_config.ssl_keyfile
    if wlk_config.forwarded_allow_ips:
        uvicorn_kwargs["forwarded_allow_ips"] = wlk_config.forwarded_allow_ips

    uvicorn.run(**uvicorn_kwargs)


if __name__ == "__main__":
    main()
