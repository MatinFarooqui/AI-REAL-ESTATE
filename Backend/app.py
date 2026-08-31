from flask import Flask, jsonify
from property import calculate_rate

app = Flask(__name__)


@app.route("/")
def home():
    return "AI Real Estate Backend is working!"


@app.route("/property-rate")
def property_rate():
    price = 5000000
    area = 1500

    rate = calculate_rate(price, area)

    return jsonify({
        "price": price,
        "area": area,
        "rate_per_sqft": rate
    })


if __name__ == "__main__":
    app.run(debug=True)