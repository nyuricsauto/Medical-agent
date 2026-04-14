import json
import base64
import asyncio
from typing import Optional, Tuple, Dict, Any
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError
from config import (
    GEMINI_API_KEY,
    GEMINI_PROJECT_ID,
    GEMINI_LOCATION,
    GEMINI_TIMEOUT,
    logger
)
from system_prompts import get_receptionist_system_prompt, get_stt_system_prompt


# Initialize Gemini client
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


async def gemini_stt(audio_bytes: bytes, detected_language: str = "en") -> Tuple[str, str, str]:
    """
    Convert speech to text using Gemini 2.0 Flash.
    
    Args:
        audio_bytes: Raw PCM audio (mono, 16-bit, 8kHz)
        detected_language: Previously detected language
    
    Returns:
        (transcript, intent, language)
    """
    try:
        # Convert audio to base64
        audio_b64 = base64.b64encode(audio_bytes).decode()
        
        # Create model
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        # Prepare prompt
        stt_prompt = get_stt_system_prompt()
        
        # Create multimodal content
        content = [
            {
                "role": "user",
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": audio_b64
                        }
                    },
                    {"text": stt_prompt}
                ]
            }
        ]
        
        # Generate response with timeout
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, content),
            timeout=GEMINI_TIMEOUT
        )
        
        # Parse response
        response_text = response.text
        
        # Extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                transcript = result.get("transcript", "")
                intent = result.get("intent", "general_greeting")
                language = result.get("language", detected_language)
                return transcript, intent, language
            except json.JSONDecodeError:
                pass
        
        # Fallback: return raw text
        return response_text, "general_greeting", detected_language
    
    except asyncio.TimeoutError:
        logger.error("Gemini STT timeout")
        return "", "error", detected_language
    except GoogleAPIError as e:
        logger.error(f"Gemini STT error: {e}")
        return "", "error", detected_language
    except Exception as e:
        logger.error(f"Gemini STT unexpected error: {e}")
        return "", "error", detected_language


async def gemini_llm(
    conversation_history: list,
    language: str,
    patient_name: Optional[str] = None,
    patient_phone: Optional[str] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Generate agent response using Gemini 2.0 Flash LLM.
    
    Args:
        conversation_history: List of {"role": "user" | "assistant", "content": "..."}
        language: Detected language code
        patient_name: Patient name (if known)
        patient_phone: Patient phone (if known)
    
    Returns:
        (response_text, action, extracted_data)
    """
    try:
        # Build system prompt
        system_prompt = get_receptionist_system_prompt(language, patient_name, patient_phone)
        
        # Create model with system instruction
        model = genai.GenerativeModel(
            "gemini-2.0-flash-exp",
            system_instruction=system_prompt
        )
        
        # Format conversation for Gemini
        messages = []
        for msg in conversation_history[-10:]:  # Keep last 10 turns for context
            messages.append({
                "role": msg["role"],
                "parts": [{"text": msg["content"]}]
            })
        
        # Generate response with timeout
        response = await asyncio.wait_for(
            asyncio.to_thread(
                model.generate_content,
                messages,
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "max_output_tokens": 512
                }
            ),
            timeout=GEMINI_TIMEOUT
        )
        
        response_text = response.text
        
        # Extract structured data from response (JSON at end of response)
        import re
        json_match = re.search(r'<json>(.*?)</json>', response_text, re.DOTALL)
        
        action = "continue"
        extracted_data = {}
        
        if json_match:
            try:
                json_data = json.loads(json_match.group(1))
                action = json_data.get("action", "continue")
                extracted_data = json_data.get("data", {})
                # Remove JSON from spoken response
                response_text = response_text[:json_match.start()].strip()
            except json.JSONDecodeError:
                pass
        
        return response_text, action, extracted_data
    
    except asyncio.TimeoutError:
        logger.error("Gemini LLM timeout")
        return "Sorry, I'm having trouble understanding. Please try again.", "error", {}
    except GoogleAPIError as e:
        logger.error(f"Gemini LLM error: {e}")
        return "Sorry, I'm having trouble understanding. Please try again.", "error", {}
    except Exception as e:
        logger.error(f"Gemini LLM unexpected error: {e}")
        return "Sorry, I'm having trouble understanding. Please try again.", "error", {}
