# AI Receptionist Voice Agent for Medical Clinic

A production-ready voice AI agent for a medical clinic in India that handles inbound calls, appointment booking, rescheduling, cancellation, and general inquiries in multiple Indian languages.

## Features

- **Multilingual Support**: Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Malayalam, Kannada, Punjabi, Urdu, Oriya, and English
- **Real-time Voice Processing**: WebSocket-based audio streaming with low latency
- **Intelligent Conversation**: Powered by Google Gemini 2.0 Flash for STT and LLM reasoning
- **Natural TTS**: ElevenLabs multilingual_v2 for natural-sounding responses
- **Appointment Management**: Book, reschedule, and cancel appointments via n8n workflows
- **Conversation Logging**: All interactions logged to Google Sheets via n8n
- **Vobiz Integration**: Compatible with Vobiz Indian telephony API
- **Error Handling**: Comprehensive timeout handling and graceful fallbacks

## Architecture

```
Inbound Call (Vobiz)
    ↓
Python /answer endpoint (returns Voice XML with wss:// stream URL)
    ↓
WebSocket Server (receives raw audio, manages session)
    ↓
Gemini 2.0 Flash (STT + intent detection + LLM response generation)
    ↓
ElevenLabs (TTS for response text)
    ↓
n8n Webhook (on action: book/reschedule/cancel)
    ↓
Google Sheets (patient records) + Google Calendar (appointments) + Logging
    ↓
Confirmation aloud + conversation transcript logged
```

## Project Structure

```
project/
├── main.py                 # FastAPI app + /answer endpoint
├── websocket_handler.py    # WebSocket session management + audio processing loop
├── gemini_client.py        # Gemini 2.0 Flash (STT + LLM)
├── elevenlabs_client.py    # ElevenLabs TTS (multilingual_v2)
├── n8n_client.py           # n8n webhook caller (booking, logging, etc.)
├── system_prompts.py       # System prompt for Gemini (detailed receptionist instructions)
├── config.py               # Environment variables + settings
├── requirements.txt        # All dependencies
├── run.py                  # Startup script with ngrok tunnel + WS server
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Prerequisites

- Python 3.10 or higher
- Vobiz phone number and API key
- Google Cloud project with Gemini API enabled
- ElevenLabs account with API key
- n8n instance (self-hosted or cloud)
- ngrok account (for local development)

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
cd "Medical Receptionist/Agent"
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Vobiz Configuration
VOBIZ_AUTH_ID=your_vobiz_auth_id_here
VOBIZ_AUTH_TOKEN=your_vobiz_auth_token_here
VOBIZ_PHONE_NUMBER=+91XXXXXXXXXX

# Google Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_CLOUD_PROJECT_ID=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1

# ElevenLabs Configuration
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# n8n Configuration
N8N_WEBHOOK_BASE=http://localhost:5678/webhook/

# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# ngrok Configuration (for local development)
NGROK_AUTH_TOKEN=your_ngrok_auth_token_here
```

### 3. Configure ElevenLabs Voices

Edit `elevenlabs_client.py` to update the `LANGUAGE_VOICE_MAP` with your actual voice IDs from ElevenLabs:

```python
LANGUAGE_VOICE_MAP = {
    "hi": "your_hindi_voice_id",
    "ta": "your_tamil_voice_id",
    # ... etc
}
```

### 4. Set Up n8n Workflows

Create the following n8n workflows with webhook endpoints:

- **book**: Create appointment in Google Calendar and log to Sheets
- **reschedule**: Modify existing appointment
- **cancel**: Delete appointment
- **query_doctors**: Return available doctors and time slots
- **log_turn**: Log each conversation turn
- **log_final**: Log final conversation summary

Each workflow should accept a JSON payload with the relevant fields.

### 5. Configure Clinic Information

Edit `config.py` to update clinic details:

```python
CLINIC_NAME = "Your Clinic Name"
CLINIC_HOURS = "9 AM - 6 PM, Monday to Saturday"
CLINIC_LOCATION = "Your Address"
CLINIC_PHONE = "+91-80-XXXX-XXXX"
CLINIC_EMAIL = "appointments@clinic.example.com"

DOCTORS = {
    "general_medicine": ["Dr. Name 1", "Dr. Name 2"],
    # ... etc
}
```

## Running the Application

### Local Development with ngrok

```bash
python run.py
```

This will:
1. Start the FastAPI server on port 8000
2. Create an ngrok tunnel for public access
3. Display the public URL for Vobiz configuration

### Production Deployment

For production, deploy to a cloud provider (Render, Fly.io, AWS EC2) and:

1. Remove ngrok dependency
2. Set up proper domain with SSL certificate
3. Set `WS_URL` to your production WebSocket URL
4. Use environment variables for all secrets

Run without ngrok:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuring Vobiz

1. Log in to your Vobiz dashboard
2. Navigate to your phone number settings
3. Set the webhook URL to: `https://your-ngrok-url.ngrok.io/answer`
4. Ensure the webhook method is set to POST
5. Save and test

## API Endpoints

### POST /answer

Vobiz webhook endpoint for incoming calls. Returns Voice XML with WebSocket streaming URL.

**Query Parameters:**
- `From` / `from`: Caller phone number
- `CallSid` / `callSid`: Call session ID

**Response:** Voice XML with WebSocket stream URL

### WebSocket /ws

Real-time audio streaming endpoint for voice agent session.

**Query Parameters:**
- `call_id`: Call session ID
- `caller_id`: Caller phone number

### GET /health

Health check endpoint.

**Response:** JSON with service status

## Testing

### Test Call Flow

1. Start the server: `python run.py`
2. Call your Vobiz phone number
3. The agent will greet you in the detected language
4. Try booking an appointment:
   - "Hello, I want to book an appointment"
   - Provide your name and phone number
   - Select a doctor and time slot
   - Confirm the details

### Test Different Languages

The agent automatically detects the caller's language. Test with:
- Hindi: "नमस्ते, मैं अपॉइंटमेंट बुक करना चाहता हूं"
- Tamil: "வணக்கம், நான் ஒரு அப்பாயின்ட்மென்ட் எடுக்க விரும்புகிறேன்"
- Telugu: "హలో, నేను అపాయింట్‌మెంట్ బుక్ చేయాలనుకుంటున్నాను"

## Troubleshooting

### ngrok Tunnel Issues

- Ensure `NGROK_AUTH_TOKEN` is set correctly
- Check if ngrok is already running: `ngrok http 8000`
- Verify your ngrok account has active tunnels

### WebSocket Connection Errors

- Check firewall settings
- Verify Vobiz can reach your public URL
- Check server logs for connection errors

### API Timeouts

- Adjust timeout values in `config.py` if needed
- Check your API rate limits
- Verify network connectivity to external APIs

### Audio Quality Issues

- Ensure audio sample rate is 8kHz for Vobiz compatibility
- Check μ-law encoding/decoding functions
- Test with different voice settings in ElevenLabs

## Cost Estimates

Per 100 calls (approximate):
- Vobiz: ~$2–5 (calls)
- Gemini: ~$0.50–1 (STT + LLM)
- ElevenLabs: ~$0.50–1 (TTS)
- n8n: Included (self-hosted or free tier)
- **Total**: ~$3–7 per 100 calls (~$30–70 per 1000 calls)

## Security Considerations

- Never commit `.env` file to version control
- Use strong API keys and rotate them regularly
- Implement rate limiting in production
- Log all API calls for audit trails
- Use HTTPS for all webhook endpoints
- Validate all incoming request parameters

## Monitoring and Logging

The application logs all important events:
- Incoming calls
- WebSocket connections/disconnections
- API errors
- Conversation turns
- Action executions

For production monitoring, consider integrating with:
- Sentry for error tracking
- Prometheus for metrics
- CloudWatch or similar for log aggregation

## License

This project is provided as-is for medical clinic use. Modify as needed for your specific requirements.

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review server logs
3. Verify n8n workflow configurations
4. Test API endpoints individually

## Version History

- **v1.0.0** (April 2026) - Initial release with full multilingual support
