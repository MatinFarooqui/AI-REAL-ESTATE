import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient


# ==========================================
# PROJECT ROOT
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("MONGO_URI is not configured in .env")


# ==========================================
# MONGODB CONNECTION
# ==========================================

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)


# ==========================================
# DATABASE
# ==========================================

db = client["AI_REAL_ESTATE"]


# ==========================================
# COLLECTIONS
# ==========================================

users_collection = db["users"]

properties_collection = db["properties"]

ml_properties_collection = db["ml_properties"]

favorites_collection = db["favorites"]

appointments_collection = db["appointments"]


# ==========================================
# CONNECTION TEST
# ==========================================

def test_connection():
    """Test MongoDB connection."""
    
    client.admin.command("ping")

    return True