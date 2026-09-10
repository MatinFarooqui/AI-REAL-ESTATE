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
# PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "ml_properties_prepared.csv"
MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v4.pkl"


# ==========================================
# LOAD DATA
# ==========================================

data = pd.read_csv(DATA_PATH)

print("Dataset loaded:", data.shape)


# ==========================================
# KEEP REAL DATA FOR FAIR TESTING
# ==========================================

real_data = data[data["record_type"] == "real_dataset"].copy()
synthetic_data = data[data["record_type"] == "source_informed_synthetic"].copy()

print("Real records:", len(real_data))
print("Synthetic records:", len(synthetic_data))


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
    "balcony"
]

target = "price_inr"


X = real_data[features]
y = real_data[target]


# ==========================================
# TRAIN / TEST SPLIT
# ==========================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42
)


# ==========================================
# ADD SYNTHETIC AURANGABAD DATA TO TRAINING
# ==========================================

X_synthetic = synthetic_data[features]
y_synthetic = synthetic_data[target]

X_train = pd.concat([X_train, X_synthetic], ignore_index=True)
y_train = pd.concat([y_train, y_synthetic], ignore_index=True)

print("Training records:", len(X_train))
print("Testing records:", len(X_test))


# ==========================================
# LOG TRANSFORM TARGET
# ==========================================

y_train_log = np.log1p(y_train)


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
    "balcony"
]


preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
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
# RANDOM FOREST MODEL
# ==========================================

model = RandomForestRegressor(
    n_estimators=400,
    random_state=42,
    n_jobs=-1,
    min_samples_leaf=2,
    max_features="sqrt"
)


# ==========================================
# TRANSFORM FEATURES
# ==========================================

X_train_processed = preprocessor.fit_transform(X_train)
X_test_processed = preprocessor.transform(X_test)


# ==========================================
# TRAIN
# ==========================================

print("\nTraining V4 model...")

model.fit(X_train_processed, y_train_log)


# ==========================================
# PREDICT
# ==========================================

predicted_log = model.predict(X_test_processed)

predicted_price = np.expm1(predicted_log)


# ==========================================
# EVALUATION
# ==========================================

mae = mean_absolute_error(y_test, predicted_price)

rmse = np.sqrt(
    mean_squared_error(y_test, predicted_price)
)

r2 = r2_score(y_test, predicted_price)


print("\n===================================")
print("V4 MODEL RESULTS")
print("===================================")

print(f"MAE  : ₹{mae:,.2f}")
print(f"RMSE : ₹{rmse:,.2f}")
print(f"R²   : {r2:.4f}")

print("===================================")


# ==========================================
# SAVE COMPLETE PIPELINE
# ==========================================

pipeline = {
    "preprocessor": preprocessor,
    "model": model,
    "features": features,
    "target": target,
    "log_target": True
}

joblib.dump(pipeline, MODEL_PATH)

print("\nV4 model saved successfully:")
print(MODEL_PATH)