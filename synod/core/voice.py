"""Voice input module for Synod - Speak your queries instead of typing.

This module provides voice-to-text functionality using:
- sounddevice for audio recording
- OpenAI Whisper API for transcription

Usage:
    from synod.core.voice import record_and_transcribe, is_voice_available

    if is_voice_available():
        text = record_and_transcribe()
"""

import io
import sys
import time
from typing import Optional, Tuple

# Optional dependencies - graceful fallback if not installed
VOICE_AVAILABLE = True
MISSING_DEPS = []

try:
    import sounddevice as sd
except ImportError:
    VOICE_AVAILABLE = False
    MISSING_DEPS.append("sounddevice")

try:
    import numpy as np
except ImportError:
    VOICE_AVAILABLE = False
    MISSING_DEPS.append("numpy")

try:
    from scipy.io import wavfile
except ImportError:
    VOICE_AVAILABLE = False
    MISSING_DEPS.append("scipy")

try:
    import httpx
except ImportError:
    # httpx should always be available (synod dependency)
    VOICE_AVAILABLE = False
    MISSING_DEPS.append("httpx")


def get_install_command() -> str:
    """Get the pip install command for missing dependencies."""
    if sys.platform == "darwin":
        # macOS may need portaudio
        return "brew install portaudio && pip install sounddevice numpy scipy"
    else:
        return "pip install sounddevice numpy scipy"


def is_voice_available() -> Tuple[bool, Optional[str]]:
    """Check if voice input is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    if not VOICE_AVAILABLE:
        install_cmd = get_install_command()
        return False, f"Voice input requires additional dependencies.\nInstall with: {install_cmd}"
    return True, None


def _get_openai_key() -> Optional[str]:
    """Get OpenAI API key from Synod config (BYOK)."""
    try:
        from synod.core.config import load_config
        config = load_config()
        providers = config.get("providers", {})
        return providers.get("openai", {}).get("key")
    except Exception:
        return None


def _record_audio(
    duration: float = 10.0,
    sample_rate: int = 16000,
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    min_duration: float = 0.5,
) -> Optional[np.ndarray]:
    """Record audio from microphone with voice activity detection.

    Args:
        duration: Maximum recording duration in seconds
        sample_rate: Audio sample rate (16kHz for Whisper)
        silence_threshold: RMS threshold for silence detection
        silence_duration: Seconds of silence before stopping
        min_duration: Minimum recording duration

    Returns:
        Audio data as numpy array, or None if cancelled
    """
    from synod.core.display import console

    chunks = []
    silence_start = None
    recording_start = time.time()

    console.print("[dim]Recording... (speak now, pause to stop)[/dim]")

    def callback(indata, frames, time_info, status):
        nonlocal silence_start

        # Calculate RMS (volume level)
        rms = np.sqrt(np.mean(indata**2))

        # Track silence
        if rms < silence_threshold:
            if silence_start is None:
                silence_start = time.time()
        else:
            silence_start = None

        chunks.append(indata.copy())

    try:
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
            callback=callback,
            blocksize=int(sample_rate * 0.1),  # 100ms blocks
        ):
            while True:
                time.sleep(0.1)
                elapsed = time.time() - recording_start

                # Check max duration
                if elapsed >= duration:
                    console.print("[dim]Max duration reached[/dim]")
                    break

                # Check for silence (but only after minimum duration)
                if elapsed >= min_duration and silence_start is not None:
                    if time.time() - silence_start >= silence_duration:
                        break

        if not chunks:
            return None

        audio = np.concatenate(chunks)
        duration_recorded = len(audio) / sample_rate
        console.print(f"[dim]Recorded {duration_recorded:.1f}s of audio[/dim]")

        return audio

    except KeyboardInterrupt:
        console.print("[dim]Recording cancelled[/dim]")
        return None
    except Exception as e:
        console.print(f"[red]Recording error: {e}[/red]")
        return None


def _transcribe_with_openai(audio: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
    """Transcribe audio using OpenAI Whisper API.

    Args:
        audio: Audio data as numpy array
        sample_rate: Sample rate of the audio

    Returns:
        Transcribed text, or None on failure
    """
    from synod.core.display import console

    api_key = _get_openai_key()
    if not api_key:
        console.print(
            "[red]Voice input requires an OpenAI API key.[/red]\n"
            "[dim]Add your OpenAI key at: synod.run/dashboard/keys[/dim]"
        )
        return None

    # Convert to WAV bytes
    audio_int16 = (audio * 32767).astype(np.int16)
    wav_buffer = io.BytesIO()
    wavfile.write(wav_buffer, sample_rate, audio_int16)
    wav_buffer.seek(0)

    console.print("[dim]Transcribing...[/dim]")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", wav_buffer, "audio/wav")},
                data={"model": "whisper-1"},
            )

            if response.status_code != 200:
                error = response.json().get("error", {}).get("message", "Unknown error")
                console.print(f"[red]Transcription failed: {error}[/red]")
                return None

            text = response.json().get("text", "").strip()
            return text if text else None

    except httpx.TimeoutException:
        console.print("[red]Transcription timed out[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Transcription error: {e}[/red]")
        return None


def record_and_transcribe(max_duration: float = 30.0) -> Optional[str]:
    """Record audio from microphone and transcribe to text.

    This is the main entry point for voice input.

    Args:
        max_duration: Maximum recording duration in seconds

    Returns:
        Transcribed text, or None if cancelled/failed
    """
    from synod.core.display import console

    # Check dependencies
    available, error = is_voice_available()
    if not available:
        console.print(f"[red]{error}[/red]")
        return None

    # Record
    audio = _record_audio(duration=max_duration)
    if audio is None or len(audio) == 0:
        return None

    # Transcribe
    text = _transcribe_with_openai(audio)

    if text:
        console.print(f"[cyan]You said:[/cyan] {text}")

    return text


def check_microphone() -> bool:
    """Check if microphone is accessible.

    Returns:
        True if microphone is available
    """
    available, _ = is_voice_available()
    if not available:
        return False

    try:
        # Try to query default input device
        device_info = sd.query_devices(kind='input')
        return device_info is not None
    except Exception:
        return False
