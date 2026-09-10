from pathlib import Path

from flask import Flask, jsonify, request
import pandas as pd
import joblib

from property import calculate_rate


# ==========================================
# PROJECT PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "properties.csv"
MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v2.pkl"


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)


# ==========================================
# LOAD AI MODEL
# ==========================================

try:
    model_pipeline = joblib.load(MODEL_PATH)
    print("AI price prediction model loaded successfully.")
except Exception as e:
    model_pipeline = None
    print("Warning: AI model could not be loaded.")
    print(e)


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return "AI Real Estate Backend is working!"


# ==========================================
# PROPERTY RATE CALCULATOR
# ==========================================

@app.route("/property-rate")
def property_rate():

    city = request.args.get("city")
    property_type = request.args.get("property_type")
    bedrooms = request.args.get("bedrooms")

    price = request.args.get("price")
    area = request.args.get("area")

    if not price or not area:
        return jsonify({
            "error": "Price and area are required"
        }), 400

    try:
        price = float(price)
        area = float(area)
    except ValueError:
        return jsonify({
            "error": "Price and area must be numeric"
        }), 400

    if price <= 0 or area <= 0:
        return jsonify({
            "error": "Price and area must be greater than zero"
        }), 400

    rate = calculate_rate(price, area)

    return jsonify({
        "city": city,
        "property_type": property_type,
        "price": price,
        "area": area,
        "bedrooms": bedrooms,
        "rate_per_sqft": rate
    })


# ==========================================
# BASIC PROPERTY SEARCH
# ==========================================

@app.route("/search-properties")
def search_properties():

    city = request.args.get("city")
    property_type = request.args.get("property_type")
    budget = request.args.get("budget")
    area = request.args.get("area")
    bedrooms = request.args.get("bedrooms")

    if not city or not property_type or not budget or not area:
        return jsonify({
            "error": "City, property type, budget and area are required"
        }), 400

    try:
        budget = float(budget)
        area = float(area)

        if bedrooms:
            bedrooms = int(bedrooms)

    except ValueError:
        return jsonify({
            "error": "Invalid numeric value"
        }), 400

    data = pd.read_csv(DATA_PATH)

    filtered = data[
        (data["city"].str.lower() == city.lower()) &
        (data["property_type"].str.lower() == property_type.lower()) &
        (data["budget"] <= budget)
    ]

    if bedrooms:
        filtered = filtered[
            filtered["bedrooms"] >= bedrooms
        ]

    filtered = filtered[
        (filtered["area"] >= area * 0.8) &
        (filtered["area"] <= area * 1.2)
    ]

    results = filtered.to_dict(orient="records")

    return jsonify({
        "count": len(results),
        "properties": results
    })


# ==========================================
# AI PROPERTY RECOMMENDATION
# ==========================================

@app.route("/recommend-properties")
def recommend_properties():

    city = request.args.get("city")
    property_type = request.args.get("property_type")
    budget = request.args.get("budget")
    area = request.args.get("area")
    bedrooms = request.args.get("bedrooms")

    if not city or not property_type or not budget or not area:
        return jsonify({
            "error": "City, property type, budget and area are required"
        }), 400

    try:
        budget = float(budget)
        area = float(area)

        if budget <= 0 or area <= 0:
            return jsonify({
                "error": "Budget and area must be greater than zero"
            }), 400

        if bedrooms:
            bedrooms = int(bedrooms)

    except ValueError:
        return jsonify({
            "error": "Invalid numeric value"
        }), 400

    data = pd.read_csv(DATA_PATH)

    recommendations = []

    for _, property in data.iterrows():

        score = 0

        # CITY MATCH
        if str(property["city"]).lower() == city.lower():
            score += 30

        # PROPERTY TYPE MATCH
        if str(property["property_type"]).lower() == property_type.lower():
            score += 25

        # BUDGET MATCH
        property_budget = float(property["budget"])

        if property_budget <= budget:

            budget_difference = budget - property_budget

            if budget_difference <= budget * 0.10:
                score += 20

            elif budget_difference <= budget * 0.20:
                score += 15

            else:
                score += 10

        # AREA MATCH
        property_area = float(property["area"])

        area_difference = abs(property_area - area) / area

        if area_difference <= 0.10:
            score += 15

        elif area_difference <= 0.20:
            score += 10

        elif area_difference <= 0.30:
            score += 5

        # BEDROOM MATCH
        if bedrooms is not None:

            property_bedrooms = int(property["bedrooms"])

            if property_bedrooms == bedrooms:
                score += 10

            elif property_bedrooms >= bedrooms:
                score += 5

        recommendations.append({
            "id": int(property["id"]),
            "city": property["city"],
            "locality": property["locality"],
            "property_type": property["property_type"],
            "area": property_area,
            "budget": property_budget,
            "bedrooms": int(property["bedrooms"]),
            "bathrooms": int(property["bathrooms"]),
            "parking": int(property["parking"]),
            "furnishing": property["furnishing"],
            "property_age": int(property["property_age"]),
            "match_score": score
        })

    recommendations.sort(
        key=lambda x: x["match_score"],
        reverse=True
    )

    recommendations = recommendations[:5]

    return jsonify({
        "count": len(recommendations),
        "recommendations": recommendations
    })


# ==========================================
# PROPERTY DETAILS
# ==========================================

@app.route("/property/<int:property_id>")
def property_details(property_id):

    data = pd.read_csv(DATA_PATH)

    property_data = data[
        data["id"] == property_id
    ]

    if property_data.empty:
        return jsonify({
            "error": "Property not found"
        }), 404

    property_info = property_data.iloc[0].to_dict()

    return jsonify({
        "id": int(property_info["id"]),
        "city": property_info["city"],
        "locality": property_info["locality"],
        "property_type": property_info["property_type"],
        "area": float(property_info["area"]),
        "budget": float(property_info["budget"]),
        "bedrooms": int(property_info["bedrooms"]),
        "bathrooms": int(property_info["bathrooms"]),
        "parking": int(property_info["parking"]),
        "furnishing": property_info["furnishing"],
        "property_age": int(property_info["property_age"])
    })


# ==========================================
# AI PRICE PREDICTION
# ==========================================

@app.route("/predict-price", methods=["POST"])
def predict_price():

    if model_pipeline is None:
        return jsonify({
            "error": "AI price prediction model is not available"
        }), 500

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "JSON request body is required"
        }), 400

    required_fields = [
        "city",
        "locality",
        "property_type",
        "bhk",
        "area_sqft",
        "bathrooms",
        "balcony"
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in data
    ]

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "missing_fields": missing_fields
        }), 400

    try:
        prediction_input = pd.DataFrame([{
            "city": str(data["city"]),
            "locality": str(data["locality"]),
            "property_type": str(data["property_type"]),
            "bhk": float(data["bhk"]),
            "area_sqft": float(data["area_sqft"]),
            "bathrooms": float(data["bathrooms"]),
            "balcony": float(data["balcony"])
        }])

    except (ValueError, TypeError):
        return jsonify({
            "error": "Invalid numeric value"
        }), 400

    try:

        # V2 model contains the preprocessing pipeline
        prediction = model_pipeline.predict(
            prediction_input
        )

        predicted_price = float(prediction[0])

        return jsonify({
            "success": True,
            "predicted_price": round(predicted_price, 2),
            "currency": "INR"
        })

    except Exception as e:

        return jsonify({
            "error": "Prediction failed",
            "details": str(e)
        }), 500


# ==========================================
# START SERVER
# ==========================================

if __name__ == "__main__":
    app.run(debug=True)