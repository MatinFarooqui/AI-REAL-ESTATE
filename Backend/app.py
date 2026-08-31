
from flask import Flask, jsonify, request
import pandas as pd
from property import calculate_rate

app = Flask(__name__)


@app.route("/")
def home():
    return "AI Real Estate Backend is working!"


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


if __name__ == "__main__":
    app.run(debug=True)

