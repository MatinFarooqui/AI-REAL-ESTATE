import os
from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env from project root
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    print("ERROR: MONGO_URI not found in .env")
    exit()

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

    # Test connection
    client.admin.command("ping")

    print("MongoDB connection successful!")

    # Show databases
    print("Available databases:")
    for database in client.list_database_names():
        print("-", database)

except Exception as e:
    print("MongoDB connection failed.")
    print("Error:", e)