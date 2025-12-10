# settings.example.py - Template for settings.py
# Copy this file to settings.py and add your actual API keys

# Gemini API Keys
# Add multiple keys for load distribution and rate limit avoidance
# Each key will be used in rotation
GEMINI_API_KEYS = [
    "your-gemini-api-key-1",
    "your-gemini-api-key-2",
    "your-gemini-api-key-3",
    "your-gemini-api-key-4",
    "your-gemini-api-key-5",
]

# Whisper Model Configuration
WHISPER_MODEL_SIZE = "base"  # Options: tiny, base, small, medium, large
WHISPER_DEVICE = "cpu"       # Options: cpu, cuda
WHISPER_COMPUTE_TYPE = "int8"  # Options: int8, float16, float32

# Application Settings
DEBUG = True
HOST = "127.0.0.1"
PORT = 5000
