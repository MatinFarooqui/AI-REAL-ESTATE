import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ==========================================
# AI REAL ESTATE - PRICE PREDICTION V2
# ==========================================

print("\n==========================================")
print("AI REAL ESTATE - PRICE PREDICTION V2")
print("==========================================")


# ==========================================
# LOAD DATASET
# ==========================================

data = pd.read_csv("../data/ml_properties_prepared.csv")

print("\nDataset loaded successfully.")
print("Total rows:", len(data))
print("Total columns:", len(data.columns))


# ==========================================
# SEPARATE REAL AND SYNTHETIC DATA
# ==========================================

real_data = data[
    data["record_type"] == "real_dataset"
].copy()

synthetic_data = data[
    data["record_type"] == "source_informed_synthetic"
].copy()


print("\nReal records:", len(real_data))
print(
    "Aurangabad source-informed records:",
    len(synthetic_data)
)


# ==========================================
# SPLIT REAL DATA
# ==========================================

real_train, real_test = train_test_split(
    real_data,
    test_size=0.20,
    random_state=42
)


print("\nReal training records:", len(real_train))
print("Real testing records:", len(real_test))


# ==========================================
# ADD AURANGABAD DATA TO TRAINING
# ==========================================

train_data = pd.concat(
    [
        real_train,
        synthetic_data
    ],
    ignore_index=True
)


print(
    "\nTraining records after augmentation:",
    len(train_data)
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
    "balcony"
]

target = "price_inr"


X_train = train_data[features]
y_train = train_data[target]

X_test = real_test[features]
y_test = real_test[target]


# ==========================================
# CATEGORICAL FEATURES
# ==========================================

categorical_features = [
    "city",
    "locality",
    "property_type"
]


# ==========================================
# NUMERICAL FEATURES
# ==========================================

numerical_features = [
    "bhk",
    "area_sqft",
    "bathrooms",
    "balcony"
]


# ==========================================
# PREPROCESSING
# ==========================================

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
            "numerical",

            "passthrough",

            numerical_features
        )

    ]
)


# ==========================================
# RANDOM FOREST MODEL
# ==========================================

model = RandomForestRegressor(

    n_estimators=300,

    random_state=42,

    n_jobs=-1,

    min_samples_leaf=2,

    max_features="sqrt"

)


# ==========================================
# COMPLETE PIPELINE
# ==========================================

pipeline = Pipeline(

    steps=[

        (
            "preprocessor",
            preprocessor
        ),

        (
            "model",
            model
        )

    ]

)


# ==========================================
# TRAIN MODEL
# ==========================================

print("\n==========================================")
print("TRAINING MODEL")
print("==========================================")

print("\nTraining Random Forest V2...")
print("Please wait...")


pipeline.fit(
    X_train,
    y_train
)


print("\nTraining completed successfully.")


# ==========================================
# PREDICTIONS
# ==========================================

print("\nGenerating predictions...")


predictions = pipeline.predict(
    X_test
)


# ==========================================
# EVALUATION
# ==========================================

mae = mean_absolute_error(
    y_test,
    predictions
)


rmse = mean_squared_error(
    y_test,
    predictions
) ** 0.5


r2 = r2_score(
    y_test,
    predictions
)


# ==========================================
# PERFORMANCE
# ==========================================

print("\n==========================================")
print("MODEL V2 PERFORMANCE")
print("==========================================")


print(
    f"MAE  : ₹{mae:,.0f}"
)


print(
    f"RMSE : ₹{rmse:,.0f}"
)


print(
    f"R²   : {r2:.4f}"
)


# ==========================================
# SAVE MODEL
# ==========================================

model_file = "real_estate_price_model_v2.pkl"


joblib.dump(
    pipeline,
    model_file
)


print("\n==========================================")
print("MODEL V2 SAVED")
print("==========================================")


print(
    f"File: ml/{model_file}"
)


# ==========================================
# COMPARISON
# ==========================================

print("\n==========================================")
print("MODEL COMPARISON")
print("==========================================")


print("V1 Random Forest R² : 0.4006")
print("Existing/target V2 reference R² : 0.4569")
print(f"Current training R² : {r2:.4f}")


if r2 > 0.4569:

    print("\nCurrent training improved over the reference R².")

elif r2 == 0.4569:

    print("\nCurrent training matched the reference R².")

else:

    print("\nCurrent training was below the reference R².")


print("\nPrice prediction model V2 training workflow is ready!")