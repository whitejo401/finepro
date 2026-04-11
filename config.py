from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"

for d in [RAW_DIR, PROCESSED_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Defaults
DEFAULT_START = "2015-01-01"
CACHE_EXPIRE_DAYS = 1

# API Keys
DART_API_KEY = os.getenv("DART_API_KEY", "")
ECOS_API_KEY = os.getenv("ECOS_API_KEY", "")
DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")
MOLIT_API_KEY = os.getenv("MOLIT_API_KEY", "")
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
EIA_API_KEY = os.getenv("EIA_API_KEY", "")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "financial-data-bot/1.0")
