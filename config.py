import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8643518852:AAEFwcoNBY3mSxarFWe9d7VCf1AlqLI1pNk")
API_ID = int(os.getenv("API_ID", "28932643"))

API_HASH = os.getenv("API_HASH", "3fb38bb53a7d33fb42ea208c6f77830b")

OWNER_ID = int(os.getenv("OWNER_ID", "1816904396"))
DB_NAME = os.getenv("DB_NAME", "naka.db")
LOGGER_GROUP_ID = int(os.environ.get("LOG_GROUP_ID", -1004477347087))
CASAKU_BASE_URL = "https://api.casaku.id"

CASAKU_LICENSE_KEY = os.getenv(
    "CASAKU_LICENSE_KEY", "cashify_198d948ad09d0062ea82a01a4490dd881d7c1d689559322e096d97ea0bc91dda"
)

CASAKU_QRIS_ID = os.getenv(
    "CASAKU_QRIS_ID", "f737504f-8f5b-492b-9df5-231224f36472"
)
