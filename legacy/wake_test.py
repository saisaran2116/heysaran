#!/usr/bin/env python3
"""
Hey Saran - Wake Word Detector Diagnostic / Test Script
Tests the 'Hey Saran' wake word through your MacBook microphone.
Default: Listens for the spoken phrase 'Hey Saran' (powered by Sarvam AI Saaras STT).
Option (--onnx): Tests local openWakeWord neural network engine.
"""

import argparse
import os
import sys
import time
import warnings

# Suppress urllib3 LibreSSL deprecation warning on macOS
warnings.filterwarnings("ignore", message=".*urllib3 v2 only supports OpenSSL.*")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import speech_recognition as sr
from heybaby.integrations.sarvam import sarvam
from legacy.notifications import notify_success, notify_error


def test_phrase_mode():
    print("=" * 65)
    print("      HEY SARAN - WAKE WORD TEST ('Hey Saran')       ")
    print("=" * 65)
    print("[INFO] Engine : Sarvam AI Saaras Speech Engine (en-IN)")
    print("[INFO] Target : Say 'Hey Saran' into your microphone.")
    print("       Press Ctrl+C to stop.\n")

    recognizer = sr.Recognizer()

    try:
        while True:
            try:
                with sr.Microphone() as source:
                    print("[LISTENING] Speak 'Hey Saran' now...")
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(source, timeout=6, phrase_time_limit=6)

                print("[PROCESSING] Analyzing speech...")
                text = None
                if sarvam.is_available():
                    try:
                        wav_bytes = audio.get_wav_data(convert_rate=16000, convert_width=2)
                        text = sarvam.transcribe(wav_bytes)
                    except Exception as e:
                        print(f"[WARN] Sarvam STT error ({e}), falling back to Google STT...")

                if not text:
                    text = recognizer.recognize_google(audio, language="en-IN")

                clean_text = text.lower().strip()
                print(f"[HEARD]: \"{text}\"")

                if any(k in clean_text for k in ("hey saran", "hey sharan", "hey sarah", "hey siri", "siri", "hey anurag", "anurag", "saran", "sharan")):
                    print("\n" + "*" * 65)
                    print(f"[{time.strftime('%H:%M:%S')}] >>> WAKE WORD DETECTED! <<<")
                    print(f"Trigger matched: 'Hey Saran' (Captured text: '{text}')")
                    print("*" * 65 + "\n")
                    notify_success(f"Wake word detected: '{text}'", subtitle="Wake Word Test")
                else:
                    print("[INFO] Phrase did not match 'Hey Saran'. Try saying 'Hey Saran' clearly.\n")

            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                print("[INFO] Could not understand audio. Please speak a bit louder.\n")
            except sr.RequestError as e:
                print(f"[ERROR] Speech service error: {e}")
                time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Diagnostics stopped by user. Exiting cleanly.")


def test_openwakeword_mode():
    import numpy as np
    import pyaudio
    import openwakeword
    from openwakeword.model import Model

    THRESHOLD = 0.60
    COOLDOWN_SECONDS = 1.5
    CHUNK_SIZE = 1280
    SAMPLE_RATE = 16000

    print("=" * 65)
    print("   HEY SARAN - OPENWAKEWORD LOCAL ONNX TEST (ALEXA / ONNX)   ")
    print("=" * 65)

    custom_model = os.path.join("models", "hey_saran.onnx")
    if os.path.exists(custom_model):
        print(f"[INFO] Using custom model: {custom_model}")
        model = Model(wakeword_models=[custom_model], inference_framework="onnx")
        model_name = "hey_saran"
    else:
        print("[INFO] Custom 'models/hey_saran.onnx' not found.")
        print("[INFO] Using pretrained test model: 'alexa'")
        model = Model(wakeword_models=["alexa"], inference_framework="onnx")
        model_name = "alexa"

    audio = pyaudio.PyAudio()
    stream = audio.open(
        rate=SAMPLE_RATE,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )

    print(f"\n[READY] Listening for wake word: '{model_name}' (Threshold: {THRESHOLD:.2f})")
    print("        Speak the wake word into your microphone.")
    print("        Press Ctrl+C to stop.\n")

    last_detection = 0.0
    try:
        while True:
            data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)
            scores = model.predict(frame)
            now = time.time()

            for name, score in scores.items():
                if score >= THRESHOLD:
                    if now - last_detection >= COOLDOWN_SECONDS:
                        print(f"[{time.strftime('%H:%M:%S')}] >>> WAKE WORD DETECTED! <<< Model: {name} | Score: {score:.2f}")
                        notify_success(f"Wake word '{name}' detected (Score: {score:.2f})", subtitle="Wake Word Test")
                        last_detection = now
                        model.reset()
                    break
            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user.")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()


def main():
    parser = argparse.ArgumentParser(description="Hey Saran Wake Word Tester")
    parser.add_argument("--onnx", "--alexa", dest="onnx", action="store_true", help="Test local openWakeWord ONNX engine instead of 'Hey Saran' phrase mode")
    args = parser.parse_args()

    if args.onnx:
        test_openwakeword_mode()
    else:
        test_phrase_mode()


if __name__ == "__main__":
    main()
