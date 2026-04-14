import os
import asyncio
import io
from typing import Optional
import httpx
from config import (
    ELEVENLABS_API_KEY,
    ELEVENLABS_VOICE_ID,
    ELEVENLABS_TIMEOUT,
    logger
)
import numpy as np
import wave


# Map language codes to voice IDs (these are example IDs - replace with your actual voice IDs)
LANGUAGE_VOICE_MAP = {
    "hi": "IuIKNXQHqMYiNDzKrRkL",  # Hindi voice
    "ta": "eIE2ZDKdMOZLXKW3i4H6",  # Tamil voice
    "te": "jlH8kqYGExd9nPV3TlE0",  # Telugu voice
    "bn": "aYtx0HgHUPVqXe7JElvB",  # Bengali voice
    "mr": "eoU3dPf4PepE7iU0vkLv",  # Marathi voice
    "gu": "VQyPl9Wy7w8HdCgKKVVl",  # Gujarati voice
    "ml": "fXvOwh8Mwch0G0h9V2Og",  # Malayalam voice
    "kn": "6LFMqLl4Mf2YPWt4Qr2H",  # Kannada voice
    "pa": "8F7G9zUKhK8r0mXr5Xvj",  # Punjabi voice
    "ur": "i0pVVZMHLjN2pAqwzZLx",  # Urdu voice
    "or": "Xb7hHc8f6g5h4j3k2l1m",  # Oriya voice
    "en": "21m00Tcm4TlvDq8ikWAM",  # English voice (Rachel)
}


async def elevenlabs_tts(text: str, language: str = "en") -> bytes:
    """
    Convert text to speech using ElevenLabs multilingual_v2 via direct HTTP API.
    
    Args:
        text: Response text (ideally < 500 chars for low latency)
        language: Language code (hi, ta, te, bn, mr, gu, ml, kn, pa, ur, en)
    
    Returns:
        Audio bytes (MP3 format)
    """
    try:
        voice_id = ELEVENLABS_VOICE_ID
        
        # Call ElevenLabs API directly with httpx
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "use_speaker_boost": True
            }
        }
        
        async with httpx.AsyncClient(timeout=ELEVENLABS_TIMEOUT) as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            audio_bytes = response.content
        
        return audio_bytes
    
    except asyncio.TimeoutError:
        logger.error("ElevenLabs TTS timeout")
        return b""
    except httpx.HTTPError as e:
        logger.error(f"ElevenLabs HTTP error: {e}")
        return b""
    except Exception as e:
        logger.error(f"ElevenLabs TTS error: {e}")
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


def convert_mp3_to_mulaw(mp3_bytes: bytes, target_sample_rate: int = 8000) -> bytes:
    """
    Convert MP3 audio to μ-law PCM (8kHz, mono).
    
    Args:
        mp3_bytes: MP3 audio bytes
        target_sample_rate: Target sample rate (default 8000 Hz)
    
    Returns:
        μ-law encoded bytes
    """
    try:
        import librosa
        
        # Load MP3 and resample to 8kHz mono
        y, sr = librosa.load(io.BytesIO(mp3_bytes), sr=target_sample_rate, mono=True)
        
        # Convert to 16-bit PCM
        pcm_16bit = (y * 32767.0).astype(np.int16)
        pcm_bytes = pcm_16bit.tobytes()
        
        # Encode to μ-law
        mulaw_bytes = encode_mulaw(pcm_bytes, target_sample_rate)
        
        return mulaw_bytes
    
    except ImportError:
        logger.error("librosa not installed for MP3 conversion")
        return b""
    except Exception as e:
        logger.error(f"MP3 to μ-law conversion error: {e}")
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
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
        wav_buffer.seek(0)
        
        return wav_buffer.getvalue()
    
    except Exception as e:
        logger.error(f"μ-law to WAV conversion error: {e}")
        return b""
