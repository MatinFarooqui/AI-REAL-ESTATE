
from flask import Flask, jsonify, request
import pandas as pd
from property import calculate_rate

app = Flask(__name__)


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

    price = float(price)
    area = float(area)

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

    budget = float(budget)
    area = float(area)

    data = pd.read_csv("../data/properties.csv")

    filtered = data[
        (data["city"].str.lower() == city.lower()) &
        (data["property_type"].str.lower() == property_type.lower()) &
        (data["budget"] <= budget)
    ]

    if bedrooms:
        bedrooms = int(bedrooms)

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

    # Load property dataset
    data = pd.read_csv("../data/properties.csv")

    recommendations = []

    for _, property in data.iterrows():

        score = 0

        # --------------------------------------
        # CITY MATCH - 30 POINTS
        # --------------------------------------

        if str(property["city"]).lower() == city.lower():
            score += 30

        # --------------------------------------
        # PROPERTY TYPE MATCH - 25 POINTS
        # --------------------------------------

        if str(property["property_type"]).lower() == property_type.lower():
            score += 25

        # --------------------------------------
        # BUDGET MATCH - 20 POINTS
        # --------------------------------------

        property_budget = float(property["budget"])

        if property_budget <= budget:

            budget_difference = budget - property_budget

            if budget_difference <= budget * 0.10:
                score += 20

            elif budget_difference <= budget * 0.20:
                score += 15

            else:
                score += 10

        # --------------------------------------
        # AREA MATCH - 15 POINTS
        # --------------------------------------

        property_area = float(property["area"])

        area_difference = abs(property_area - area) / area

        if area_difference <= 0.10:
            score += 15

        elif area_difference <= 0.20:
            score += 10

        elif area_difference <= 0.30:
            score += 5

        # --------------------------------------
        # BEDROOM MATCH - 10 POINTS
        # --------------------------------------

        if bedrooms is not None:

            property_bedrooms = int(property["bedrooms"])

            if property_bedrooms == bedrooms:
                score += 10

            elif property_bedrooms >= bedrooms:
                score += 5

        # --------------------------------------
        # ADD RECOMMENDATION
        # --------------------------------------

     
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

    # --------------------------------------
    # SORT BEST MATCH FIRST
    # --------------------------------------

    recommendations.sort(
        key=lambda x: x["match_score"],
        reverse=True
    )

    # Return top 5 recommendations
    recommendations = recommendations[:5]

    return jsonify({
        "count": len(recommendations),
        "recommendations": recommendations
    })


# ==========================================
# START SERVER
# ==========================================
# ==========================================
# PROPERTY DETAILS
# ==========================================

@app.route("/property/<int:property_id>")
def property_details(property_id):

    data = pd.read_csv("../data/properties.csv")

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

if __name__ == "__main__":
    app.run(debug=True)
