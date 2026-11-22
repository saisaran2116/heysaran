#!/usr/bin/env python3
"""
Hey Saran - Sarvam AI Text-to-Speech Test Script
Demonstrates calling the Sarvam AI Bulbul TTS API to synthesize natural speech.
Saves the generated audio to 'sarvam_output.mp3'.
"""

def main():
    import base64
    import os
    import sys
    from dotenv import load_dotenv

    # Load SARVAM_API_KEY from .env (never hardcoded)
    load_dotenv()

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        print("[ERROR] SARVAM_API_KEY is not set in your .env file.")
        sys.exit(1)

    from sarvamai import SarvamAI

    print("[INFO] Initializing Sarvam AI client...")
    client = SarvamAI(api_subscription_key=api_key)

    text_to_speak = "Hello Saran! I am your macOS voice assistant, powered by Sarvam AI."
    output_file = "sarvam_output.mp3"

    print(f"[INFO] Synthesizing speech with Sarvam AI Bulbul...")
    print(f"       Text: \"{text_to_speak}\"")
    print(f"       Language: en-IN (Indian English)")

    try:
        response = client.text_to_speech.convert(
            text=text_to_speak,
            language_code="en-IN",
            model="bulbul:v3",
            speaker="kavya",
            output_audio_codec="mp3"
        )

        if response.audios and len(response.audios) > 0:
            audio_base64 = response.audios[0]
            audio_bytes = base64.b64decode(audio_base64)

            with open(output_file, "wb") as f:
                f.write(audio_bytes)

            print(f"[SUCCESS] Audio received from Sarvam AI!")
            print(f"          Saved to: {output_file} ({len(audio_bytes)} bytes)")
            print(f"          Playback command: afplay {output_file}")
        else:
            print("[WARN] Received empty audio response from Sarvam AI API.")

    except Exception as e:
        print(f"[ERROR] API call failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
