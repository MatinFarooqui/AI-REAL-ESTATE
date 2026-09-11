from pathlib import Path

import pandas as pd

from mongodb import ml_properties_collection


# ==========================================
# PROJECT PATH
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "ml_properties_prepared.csv"


# ==========================================
# LOAD MAIN DATASET
# ==========================================

print("Loading main ML dataset...")

data = pd.read_csv(DATA_PATH)

print(f"Records found: {len(data)}")


# ==========================================
# PREPARE DOCUMENTS
# ==========================================

documents = []

for _, row in data.iterrows():

    document = {
        "city": str(row["city"]),
        "locality": str(row["locality"]),
        "property_type": str(row["property_type"]),
        "bhk": float(row["bhk"]),
        "area_sqft": float(row["area_sqft"]),
        "bathrooms": float(row["bathrooms"]),
        "balcony": float(row["balcony"]),
        "price_inr": float(row["price_inr"]),
        "price_per_sqft": float(row["price_per_sqft"]),
        "data_source": str(row["data_source"]),
        "record_type": str(row["record_type"])
    }

    documents.append(document)


# ==========================================
# CLEAR OLD ML DATA
# ==========================================

print("Removing previous ML dataset from MongoDB...")

ml_properties_collection.delete_many({})


# ==========================================
# INSERT DATA IN BATCHES
# ==========================================

print("Importing main dataset...")

batch_size = 1000

for start in range(0, len(documents), batch_size):

    batch = documents[start:start + batch_size]

    ml_properties_collection.insert_many(batch)

    print(
        f"Imported {min(start + batch_size, len(documents))}"
        f"/{len(documents)} records"
    )


# ==========================================
# CREATE INDEXES
# ==========================================

print("Creating database indexes...")

ml_properties_collection.create_index("city")
ml_properties_collection.create_index("locality")
ml_properties_collection.create_index("property_type")
ml_properties_collection.create_index("price_inr")


# ==========================================
# FINAL RESULT
# ==========================================

total = ml_properties_collection.count_documents({})

print()
print("==========================================")
print("ML DATASET IMPORT COMPLETED")
print("==========================================")
print(f"Total records in MongoDB: {total}")
print("Collection: ml_properties")
print("==========================================")