
from pathlib import Path

import pandas as pd

from mongodb import properties_collection


# ==========================================
# PROJECT PATH
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "properties.csv"


# ==========================================
# LOAD CSV
# ==========================================

data = pd.read_csv(DATA_PATH)

print(f"CSV properties found: {len(data)}")


# ==========================================
# IMPORT PROPERTIES
# ==========================================

inserted = 0
skipped = 0

for _, row in data.iterrows():

    property_id = int(row["id"])

    # Prevent duplicate properties
    existing = properties_collection.find_one({
        "id": property_id
    })

    if existing:
        skipped += 1
        continue

    property_document = {
        "id": property_id,
        "city": str(row["city"]),
        "locality": str(row["locality"]),
        "property_type": str(row["property_type"]),
        "area": float(row["area"]),
        "budget": float(row["budget"]),
        "bedrooms": int(row["bedrooms"]),
        "bathrooms": int(row["bathrooms"]),
        "parking": int(row["parking"]),
        "furnishing": str(row["furnishing"]),
        "property_age": int(row["property_age"])
    }

    properties_collection.insert_one(property_document)

    inserted += 1


# ==========================================
# RESULT
# ==========================================

print()
print("MongoDB import completed.")
print(f"Inserted: {inserted}")
print(f"Skipped: {skipped}")
print(f"Total in CSV: {len(data)}")