from flask import Flask, jsonify, request
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


if __name__ == "__main__":
    app.run(debug=True)