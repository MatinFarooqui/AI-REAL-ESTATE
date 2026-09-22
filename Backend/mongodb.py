from pathlib import Path
import os

from dotenv import load_dotenv
from pymongo import MongoClient

try:
    import certifi
except ImportError as exc:
    raise RuntimeError("certifi is required for secure MongoDB TLS connections.") from exc

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI", "").strip()
if not MONGO_URI:
    raise ValueError("MONGO_URI is not configured in .env")

mongo_kwargs = {
    "serverSelectionTimeoutMS": 5000,
    "connectTimeoutMS": 5000,
    "socketTimeoutMS": 10000,
    "tlsCAFile": certifi.where(),
    "retryWrites": True,
}

client = MongoClient(MONGO_URI, **mongo_kwargs)

db = client["AI_REAL_ESTATE"]

# Primary collections
users_collection = db["users"]
properties_collection = db["properties"]
favorites_collection = db["favorites"]
conversations_collection = db["conversations"]
messages_collection = db["messages"]
offers_collection = db["offers"]
notifications_collection = db["notifications"]
reports_collection = db["reports"]
ml_properties_collection = db["ml_properties"]


def test_connection() -> bool:
    client.admin.command("ping")
    return True


# Indexes are intentionally small and aligned with the actual application queries.
try:
    users_collection.create_index("email", unique=True, sparse=True)
    users_collection.create_index("phone", unique=True, sparse=True)
    users_collection.create_index("email_verification_token_hash", sparse=True)

    properties_collection.create_index("property_id", unique=True)
    properties_collection.create_index([("owner_id", 1), ("created_at", -1)])
    properties_collection.create_index([("status", 1), ("expires_at", 1)])
    properties_collection.create_index([("state", 1), ("city", 1), ("locality", 1)])
    properties_collection.create_index("property_type")
    properties_collection.create_index("listing_type")

    favorites_collection.create_index([("user_id", 1), ("property_id", 1)], unique=True)

    conversations_collection.create_index("conversation_id", unique=True, sparse=True)
    conversations_collection.create_index([("property_id", 1), ("buyer_id", 1), ("owner_id", 1)])
    conversations_collection.create_index([("buyer_id", 1), ("updated_at", -1)])
    conversations_collection.create_index([("owner_id", 1), ("updated_at", -1)])

    messages_collection.create_index("message_id", unique=True, sparse=True)
    messages_collection.create_index([("conversation_id", 1), ("created_at", 1)])

    offers_collection.create_index("offer_id", unique=True, sparse=True)
    offers_collection.create_index([("property_id", 1), ("buyer_id", 1), ("created_at", -1)])
    offers_collection.create_index([("seller_id", 1), ("status", 1), ("created_at", -1)])

    notifications_collection.create_index("notification_id", unique=True, sparse=True)
    notifications_collection.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])

    reports_collection.create_index("report_id", unique=True, sparse=True)
    reports_collection.create_index([("property_id", 1), ("status", 1), ("created_at", -1)])
except Exception as error:
    # Index creation should never prevent the app from starting after an older DB schema exists.
    print("MongoDB index setup warning:", error)
