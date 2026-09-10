from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder


# ==========================================
# PROJECT PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent.parent  
DATA_PATH = BASE_DIR / "data" / "ml_properties_prepared.csv"
MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v5.pkl"


# ==========================================
# LOAD DATA
# ==========================================

data = pd.read_csv(DATA_PATH)

print("Dataset loaded:", data.shape)


# ==========================================
# SEPARATE REAL AND SYNTHETIC DATA
# ==========================================

real_data = data[
    data["record_type"] == "real_dataset"
].copy()

synthetic_data = data[
    data["record_type"] == "source_informed_synthetic"
].copy()

print("Real records:", len(real_data))
print("Synthetic records:", len(synthetic_data))


# ==========================================
# BASIC CLEANING
# ==========================================

numeric_columns = [
    "bhk",
    "area_sqft",
    "bathrooms",
    "balcony",
    "price_inr"
]

for column in numeric_columns:
    real_data[column] = pd.to_numeric(
        real_data[column],
        errors="coerce"
    )

    synthetic_data[column] = pd.to_numeric(
        synthetic_data[column],
        errors="coerce"
    )


real_data = real_data.dropna(
    subset=[
        "city",
        "locality",
        "property_type",
        "bhk",
        "area_sqft",
        "bathrooms",
        "balcony",
        "price_inr"
    ]
)

synthetic_data = synthetic_data.dropna(
    subset=[
        "city",
        "locality",
        "property_type",
        "bhk",
        "area_sqft",
        "bathrooms",
        "balcony",
        "price_inr"
    ]
)


# ==========================================
# TRAIN / TEST SPLIT
# ==========================================

train_real, test_real = train_test_split(
    real_data,
    test_size=0.20,
    random_state=42
)


# ==========================================
# BUILD LOCALITY PRICE BENCHMARK
# ONLY FROM TRAINING DATA
# ==========================================

train_real["train_price_per_sqft"] = (
    train_real["price_inr"] /
    train_real["area_sqft"]
)

locality_rate = (
    train_real
    .groupby(["city", "locality"])["train_price_per_sqft"]
    .median()
    .to_dict()
)


city_rate = (
    train_real
    .groupby("city")["train_price_per_sqft"]
    .median()
    .to_dict()
)


overall_rate = train_real[
    "train_price_per_sqft"
].median()


def add_engineered_features(df):

    df = df.copy()

    # Area-based size features
    df["area_per_bhk"] = (
        df["area_sqft"] /
        df["bhk"].replace(0, 1)
    )

    # Bathroom/BHK relationship
    df["bathrooms_per_bhk"] = (
        df["bathrooms"] /
        df["bhk"].replace(0, 1)
    )

    # Training-only locality benchmark
    df["locality_rate"] = [
        locality_rate.get(
            (city, locality),
            city_rate.get(city, overall_rate)
        )
        for city, locality in zip(
            df["city"],
            df["locality"]
        )
    ]

    # Estimated market benchmark price
    df["benchmark_price"] = (
        df["area_sqft"] *
        df["locality_rate"]
    )

    return df


# ==========================================
# FEATURE ENGINEERING
# ==========================================

X_train = add_engineered_features(train_real)

X_test = add_engineered_features(test_real)

X_synthetic = add_engineered_features(
    synthetic_data
)


# ==========================================
# FEATURES
# ==========================================

features = [
    "city",
    "locality",
    "property_type",
    "bhk",
    "area_sqft",
    "bathrooms",
    "balcony",
    "area_per_bhk",
    "bathrooms_per_bhk",
    "locality_rate",
    "benchmark_price"
]


target = "price_inr"


# ==========================================
# ADD SYNTHETIC DATA ONLY TO TRAINING
# ==========================================

X_train = pd.concat(
    [
        X_train[features],
        X_synthetic[features]
    ],
    ignore_index=True
)

y_train = pd.concat(
    [
        train_real[target],
        synthetic_data[target]
    ],
    ignore_index=True
)

X_test = X_test[features]

y_test = test_real[target]


print("Training records:", len(X_train))
print("Testing records:", len(X_test))


# ==========================================
# PREPROCESSING
# ==========================================

categorical_features = [
    "city",
    "locality",
    "property_type"
]

numeric_features = [
    "bhk",
    "area_sqft",
    "bathrooms",
    "balcony",
    "area_per_bhk",
    "bathrooms_per_bhk",
    "locality_rate",
    "benchmark_price"
]


preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(
                handle_unknown="ignore"
            ),
            categorical_features
        ),
        (
            "numeric",
            "passthrough",
            numeric_features
        )
    ]
)


# ==========================================
# RANDOM FOREST V5
# ==========================================

model = RandomForestRegressor(
    n_estimators=500,
    random_state=42,
    n_jobs=-1,
    min_samples_leaf=2,
    max_features=0.8
)


# ==========================================
# PREPROCESS
# ==========================================

X_train_processed = preprocessor.fit_transform(
    X_train
)

X_test_processed = preprocessor.transform(
    X_test
)


# ==========================================
# TRAIN
# ==========================================

print("\nTraining V5 model...")

model.fit(
    X_train_processed,
    y_train
)


# ==========================================
# PREDICTION
# ==========================================

predictions = model.predict(
    X_test_processed
)


# ==========================================
# EVALUATION
# ==========================================

mae = mean_absolute_error(
    y_test,
    predictions
)

rmse = np.sqrt(
    mean_squared_error(
        y_test,
        predictions
    )
)

r2 = r2_score(
    y_test,
    predictions
)


# ==========================================
# RESULTS
# ==========================================

print("\n===================================")
print("V5 MODEL RESULTS")
print("===================================")

print(
    f"MAE  : ₹{mae:,.2f}"
)

print(
    f"RMSE : ₹{rmse:,.2f}"
)

print(
    f"R²   : {r2:.4f}"
)

print("===================================")


# ==========================================
# SAVE MODEL
# ==========================================

pipeline = {
    "preprocessor": preprocessor,
    "model": model,
    "features": features,
    "locality_rate": locality_rate,
    "city_rate": city_rate,
    "overall_rate": overall_rate
}

joblib.dump(
    pipeline,
    MODEL_PATH
)

print("\nV5 model saved successfully:")

print(MODEL_PATH)