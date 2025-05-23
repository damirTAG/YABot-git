import os
from pathlib    import Path
from dotenv     import load_dotenv

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Define default values and get environment variables
def get_env(key, default=None, required=False):
    value = os.getenv(key, default)
    if required and value is None:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value

# Application environment
# Options: development, testing, production
ENV = get_env("ENV", "testing")  
DEBUG = ENV == "testing"

# Bot configuration
BOT_TOKEN = get_env("TOKEN", required=True)
TEST_BOT_TOKEN = get_env("TEST_BOT_TOKEN")
ACTIVE_BOT_TOKEN = TEST_BOT_TOKEN if ENV == "testing" else BOT_TOKEN

# API tokens
GPT_TOKEN = get_env("GPT_TOKEN")
OPEN_AI_TOKEN = get_env("OPEN_AI_TOKEN")
AUDIO_MODEL_KEY = get_env("AUDIO_MODEL_KEY")
YANDEX_MUSIC_TOKEN = get_env("YANDEX_MUSIC_TOKEN")

# GitHub configuration
# GITHUB_TOKEN = get_env("GITHUB_TOKEN")
# GITHUB_USERNAME = get_env("GITHUB_USERNAME")

# Instagram credentials 
INST_USERNAME = get_env("INST_USERNAME")
INST_PASS = get_env("INST_PASS")

# Email configuration
CR_MAIL = get_env("CR_MAIL")
CR_PASS = get_env("CR_PASS")

# User IDs
ADMIN_USER_ID = int(get_env("ME", 0))

# Database configuration
DB_PATH = get_env("DB_PATH", "bot_settings.db")

# Paths
BASE_DIR = Path(__file__).parent.parent
# TEMP_DIR = BASE_DIR / "temp"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
# TEMP_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Feature flags
ENABLE_VOICE_RECOGNITION = get_env("ENABLE_VOICE_RECOGNITION", "true").lower() == "true"
ENABLE_AI_FEATURES = get_env("ENABLE_AI_FEATURES", "true").lower() == "true"
ENABLE_DOWNLOAD_FEATURES = get_env("ENABLE_DOWNLOAD_FEATURES", "true").lower() == "true"

# Create a dictionary of all settings for easy access
settings = {k: v for k, v in locals().items() if k.isupper()}