#!/usr/bin/env python3
"""
================================================================================
 Hey Saran - Sarvam AI Integration Service
================================================================================
Provides modular wrappers for:
1. Speech-to-Text (STT) via Sarvam Saaras (model: saaras:v3)
2. Text-to-Speech (TTS) via Sarvam Bulbul (model: bulbul:v3)
3. Conversational AI (Chat) via Sarvam 105B (model: sarvam-105b-conversations)

Security:
- Reads SARVAM_API_KEY from environment / .env. Never prints or commits the key.
- Graceful fallbacks for network errors, rate limits, and authentication failures.
================================================================================
"""

import base64
import io
import os
import sys
from typing import Optional

# Ensure .env is loaded
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Model configurations
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
SARVAM_TTS_MODEL = os.getenv("SARVAM_TTS_MODEL", "bulbul:v3")
SARVAM_CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b-conversations")
SARVAM_DEFAULT_SPEAKER = os.getenv("SARVAM_SPEAKER", "kavya")
SARVAM_LANGUAGE = os.getenv("SARVAM_LANGUAGE", "en-IN")


class SarvamService:
    """Encapsulates all Sarvam AI API interactions with safe error handling."""

    def __init__(self):
        self.api_key = os.getenv("SARVAM_API_KEY")
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initializes the official SarvamAI SDK client if API key is present."""
        if not self.api_key:
            print("[SARVAM] Notice: SARVAM_API_KEY is not set. Sarvam cloud features disabled.")
            return

        try:
            from sarvamai import SarvamAI
            self.client = SarvamAI(api_subscription_key=self.api_key)
            print("[SARVAM] Sarvam AI client initialized successfully.")
        except Exception as e:
            print(f"[SARVAM] Error initializing Sarvam AI SDK: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Returns True if the Sarvam AI client is configured and ready."""
        return self.client is not None

    # --------------------------------------------------------------------------
    # 1. Speech-to-Text (Saaras)
    # --------------------------------------------------------------------------
    def transcribe(self, wav_bytes: bytes, filename: str = "voice_command.wav") -> Optional[str]:
        """
        Transcribes in-memory WAV audio bytes using Sarvam Saaras API.
        Returns the transcribed text string or None on failure.
        """
        if not self.is_available() or not wav_bytes:
            return None

        try:
            audio_stream = io.BytesIO(wav_bytes)
            audio_stream.name = filename

            response = self.client.speech_to_text.transcribe(
                file=audio_stream,
                model=SARVAM_STT_MODEL,
                language_code=SARVAM_LANGUAGE
            )

            transcript = getattr(response, "transcript", "")
            if transcript:
                return transcript.strip()
            return None

        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "unauthorized" in err_msg.lower():
                print("[SARVAM STT ERROR] Authentication failed. Please check SARVAM_API_KEY.")
            elif "429" in err_msg or "quota" in err_msg.lower():
                print("[SARVAM STT ERROR] Quota or rate limit exceeded.")
            else:
                print(f"[SARVAM STT ERROR] Transcription failed: {e}")
            return None

    # --------------------------------------------------------------------------
    # 2. Text-to-Speech (Bulbul)
    # --------------------------------------------------------------------------
    def synthesize(self, text: str, speaker: Optional[str] = None) -> Optional[bytes]:
        """
        Converts text to speech audio bytes (MP3) using Sarvam Bulbul API.
        Returns raw MP3 bytes or None on failure.
        """
        if not self.is_available() or not text:
            return None

        active_speaker = speaker or SARVAM_DEFAULT_SPEAKER

        try:
            response = self.client.text_to_speech.convert(
                text=text,
                language_code=SARVAM_LANGUAGE,
                model=SARVAM_TTS_MODEL,
                speaker=active_speaker,
                output_audio_codec="mp3"
            )

            if response.audios and len(response.audios) > 0:
                return base64.b64decode(response.audios[0])
            return None

        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "unauthorized" in err_msg.lower():
                print("[SARVAM TTS ERROR] Authentication failed. Please check SARVAM_API_KEY.")
            elif "429" in err_msg or "quota" in err_msg.lower():
                print("[SARVAM TTS ERROR] Quota or rate limit exceeded.")
            else:
                print(f"[SARVAM TTS ERROR] Speech synthesis failed: {e}")
            return None

    # --------------------------------------------------------------------------
    # 3. Conversational AI Chat Completion (Sarvam 105B)
    # --------------------------------------------------------------------------
    def chat(self, user_prompt: str) -> Optional[str]:
        """
        Generates a concise, conversational answer for general knowledge / questions.
        Returns the text response string or None on failure.
        """
        if not self.is_available() or not user_prompt:
            return None

        system_message = (
            "You are Hey Saran, an intelligent and friendly MacBook voice assistant for Saran. "
            "Keep your answers clear, natural, and concise (1 to 2 sentences max), suitable for spoken voice output."
        )

        try:
            response = self.client.chat.completions(
                model=SARVAM_CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200
            )

            if response.choices and len(response.choices) > 0:
                message = response.choices[0].message
                content = getattr(message, "content", None)
                if content:
                    return content.strip()
            return None

        except Exception as e:
            err_msg = str(e)
            if "401" in err_msg or "unauthorized" in err_msg.lower():
                print("[SARVAM CHAT ERROR] Authentication failed. Please check SARVAM_API_KEY.")
            elif "429" in err_msg or "quota" in err_msg.lower():
                print("[SARVAM CHAT ERROR] Quota or rate limit exceeded.")
            else:
                print(f"[SARVAM CHAT ERROR] Chat completion failed: {e}")
            return None


# Global singleton instance for easy import across modules
sarvam = SarvamService()
