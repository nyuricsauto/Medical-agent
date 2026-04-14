import os
import asyncio
import io
import base64
from typing import Optional
import httpx
from config import (
    SARVAM_API_KEY,
    SARVAM_MODEL,
    SARVAM_SPEAKER,
    SARVAM_SAMPLE_RATE,
    SARVAM_SPEED,
    SARVAM_TEMPERATURE,
    SARVAM_TIMEOUT,
    logger
)
import numpy as np
from scipy.io import wavfile


# Map language codes to Sarvam AI language codes (BCP-47 format)
LANGUAGE_CODE_MAP = {
    "hi": "hi-IN",  # Hindi
    "ta": "ta-IN",  # Tamil
    "te": "te-IN",  # Telugu
    "bn": "bn-IN",  # Bengali
    "mr": "mr-IN",  # Marathi
    "gu": "gu-IN",  # Gujarati
    "ml": "ml-IN",  # Malayalam
    "kn": "kn-IN",  # Kannada
    "pa": "pa-IN",  # Punjabi
    "ur": "ur-IN",  # Urdu
    "or": "or-IN",  # Odia
    "en": "en-IN",  # English (Indian)
}


async def sarvam_tts(text: str, language: str = "en") -> bytes:
    """
    Convert text to speech using Sarvam AI bulbul:v3.
    
    Args:
        text: Response text (max 2500 characters for bulbul:v3)
        language: Language code (hi, ta, te, bn, mr, gu, ml, kn, pa, ur, or, en)
    
    Returns:
        Audio bytes (WAV format)
    """
    try:
        # Map language code to BCP-47 format
        target_language_code = LANGUAGE_CODE_MAP.get(language, "en-IN")
        
        # Call Sarvam AI API
        url = "https://api.sarvam.ai/text-to-speech"
        headers = {
            "api-subscription-key": SARVAM_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "inputs": [text],
            "target_language_code": target_language_code,
            "speaker": SARVAM_SPEAKER,
            "model": SARVAM_MODEL,
            "sample_rate": SARVAM_SAMPLE_RATE,
            "speed": SARVAM_SPEED,
            "temperature": SARVAM_TEMPERATURE,
            "enable_timestamps": False,
            "normalize_english_text": False
        }
        
        async with httpx.AsyncClient(timeout=SARVAM_TIMEOUT) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            result = response.json()
        
        # Sarvam AI returns base64-encoded audio
        if "audio" in result:
            audio_base64 = result["audio"]
            audio_bytes = base64.b64decode(audio_base64)
            return audio_bytes
        else:
            logger.error("No audio in Sarvam AI response")
            return b""
    
    except asyncio.TimeoutError:
        logger.error("Sarvam AI TTS timeout")
        return b""
    except httpx.HTTPError as e:
        logger.error(f"Sarvam AI HTTP error: {e}")
        return b""
    except Exception as e:
        logger.error(f"Sarvam AI TTS error: {e}")
        return b""


def encode_mulaw(pcm_data: bytes, sample_rate: int = 8000) -> bytes:
    """
    Encode PCM audio to μ-law format (8-bit).
    
    Args:
        pcm_data: Raw PCM audio bytes (16-bit signed)
        sample_rate: Sample rate (default 8000 Hz)
    
    Returns:
        μ-law encoded bytes
    """
    try:
        # Convert bytes to numpy array (16-bit signed)
        pcm_array = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Convert to float and normalize to [-1, 1]
        pcm_float = pcm_array.astype(np.float32) / 32768.0
        
        # Apply μ-law encoding
        mu_law = np.sign(pcm_float) * np.log1p(255 * np.abs(pcm_float)) / np.log(256)
        
        # Convert to 8-bit unsigned
        mu_law_8bit = ((mu_law + 1) * 128).astype(np.uint8)
        
        return mu_law_8bit.tobytes()
    
    except Exception as e:
        logger.error(f"μ-law encoding error: {e}")
        return b""


def decode_mulaw(mu_law_data: bytes, sample_rate: int = 8000) -> bytes:
    """
    Decode μ-law audio to PCM format (16-bit).
    
    Args:
        mu_law_data: μ-law encoded bytes (8-bit)
        sample_rate: Sample rate (default 8000 Hz)
    
    Returns:
        PCM audio bytes (16-bit signed)
    """
    try:
        # Convert bytes to numpy array (8-bit unsigned)
        mu_law_array = np.frombuffer(mu_law_data, dtype=np.uint8)
        
        # Normalize to [-1, 1]
        mu_law_float = (mu_law_array.astype(np.float32) / 128.0) - 1.0
        
        # Apply μ-law decoding
        pcm_float = np.sign(mu_law_float) * (1.0 / 255.0) * (np.exp(np.abs(mu_law_float) * np.log(256)) - 1.0)
        
        # Convert to 16-bit signed
        pcm_16bit = (pcm_float * 32768.0).astype(np.int16)
        
        return pcm_16bit.tobytes()
    
    except Exception as e:
        logger.error(f"μ-law decoding error: {e}")
        return b""


def convert_wav_to_mulaw(wav_bytes: bytes, target_sample_rate: int = 8000) -> bytes:
    """
    Convert WAV audio to μ-law PCM (8kHz, mono).
    
    Args:
        wav_bytes: WAV audio bytes
        target_sample_rate: Target sample rate (default 8000 Hz)
    
    Returns:
        μ-law encoded bytes
    """
    try:
        import librosa
        
        # Load WAV and resample to 8kHz mono
        y, sr = librosa.load(io.BytesIO(wav_bytes), sr=target_sample_rate, mono=True)
        
        # Convert to 16-bit PCM
        pcm_16bit = (y * 32767.0).astype(np.int16)
        pcm_bytes = pcm_16bit.tobytes()
        
        # Encode to μ-law
        mulaw_bytes = encode_mulaw(pcm_bytes, target_sample_rate)
        
        return mulaw_bytes
    
    except ImportError:
        logger.error("librosa not installed for WAV conversion")
        return b""
    except Exception as e:
        logger.error(f"WAV to μ-law conversion error: {e}")
        return b""


def convert_mulaw_to_wav(mu_law_data: bytes, sample_rate: int = 8000) -> bytes:
    """
    Convert μ-law audio to WAV format for Gemini.
    
    Args:
        mu_law_data: μ-law encoded bytes
        sample_rate: Sample rate (default 8000 Hz)
    
    Returns:
        WAV file bytes
    """
    try:
        # Decode μ-law to PCM
        pcm_bytes = decode_mulaw(mu_law_data, sample_rate)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        wavfile.write(wav_buffer, sample_rate, np.frombuffer(pcm_bytes, dtype=np.int16))
        wav_buffer.seek(0)
        
        return wav_buffer.getvalue()
    
    except Exception as e:
        logger.error(f"μ-law to WAV conversion error: {e}")
        return b""
