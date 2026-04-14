import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
VOBIZ_AUTH_ID = os.getenv("VOBIZ_AUTH_ID")
VOBIZ_AUTH_TOKEN = os.getenv("VOBIZ_AUTH_TOKEN")
VOBIZ_PHONE_NUMBER = os.getenv("VOBIZ_PHONE_NUMBER", "")

GEMINI_PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT_ID")
GEMINI_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Sarvam AI Configuration
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
SARVAM_MODEL = os.getenv("SARVAM_MODEL", "bulbul:v3")
SARVAM_SPEAKER = os.getenv("SARVAM_SPEAKER", "ritu")
SARVAM_SAMPLE_RATE = int(os.getenv("SARVAM_SAMPLE_RATE", "24000"))
SARVAM_SPEED = float(os.getenv("SARVAM_SPEED", "1.0"))
SARVAM_TEMPERATURE = float(os.getenv("SARVAM_TEMPERATURE", "0.6"))
SARVAM_TIMEOUT = float(os.getenv("SARVAM_TIMEOUT", "15.0"))

N8N_WEBHOOK_BASE = os.getenv("N8N_WEBHOOK_BASE", "http://localhost:5678/webhook/")

# Server Config
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))
NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
WS_URL = os.getenv("WS_URL", "")

# Clinic Info
CLINIC_NAME = "Skin Fertility Institute"
CLINIC_HOURS = "24 hours for calls, Doctor consultation: 10:00 AM – 1:00 PM and 4:00 PM – 7:00 PM (Monday to Sunday)"
CLINIC_LOCATION = "NH-6, near TVS Showroom, निगमानंद विहार, बरगढ़, ओडिशा, 768028"
CLINIC_CITY = "Bargarh, Odisha"
CLINIC_PHONE = "+91 9348425256"
CLINIC_WEBSITE = "https://skinandfertilityinstitute.com"
CLINIC_EMAIL = "skinfertilityinstitute@gmail.com"
CONSULTATION_FEE = "Rs. 400 per visit"

# Doctors
DOCTORS = {
    "dermatology": ["Dr. इप्सिता देबता (Dermatologist and Cosmetologist)"],
    "gynecology": ["Dr. शक्ति कुमार त्रिपाठी (Gynecologist and Fertility Specialist)"]
}

# Services
SERVICES = {
    "dermatology": ["Acne treatment", "Pigmentation treatment", "Hair fall treatment", "Skin infections", "Allergy treatment"],
    "cosmetology": ["Skin rejuvenation", "Chemical peel treatments", "Cosmetic dermatology procedures"],
    "hair": ["Hair transplant consultation", "Hair fall diagnosis and treatment"],
    "gynecology": ["Fertility consultation", "Infertility treatment", "Pregnancy consultation", "Women's reproductive health care"],
    "laboratory": ["Blood tests", "Basic diagnostic tests"]
}

# Audio Config
AUDIO_SAMPLE_RATE = 8000  # 8kHz for Vobiz
AUDIO_CHANNELS = 1  # Mono
SILENCE_TIMEOUT = 2.0  # Seconds of silence to detect end of speech
MAX_SILENCE_DURATION = 30.0  # Max seconds of silence before hangup

# Silence Prompt Config
SILENCE_FIRST_PROMPT_DELAY = 5.0  # Seconds of silence before first "Can you hear me?" prompt
SILENCE_SECOND_PROMPT_DELAY = 3.0  # Additional seconds of silence before second prompt (total 8s)
SILENCE_HANGUP_DELAY = 3.0  # Additional seconds of silence before hangup after second prompt (total 11s)

# API Timeouts
GEMINI_TIMEOUT = 15.0
SARVAM_TIMEOUT = 15.0
N8N_TIMEOUT = 15.0

# Logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
