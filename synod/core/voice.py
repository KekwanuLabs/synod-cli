"""Voice input module for Synod - Speak your queries instead of typing.

This module provides voice-to-text functionality using:
- sounddevice for audio recording
- faster-whisper for local transcription (no API costs!)

Usage:
    from synod.core.voice import record_and_transcribe, is_voice_available

    if is_voice_available():
        text = record_and_transcribe()
"""

import sys
import time
from pathlib import Path
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
    from faster_whisper import WhisperModel
except ImportError:
    VOICE_AVAILABLE = False
    MISSING_DEPS.append("faster-whisper")


# Model configuration
DEFAULT_MODEL = "base.en"  # Good balance of speed and accuracy
MODEL_CACHE_DIR = Path.home() / ".cache" / "synod" / "whisper-models"

# Global model instance (lazy loaded)
_whisper_model: Optional["WhisperModel"] = None


def get_install_command() -> str:
    """Get the pip install command for voice dependencies."""
    if sys.platform == "darwin":
        # macOS may need portaudio
        return "brew install portaudio && pip install synod-cli[voice]"
    else:
        return "pip install synod-cli[voice]"


def is_voice_available() -> Tuple[bool, Optional[str]]:
    """Check if voice input is available.

    Returns:
        Tuple of (is_available, error_message)
    """
    if not VOICE_AVAILABLE:
        install_cmd = get_install_command()
        return False, f"Voice input requires additional dependencies.\nInstall with: {install_cmd}"
    return True, None


def _get_model_path() -> Path:
    """Get the path where models are cached."""
    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return MODEL_CACHE_DIR


def _load_whisper_model(model_name: str = DEFAULT_MODEL) -> "WhisperModel":
    """Load or get cached Whisper model.

    Downloads the model on first use (~140MB for base.en).
    """
    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    from synod.core.display import console

    model_path = _get_model_path()

    # Check if this is first download
    model_dir = model_path / f"models--Systran--faster-whisper-{model_name}"
    is_first_download = not model_dir.exists()

    if is_first_download:
        console.print(f"[dim]Downloading Whisper model ({model_name})...[/dim]")
        console.print(f"[dim]This only happens once. Model cached at: {model_path}[/dim]")

    try:
        # Use CPU with int8 quantization for best compatibility
        # GPU users can set CUDA_VISIBLE_DEVICES
        _whisper_model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            download_root=str(model_path),
        )

        if is_first_download:
            console.print("[green]Model downloaded successfully![/green]")

        return _whisper_model

    except Exception as e:
        console.print(f"[red]Failed to load Whisper model: {e}[/red]")
        raise


def _record_audio(
    duration: float = 10.0,
    sample_rate: int = 16000,
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    min_duration: float = 0.5,
) -> Optional["np.ndarray"]:
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


def _transcribe_local(audio: "np.ndarray", sample_rate: int = 16000) -> Optional[str]:
    """Transcribe audio using local Whisper model.

    Args:
        audio: Audio data as numpy array (float32, mono)
        sample_rate: Sample rate of the audio

    Returns:
        Transcribed text, or None on failure
    """
    from synod.core.display import console

    console.print("[dim]Transcribing...[/dim]")

    try:
        model = _load_whisper_model()

        # faster-whisper expects float32 audio
        # Ensure audio is in correct format
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Flatten if needed (should be 1D)
        audio = audio.flatten()

        # Transcribe
        segments, info = model.transcribe(
            audio,
            beam_size=5,
            language="en",
            vad_filter=True,  # Filter out silence
        )

        # Collect all segment texts
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts).strip()
        return text if text else None

    except Exception as e:
        console.print(f"[red]Transcription error: {e}[/red]")
        return None


def record_and_transcribe(max_duration: float = 30.0) -> Optional[str]:
    """Record audio from microphone and transcribe to text.

    This is the main entry point for voice input.
    Uses local Whisper model - no API costs!

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

    # Transcribe locally
    text = _transcribe_local(audio)

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


def get_model_info() -> dict:
    """Get information about the Whisper model.

    Returns:
        Dict with model name, path, and download status
    """
    model_path = _get_model_path()
    model_dir = model_path / f"models--Systran--faster-whisper-{DEFAULT_MODEL}"

    return {
        "model": DEFAULT_MODEL,
        "cache_dir": str(model_path),
        "downloaded": model_dir.exists(),
        "loaded": _whisper_model is not None,
    }
