"""
RealtyKey AI - Model Training & Calibration V6
Produces a leak-free, validated Random Forest model with geographic benchmark tables
for hierarchical fallback (Locality -> City -> State -> National).
"""

from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "ml_properties_prepared.csv"
MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v6.pkl"

print("=" * 60)
print("REALTYKEY AI - ML VALUATION TRAINING (V6)")
print("=" * 60)

# 1. Load Data
df = pd.read_csv(DATA_PATH)
print(f"Total dataset loaded: {len(df):,} records")

df["city"] = df["city"].astype(str).str.strip()
df["locality"] = df["locality"].astype(str).str.strip()
df["property_type"] = df["property_type"].astype(str).str.strip()

for col in ["bhk", "area_sqft", "bathrooms", "balcony", "price_inr"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# Clean out zero/erroneous values
df = df[(df["area_sqft"] >= 100) & (df["price_inr"] > 100000)].copy()

CITY_TO_STATE = {
    "Bangalore": "Karnataka",
    "Bengaluru": "Karnataka",
    "Pune": "Maharashtra",
    "Mumbai": "Maharashtra",
    "Thane": "Maharashtra",
    "Aurangabad": "Maharashtra",
    "Chhatrapati Sambhajinagar": "Maharashtra",
    "Nashik": "Maharashtra",
    "Nagpur": "Maharashtra",
    "New Delhi": "Delhi",
    "Delhi": "Delhi",
    "Chennai": "Tamil Nadu",
    "Kolkata": "West Bengal",
    "Hyderabad": "Telangana",
}
df["state"] = df["city"].map(CITY_TO_STATE).fillna("Other")

# 2. Split Real and Synthetic Data (Real for fair evaluation)
real_data = df[df["record_type"] == "real_dataset"].copy()
synth_data = df[df["record_type"] == "source_informed_synthetic"].copy()

print(f"Real records: {len(real_data):,}")
print(f"Source-informed synthetic records: {len(synth_data):,}")

features = [
    "city",
    "locality",
    "property_type",
    "bhk",
    "area_sqft",
    "bathrooms",
    "balcony",
]
target = "price_inr"

# 80/20 split on real records
train_real, test_real = train_test_split(
    real_data, test_size=0.20, random_state=42
)

# Augmented training dataset
train_full = pd.concat([train_real, synth_data], ignore_index=True)

print(f"Training set: {len(train_full):,} records")
print(f"Testing set: {len(test_real):,} records")

# 3. Preprocessing Pipeline
preprocessor = ColumnTransformer(
    transformers=[
        (
            "cat",
            OneHotEncoder(handle_unknown="ignore"),
            ["city", "locality", "property_type"],
        ),
        (
            "num",
            "passthrough",
            ["bhk", "area_sqft", "bathrooms", "balcony"],
        ),
    ]
)

X_train = train_full[features]
y_train = train_full[target]
X_test = test_real[features]
y_test = test_real[target]

X_train_proc = preprocessor.fit_transform(X_train)
X_test_proc = preprocessor.transform(X_test)

# 4. Train Model
print("\nFitting Random Forest Regressor...")
rf_model = RandomForestRegressor(
    n_estimators=300,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1,
)
rf_model.fit(X_train_proc, y_train)

# 5. Evaluate on Held-out Test Set
predictions = rf_model.predict(X_test_proc)

mae = mean_absolute_error(y_test, predictions)
rmse = float(np.sqrt(mean_squared_error(y_test, predictions)))
r2 = r2_score(y_test, predictions)

errors_pct = np.abs((y_test - predictions) / y_test)
med_ape = float(np.median(errors_pct) * 100)
within_10 = float((errors_pct <= 0.10).mean() * 100)
within_20 = float((errors_pct <= 0.20).mean() * 100)

print("\n" + "=" * 60)
print("HELD-OUT VALIDATION METRICS:")
print("=" * 60)
print(f"MAE                     : ₹{mae:,.0f}")
print(f"RMSE                    : ₹{rmse:,.0f}")
print(f"R² Score                : {r2:.4f}")
print(f"Median Abs % Error      : {med_ape:.2f}%")
print(f"Predictions within ±10% : {within_10:.2f}%")
print(f"Predictions within ±20% : {within_20:.2f}%")
print("=" * 60)

# 6. Extract Hierarchical Benchmark Rates (from train data only)
train_full["rate_sqft"] = train_full["price_inr"] / train_full["area_sqft"]

locality_rates = {}
for (c, l), group in train_full.groupby(["city", "locality"])["rate_sqft"]:
    locality_rates[(c.lower(), l.lower())] = {
        "median_rate": float(group.median()),
        "mean_rate": float(group.mean()),
        "count": int(group.count()),
        "p25": float(group.quantile(0.25)),
        "p75": float(group.quantile(0.75)),
    }

city_rates = {}
for c, group in train_full.groupby("city")["rate_sqft"]:
    city_rates[c.lower()] = {
        "median_rate": float(group.median()),
        "mean_rate": float(group.mean()),
        "count": int(group.count()),
        "p25": float(group.quantile(0.25)),
        "p75": float(group.quantile(0.75)),
    }

state_rates = {}
for s, group in train_full.groupby("state")["rate_sqft"]:
    state_rates[s.lower()] = {
        "median_rate": float(group.median()),
        "mean_rate": float(group.mean()),
        "count": int(group.count()),
    }

overall_median_rate = float(train_full["rate_sqft"].median())

# 7. Package and Save Model Bundle
bundle = {
    "version": "v6_calibrated",
    "preprocessor": preprocessor,
    "model": rf_model,
    "features": features,
    "metrics": {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "med_ape": float(med_ape),
        "within_10_pct": float(within_10),
        "within_20_pct": float(within_20),
    },
    "benchmarks": {
        "locality_rates": locality_rates,
        "city_rates": city_rates,
        "state_rates": state_rates,
        "overall_rate": overall_median_rate,
        "city_to_state": {k.lower(): v for k, v in CITY_TO_STATE.items()},
    },
}

joblib.dump(bundle, MODEL_PATH)
print(f"\nModel bundle saved successfully to:\n{MODEL_PATH}")
