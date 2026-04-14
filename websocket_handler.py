import asyncio
import uuid
import os
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

from config import (
    AUDIO_SAMPLE_RATE,
    SILENCE_TIMEOUT,
    MAX_SILENCE_DURATION,
    SILENCE_FIRST_PROMPT_DELAY,
    SILENCE_SECOND_PROMPT_DELAY,
    SILENCE_HANGUP_DELAY,
    logger
)
from gemini_client import gemini_stt, gemini_llm
from tts_client import (
    sarvam_tts,
    encode_mulaw,
    decode_mulaw,
    convert_mulaw_to_wav,
    convert_wav_to_mulaw
)
from n8n_client import (
    log_conversation_turn,
    log_final_summary,
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    query_doctors
)


class SessionState:
    """Manages per-call session state."""
    
    def __init__(self, call_id: str, caller_id: str):
        self.call_id = call_id
        self.caller_id = caller_id
        self.conversation_history = []  # List of {"role": "user" | "assistant", "content": "..."}
        self.patient_name = None
        self.patient_phone = None
        self.selected_doctor = None
        self.selected_slot = None
        self.detected_language = "en"  # Default to English
        self.confirmed_details = False
        self.appointment_id = None
        self.last_activity = datetime.now()
        self.audio_buffer = b""
        self.silence_start = None
        self.silence_prompt_count = 0  # Track how many silence prompts sent
        self.last_silence_prompt_time = None
        self.awaiting_hangup_confirmation = False  # Track if we asked for hangup confirmation
        self.hangup_confirmed = False  # Track if caller confirmed they don't need more help
        # Call recording buffers
        self.incoming_audio_buffer = b""  # Buffer for caller's audio
        self.outgoing_audio_buffer = b""  # Buffer for agent's audio


async def handle_websocket(websocket: WebSocket, call_id: str, caller_id: str):
    """
    Main WebSocket handler for voice agent session.
    
    Loop:
    1. Receive audio chunk
    2. Accumulate audio (VAD or timeout-based)
    3. STT via Gemini → get transcript + intent
    4. LLM via Gemini → generate response text + action
    5. TTS via ElevenLabs → convert response to audio
    6. Stream audio back to Vobiz
    7. On action (book/reschedule/etc.), call n8n webhook
    8. Repeat until hangup
    """
    await websocket.accept()
    session = SessionState(call_id, caller_id)
    
    logger.info(f"New WebSocket connection for call {call_id} from {caller_id}")
    
    # Send initial greeting
    await send_greeting(websocket, session)
    
    try:
        while True:
            # Receive audio chunk from Vobiz
            data = await websocket.receive_bytes()
            
            if not data:
                logger.warning(f"Empty audio received for call {call_id}")
                break
            
            # Update activity timestamp and reset silence prompts
            session.last_activity = datetime.now()
            session.silence_prompt_count = 0
            session.last_silence_prompt_time = None
            
            # Decode audio (μ-law to PCM)
            audio_pcm = decode_mulaw(data)
            
            # Record incoming audio for call recording
            session.incoming_audio_buffer += audio_pcm
            
            # Accumulate audio into buffer
            session.audio_buffer += audio_pcm
            
            # Check for silence (simple timeout-based approach)
            if len(session.audio_buffer) > 0:
                # Start silence timer
                if session.silence_start is None:
                    session.silence_start = datetime.now()
                
                # If silence exceeds timeout, process the audio
                silence_duration = (datetime.now() - session.silence_start).total_seconds()
                if silence_duration >= SILENCE_TIMEOUT:
                    # Process the accumulated audio
                    await process_user_speech(websocket, session)
                    
                    # Reset buffer
                    session.audio_buffer = b""
                    session.silence_start = None
            
            # Check for extended silence and send prompts
            await check_silence_and_prompt(websocket, session)
            
            # Check for max silence (auto hangup)
            max_silence = (datetime.now() - session.last_activity).total_seconds()
            if max_silence >= MAX_SILENCE_DURATION:
                logger.info(f"Max silence exceeded for call {call_id}")
                if not session.awaiting_hangup_confirmation:
                    await ask_hangup_confirmation(websocket, session)
                else:
                    await send_hangup_message(websocket, session)
                    break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_id}")
    except Exception as e:
        logger.error(f"WebSocket error for call {call_id}: {e}")
    finally:
        # Save call recording
        await save_call_recording(session)
        # Log final summary
        await log_final_summary(session.__dict__)
        await websocket.close()
        logger.info(f"Closed WebSocket for call {call_id}")


async def send_greeting(websocket: WebSocket, session: SessionState):
    """Send initial greeting to caller."""
    greeting_text = "Hello, skin fertility institue मैं प्रिया बोल रही हूँ reception से। जी बताइए.. आप किस भाषा में बात करने में comfortable हैं - Hindi, English, Odia या कोई अन्य भाषा?"
    
    # Convert to audio
    audio_wav = await sarvam_tts(greeting_text, session.detected_language)
    
    if audio_wav:
        # Convert to μ-law and send
        audio_mulaw = convert_wav_to_mulaw(audio_wav)
        # Record outgoing audio for call recording
        session.outgoing_audio_buffer += audio_mulaw
        await websocket.send_bytes(audio_mulaw)
    
    # Add to conversation history
    session.conversation_history.append({
        "role": "assistant",
        "content": greeting_text,
        "timestamp": datetime.now().isoformat()
    })


async def check_silence_and_prompt(websocket: WebSocket, session: SessionState):
    """Check for extended silence and send prompts if needed."""
    silence_duration = (datetime.now() - session.last_activity).total_seconds()
    
    # Check if we need to send first prompt (5 seconds)
    if session.silence_prompt_count == 0 and silence_duration >= SILENCE_FIRST_PROMPT_DELAY:
        await send_silence_prompt(websocket, session)
        session.silence_prompt_count = 1
        session.last_silence_prompt_time = datetime.now()
    
    # Check if we need to send second prompt (8 seconds total: 5 + 3)
    elif session.silence_prompt_count == 1 and silence_duration >= (SILENCE_FIRST_PROMPT_DELAY + SILENCE_SECOND_PROMPT_DELAY):
        await send_silence_prompt(websocket, session)
        session.silence_prompt_count = 2
        session.last_silence_prompt_time = datetime.now()
    
    # Check if we need to hang up (11 seconds total: 5 + 3 + 3)
    elif session.silence_prompt_count == 2 and silence_duration >= (SILENCE_FIRST_PROMPT_DELAY + SILENCE_SECOND_PROMPT_DELAY + SILENCE_HANGUP_DELAY):
        logger.info(f"No response after 2 prompts for call {session.call_id}, hanging up")
        if not session.awaiting_hangup_confirmation:
            await ask_hangup_confirmation(websocket, session)
        else:
            await send_hangup_message(websocket, session)
        return True  # Signal to hangup
    
    return False


async def send_silence_prompt(websocket: WebSocket, session: SessionState):
    """Send 'Can you hear me?' prompt to caller."""
    prompt_text = "Can you hear me? Are you there?"
    
    # Convert to audio
    audio_wav = await sarvam_tts(prompt_text, session.detected_language)
    
    if audio_wav:
        # Convert to μ-law and send
        audio_mulaw = convert_wav_to_mulaw(audio_wav)
        # Record outgoing audio for call recording
        session.outgoing_audio_buffer += audio_mulaw
        await websocket.send_bytes(audio_mulaw)
    
    logger.info(f"Sent silence prompt for call {session.call_id} (count: {session.silence_prompt_count + 1})")


async def process_user_speech(websocket: WebSocket, session: SessionState):
    """Process accumulated user speech through STT → LLM → TTS pipeline."""
    if len(session.audio_buffer) < 1000:  # Too short, ignore
        return
    
    # Convert μ-law buffer to WAV for Gemini
    wav_audio = convert_mulaw_to_wav(session.audio_buffer, AUDIO_SAMPLE_RATE)
    
    if not wav_audio:
        logger.warning("Failed to convert audio to WAV")
        return
    
    # STT via Gemini
    transcript, intent, language = await gemini_stt(wav_audio, session.detected_language)
    
    if not transcript:
        logger.warning("No transcript received from STT")
        return
    
    session.detected_language = language
    logger.info(f"Transcript: {transcript} (Language: {language}, Intent: {intent})")
    
    # Check if we're awaiting hangup confirmation
    if session.awaiting_hangup_confirmation:
        # Check if caller said "no" or similar to confirm they don't need more help
        transcript_lower = transcript.lower()
        if any(word in transcript_lower for word in ["no", "nah", "nahi", "na", "nothing", "kuch nahi", "done", "finished"]):
            session.hangup_confirmed = True
            await send_hangup_message(websocket, session)
            return
        else:
            # Caller needs more help, continue conversation
            session.awaiting_hangup_confirmation = False
    
    # Add user transcript to history
    session.conversation_history.append({
        "role": "user",
        "content": transcript,
        "timestamp": datetime.now().isoformat()
    })
    
    # Generate agent response via LLM
    response_text, action, extracted_data = await gemini_llm(
        session.conversation_history,
        session.detected_language,
        session.patient_name,
        session.patient_phone
    )
    
    # Update session state from LLM output
    if "patient_name" in extracted_data:
        session.patient_name = extracted_data["patient_name"]
    if "patient_phone" in extracted_data:
        session.patient_phone = extracted_data["patient_phone"]
    if "doctor" in extracted_data:
        session.selected_doctor = extracted_data["doctor"]
    if "slot" in extracted_data:
        session.selected_slot = extracted_data["slot"]
    
    # Handle actions
    if action in ["book", "reschedule", "cancel", "query_doctors"]:
        await handle_action(websocket, session, action, extracted_data, response_text)
    else:
        # Just send the response
        await send_response(websocket, session, response_text, action)
    
    # Log turn to n8n
    await log_conversation_turn(session.__dict__, transcript, response_text, action)


async def handle_action(
    websocket: WebSocket,
    session: SessionState,
    action: str,
    extracted_data: Dict[str, Any],
    response_text: str
):
    """Handle backend actions (book, reschedule, cancel, query)."""
    result = {}
    
    if action == "book":
        result = await book_appointment(
            call_id=session.call_id,
            patient_name=session.patient_name or extracted_data.get("patient_name", ""),
            patient_phone=session.patient_phone or extracted_data.get("patient_phone", ""),
            doctor=session.selected_doctor or extracted_data.get("doctor", ""),
            slot=session.selected_slot or extracted_data.get("slot", ""),
            language=session.detected_language
        )
    
    elif action == "reschedule":
        result = await reschedule_appointment(
            call_id=session.call_id,
            patient_name=session.patient_name or "",
            patient_phone=session.patient_phone or "",
            old_slot=extracted_data.get("old_slot", ""),
            new_slot=extracted_data.get("new_slot", ""),
            language=session.detected_language
        )
    
    elif action == "cancel":
        result = await cancel_appointment(
            call_id=session.call_id,
            patient_name=session.patient_name or "",
            patient_phone=session.patient_phone or "",
            slot=session.selected_slot or extracted_data.get("slot", ""),
            language=session.detected_language
        )
    
    elif action == "query_doctors":
        result = await query_doctors(language=session.detected_language)
    
    # Update session with result
    if result.get("status") == "success":
        if action == "book":
            session.appointment_id = result.get("appointment_id")
            response_text += f" {result.get('confirmation_message', '')}"
        elif action == "reschedule":
            session.selected_slot = extracted_data.get("new_slot")
            response_text += f" {result.get('confirmation_message', '')}"
        elif action == "cancel":
            response_text += f" {result.get('confirmation_message', '')}"
        elif action == "query_doctors":
            # Append available doctors/slots to response
            doctors_info = result.get("doctors", [])
            if doctors_info:
                response_text += " Here are the available doctors: " + ", ".join(doctors_info)
    
    # Send final response
    await send_response(websocket, session, response_text, action)


async def send_response(websocket: WebSocket, session: SessionState, text: str, action: str):
    """Convert text to audio and send to caller."""
    # Add to conversation history
    session.conversation_history.append({
        "role": "assistant",
        "content": text,
        "action": action,
        "timestamp": datetime.now().isoformat()
    })
    
    # TTS: Convert response to audio
    audio_wav = await sarvam_tts(text, session.detected_language)
    
    if audio_wav:
        # Convert to μ-law and send
        audio_mulaw = convert_wav_to_mulaw(audio_wav)
        # Record outgoing audio for call recording
        session.outgoing_audio_buffer += audio_mulaw
        await websocket.send_bytes(audio_mulaw)
    else:
        logger.error("Failed to generate TTS audio")


async def ask_hangup_confirmation(websocket: WebSocket, session: SessionState):
    """Ask caller if they need any other help before hanging up."""
    confirmation_text = "Do you need any other help?"
    
    # Convert to audio
    audio_wav = await sarvam_tts(confirmation_text, session.detected_language)
    
    if audio_wav:
        # Convert to μ-law and send
        audio_mulaw = convert_wav_to_mulaw(audio_wav)
        # Record outgoing audio for call recording
        session.outgoing_audio_buffer += audio_mulaw
        await websocket.send_bytes(audio_mulaw)
    
    # Add to conversation history
    session.conversation_history.append({
        "role": "assistant",
        "content": confirmation_text,
        "timestamp": datetime.now().isoformat()
    })
    
    session.awaiting_hangup_confirmation = True


async def save_call_recording(session: SessionState):
    """Save combined call recording (incoming + outgoing audio) to WAV file."""
    try:
        # Create recordings directory if it doesn't exist
        recordings_dir = Path("recordings")
        recordings_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp and call ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"call_{session.call_id}_{timestamp}.wav"
        filepath = recordings_dir / filename
        
        # Combine incoming and outgoing audio buffers
        # For simplicity, we'll just save the incoming audio (caller's voice)
        # since that's usually what's needed for compliance/quality monitoring
        if len(session.incoming_audio_buffer) > 0:
            # Convert μ-law to WAV
            wav_audio = convert_mulaw_to_wav(session.incoming_audio_buffer, AUDIO_SAMPLE_RATE)
            
            if wav_audio:
                # Save to file
                with open(filepath, "wb") as f:
                    f.write(wav_audio)
                
                logger.info(f"Saved call recording to {filepath}")
            else:
                logger.warning("Failed to convert incoming audio to WAV for recording")
        else:
            logger.warning("No incoming audio to record")
    
    except Exception as e:
        logger.error(f"Failed to save call recording: {e}")


async def send_hangup_message(websocket: WebSocket, session: SessionState):
    """Send final message before hangup in the caller's language."""
    if session.detected_language == "hi":
        if session.appointment_id:
            message = "आपकी अपॉइंटमेंट की पुष्टि हो गई है। स्किन फर्टिलिटी इंस्टिट्यूट कॉल करने के लिए धन्यवाद। अच्छा दिन हो।"
        else:
            message = "स्किन फर्टिलिटी इंस्टिट्यूट कॉल करने के लिए धन्यवाद। अच्छा दिन हो।"
    elif session.detected_language == "or":
        if session.appointment_id:
            message = "ଆପଣଙ୍କର ଆପଣମେଣ୍ଟମେଣ୍ଟ ନିଶ୍ଚିତ ହୋଇଛି। ସ୍କିନ୍ ଫର୍ଟିଲିଟି ଇନଷ୍ଟିଚ୍ୟୁଟ୍ କଲ୍ କରିବାକୁ ଧନ୍ୟବାଦ୍। ଶୁଭ ଦିନ।"
        else:
            message = "ସ୍କିନ୍ ଫର୍ଟିଲିଟି ଇନଷ୍ଟିଚ୍ୟୁଟ୍ କଲ୍ କରିବାକୁ ଧନ୍ୟବାଦ୍। ଶୁଭ ଦିନ।"
    else:  # Default to English
        if session.appointment_id:
            message = "Thank you for calling Skin Fertility Institute. Your appointment is confirmed. Have a good day."
        else:
            message = "Thank you for calling Skin Fertility Institute. Have a good day."
    
    await send_response(websocket, session, message, "hangup")
