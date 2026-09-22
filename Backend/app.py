from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import json
import os
import time

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.utils import secure_filename

from auth import auth_bp
from mongodb import (
    client,
    db,
    users_collection,
    properties_collection,
    favorites_collection,
    conversations_collection,
    messages_collection,
    offers_collection,
    notifications_collection,
    reports_collection,
)
from property import calculate_rate
from valuation_engine import estimate_property_value, get_model_metrics


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_FOLDER = BASE_DIR / "frontend"
DATA_PATH = BASE_DIR / "data" / "properties.csv"
UPLOAD_FOLDER = BASE_DIR / "uploads" / "properties"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGES = 20
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_REQUEST_SIZE = 220 * 1024 * 1024

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_USER_AGENT = "RealtyKeyAI/2.1 (college-capstone; support@realtykey.ai)"

app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    secret_key = os.urandom(32)
    print("WARNING: SECRET_KEY is not set; sessions reset when the server restarts.")
app.config["SECRET_KEY"] = secret_key
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_SIZE
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
app.config["JSON_SORT_KEYS"] = False
app.register_blueprint(auth_bp, url_prefix="/auth")

_cleanup_last_run = 0.0


# ============================================================
# HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def expiry_iso(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def clean_text(value) -> str:
    return str(value or "").strip()


def safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


CITY_STATE_MAP = {
    "aurangabad": "Maharashtra",
    "chhatrapati sambhajinagar": "Maharashtra",
    "pune": "Maharashtra",
    "mumbai": "Maharashtra",
    "thane": "Maharashtra",
    "nashik": "Maharashtra",
    "nagpur": "Maharashtra",
    "parbhani": "Maharashtra",
    "kolhapur": "Maharashtra",
    "solapur": "Maharashtra",
    "amravati": "Maharashtra",
    "bangalore": "Karnataka",
    "bengaluru": "Karnataka",
    "mysore": "Karnataka",
    "hyderabad": "Telangana",
    "chennai": "Tamil Nadu",
    "kolkata": "West Bengal",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "noida": "Uttar Pradesh",
    "gurgaon": "Haryana",
    "gurugram": "Haryana",
    "jaipur": "Rajasthan",
    "ahmedabad": "Gujarat",
}


def infer_state(city: str, default: str = "Maharashtra") -> str:
    return CITY_STATE_MAP.get(clean_text(city).lower(), default)


def parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def is_expired(expires_at: str | None) -> bool:
    dt = parse_iso(expires_at)
    return bool(dt and dt <= datetime.now(timezone.utc))


def normalize_property(record: dict) -> dict:
    item = dict(record)
    item["id"] = safe_int(item.get("property_id") or item.get("id")) or 0
    item["property_id"] = item["id"]
    item["city"] = clean_text(item.get("city")) or "Unknown City"
    item["locality"] = clean_text(item.get("locality")) or "City Center"
    item["state"] = clean_text(item.get("state")) or infer_state(item["city"], "Other")
    item["property_type"] = clean_text(item.get("property_type")) or "Apartment"
    item["listing_type"] = clean_text(item.get("listing_type")) or "Sale"
    if item["listing_type"].lower() == "sell":
        item["listing_type"] = "Sale"

    item["price"] = safe_float(item.get("price") or item.get("budget") or item.get("price_inr")) or 0.0
    item["budget"] = item["price"]
    item["area"] = safe_float(item.get("area") or item.get("area_sqft") or item.get("built_up_area") or item.get("plot_area")) or 0.0
    item["built_up_area"] = safe_float(item.get("built_up_area")) or (item["area"] if item["property_type"] != "Plot" else None)
    item["carpet_area"] = safe_float(item.get("carpet_area"))
    item["plot_area"] = safe_float(item.get("plot_area")) or (item["area"] if item["property_type"] == "Plot" else None)
    item["length"] = safe_float(item.get("length"))
    item["width"] = safe_float(item.get("width"))
    item["road_width"] = safe_float(item.get("road_width"))

    item["bhk"] = safe_int(item.get("bhk") or item.get("bedrooms")) or 0
    item["bedrooms"] = safe_int(item.get("bedrooms")) or item["bhk"]
    item["bathrooms"] = safe_int(item.get("bathrooms")) or (max(1, item["bedrooms"]) if item["property_type"] != "Plot" else 0)
    item["parking"] = safe_int(item.get("parking") or item.get("parking_spaces")) or 0
    item["facing"] = clean_text(item.get("facing")) or "Not Specified"
    item["furnishing"] = clean_text(item.get("furnishing")) or ("Not Applicable" if item["property_type"] == "Plot" else "Unfurnished")
    item["property_age"] = safe_int(item.get("property_age")) or 0
    item["floors"] = safe_int(item.get("floors") or item.get("number_of_floors"))
    item["floor_number"] = safe_int(item.get("floor_number"))
    item["total_floors"] = safe_int(item.get("total_floors"))
    item["floor_position"] = clean_text(item.get("floor_position"))
    item["amenities"] = item.get("amenities") if isinstance(item.get("amenities"), list) else []

    item["description"] = clean_text(item.get("description"))
    item["status"] = clean_text(item.get("status")) or "active"
    item["views"] = safe_int(item.get("views")) or 0
    item["images"] = item.get("images") if isinstance(item.get("images"), list) else []
    item["image_count"] = len(item["images"])

    item["owner_id"] = clean_text(item.get("owner_id"))
    item["owner_name"] = clean_text(item.get("owner_name")) or "Property Lister"
    item["owner_email"] = clean_text(item.get("owner_email"))

    item["latitude"] = safe_float(item.get("latitude"))
    item["longitude"] = safe_float(item.get("longitude"))
    item["location_address"] = clean_text(item.get("location_address")) or f"{item['locality']}, {item['city']}, {item['state']}"

    item["created_at"] = clean_text(item.get("created_at")) or now_iso()
    item["expires_at"] = clean_text(item.get("expires_at")) or expiry_iso(30)
    item["is_expired"] = is_expired(item["expires_at"])
    item["is_user_listing"] = bool(item.get("owner_id"))
    item["map_url"] = (
        f"https://www.openstreetmap.org/?mlat={item['latitude']}&mlon={item['longitude']}#map=18/{item['latitude']}/{item['longitude']}"
        if item.get("latitude") is not None and item.get("longitude") is not None else ""
    )

    item.pop("_id", None)
    item.pop("password_hash", None)
    item.pop("record_type", None)
    return item


def require_login() -> str | None:
    user_id = session.get("user_id")
    return clean_text(user_id) or None


def is_admin() -> bool:
    user_id = require_login()
    if not user_id:
        return False
    if session.get("user_role") == "admin":
        return True
    admin_email = clean_text(os.getenv("ADMIN_EMAIL")).lower()
    return bool(admin_email and clean_text(session.get("user_email")).lower() == admin_email)


def require_admin():
    if not is_admin():
        return jsonify({"success": False, "error": "Admin access required."}), 403
    return None


def allowed_image_extension(filename: str) -> bool:
    return bool(filename and "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS)


def validate_image(file):
    if not file or not file.filename:
        return False, "Invalid image file."
    if not allowed_image_extension(file.filename):
        return False, "Only JPG, JPEG, PNG, and WEBP images are allowed."
    if file.mimetype not in ALLOWED_IMAGE_MIMETYPES:
        return False, "Invalid image format. Supported formats: JPG, JPEG, PNG, WEBP."
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_SIZE:
        return False, "Each image must be 10 MB or smaller."
    return True, None


def csv_properties() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    try:
        df = pd.read_csv(DATA_PATH).fillna("")
        return [normalize_property(row) for row in df.to_dict(orient="records")]
    except Exception as error:
        print("CSV properties read error:", error)
        return []


def delete_property_assets(property_id: int):
    folder = UPLOAD_FOLDER / str(property_id)
    if not folder.exists():
        return
    for path in folder.glob("*"):
        try:
            path.unlink()
        except OSError:
            pass
    try:
        folder.rmdir()
    except OSError:
        pass


def purge_expired_listings(force: bool = False):
    """Delete expired user listings and associated assets; run at most every 30 seconds."""
    global _cleanup_last_run
    if not force and time.monotonic() - _cleanup_last_run < 30:
        return
    _cleanup_last_run = time.monotonic()
    try:
        active_docs = list(properties_collection.find({"status": {"$in": ["active", "approved"]}}, {"property_id": 1, "expires_at": 1}))
        expired_ids = [safe_int(d.get("property_id")) for d in active_docs if is_expired(d.get("expires_at"))]
        expired_ids = [x for x in expired_ids if x]
        for pid in expired_ids:
            properties_collection.delete_one({"property_id": pid})
            favorites_collection.delete_many({"property_id": pid})
            conversations_collection.delete_many({"property_id": pid})
            messages_collection.delete_many({"property_id": pid})
            offers_collection.delete_many({"property_id": pid})
            reports_collection.delete_many({"property_id": pid})
            delete_property_assets(pid)
        if expired_ids:
            print(f"Expired listings purged: {expired_ids}")
    except Exception as error:
        print("Expiry cleanup warning:", error)


def all_public_properties() -> list[dict]:
    purge_expired_listings()
    try:
        mongo_records = list(properties_collection.find({"status": {"$in": ["active", "approved"]}}, {"_id": 0}).sort("created_at", -1))
    except Exception as error:
        print("Mongo property read warning:", error)
        mongo_records = []

    user_items = []
    seen_ids = set()
    for record in mongo_records:
        item = normalize_property(record)
        if item["is_expired"]:
            continue
        item["is_user_listing"] = True
        user_items.append(item)
        seen_ids.add(item["id"])

    base = [p for p in csv_properties() if p["id"] not in seen_ids]
    for item in base:
        item["is_user_listing"] = False
    return user_items + base


def get_property_by_id(property_id: int) -> dict | None:
    purge_expired_listings()
    try:
        record = properties_collection.find_one({"property_id": property_id}, {"_id": 0})
        if record:
            item = normalize_property(record)
            return None if item["is_expired"] else item
    except Exception:
        pass
    for item in csv_properties():
        if item["id"] == property_id:
            return item
    return None


def next_property_id() -> int:
    max_csv = max([p["id"] for p in csv_properties()] or [0])
    try:
        latest = properties_collection.find_one({"property_id": {"$exists": True}}, sort=[("property_id", -1)])
        max_mongo = safe_int(latest.get("property_id")) if latest else 0
    except Exception:
        max_mongo = 0
    return max(max_csv, max_mongo or 0) + 1


def create_notification(user_id: str, n_type: str, title: str, body: str, link: str = ""):
    if not user_id:
        return
    try:
        notifications_collection.insert_one({
            "notification_id": uuid4().hex,
            "user_id": str(user_id),
            "type": n_type,
            "title": title,
            "body": body,
            "link": link,
            "read": False,
            "created_at": now_iso(),
        })
    except Exception as error:
        print("Notification creation warning:", error)


def find_user(user_id: str):
    if not user_id:
        return None
    from bson import ObjectId
    if ObjectId.is_valid(user_id):
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            return user
    return users_collection.find_one({"user_id": user_id})


def sanitize_query_value(value):
    return clean_text(value).lower()


# ============================================================
# BASIC ROUTES
# ============================================================

@app.route("/")
def home():
    return send_from_directory(FRONTEND_FOLDER, "index.html")


@app.route("/<path:filename>")
def serve_frontend(filename):
    path = FRONTEND_FOLDER / filename
    if path.is_file():
        return send_from_directory(FRONTEND_FOLDER, filename)
    return jsonify({"success": False, "error": "Resource not found."}), 404


@app.route("/api/health")
def health_check():
    model_metrics = get_model_metrics()
    return jsonify({
        "success": True,
        "service": "RealtyKey AI",
        "tagline": "Smarter Property Decisions",
        "status": "healthy",
        "ml_status": "active" if model_metrics.get("available", True) else "unavailable",
        "version": "2.1.0",
    })


@app.route("/mongodb-status")
def mongodb_status():
    try:
        client.admin.command("ping")
        return jsonify({"success": True, "connected": True})
    except Exception as error:
        return jsonify({"success": False, "connected": False, "error": str(error)}), 503


@app.route("/uploads/properties/<int:property_id>/<filename>")
def serve_property_image(property_id: int, filename: str):
    return send_from_directory(UPLOAD_FOLDER / str(property_id), filename)


# ============================================================
# SEARCH / LOCATION
# ============================================================

@app.route("/location-hierarchy")
def location_hierarchy():
    hierarchy: dict[str, dict[str, set[str]]] = {}
    for prop in all_public_properties():
        state = prop.get("state") or "Other"
        city = prop.get("city") or "Other"
        locality = prop.get("locality") or "Other"
        hierarchy.setdefault(state, {}).setdefault(city, set()).add(locality)
    serialized = {state: {city: sorted(locations) for city, locations in cities.items()} for state, cities in sorted(hierarchy.items())}
    states = sorted(serialized.keys())
    return jsonify({"success": True, "hierarchy": serialized, "states": states})


def attach_card_valuation(prop: dict) -> dict:
    """Attach the same explainable AI valuation used by the valuation page.

    Asking price is passed only for anomaly/status comparison; it never changes
    the generated estimated value itself.
    """
    try:
        value = estimate_property_value(
            city=prop.get("city", ""),
            locality=prop.get("locality", ""),
            property_type=prop.get("property_type", "Apartment"),
            area_sqft=prop.get("area", 0),
            bhk=prop.get("bhk", 0),
            bathrooms=prop.get("bathrooms", 0),
            asking_price=prop.get("price"),
            state=prop.get("state", ""),
        )
        prop["ai_valuation"] = value.get("estimated_price")
        prop["ai_valuation_lower"] = value.get("price_range", {}).get("lower")
        prop["ai_valuation_upper"] = value.get("price_range", {}).get("upper")
        prop["ai_valuation_rate"] = value.get("rate_per_sqft")
        prop["ai_valuation_basis"] = value.get("valuation_basis_short") or value.get("valuation_basis")
        prop["ai_valuation_level"] = value.get("fallback_level")
        prop["ai_valuation_confidence"] = value.get("confidence_level")
        prop["ai_valuation_model_weight"] = value.get("model_weight", 0)
        prop["ai_valuation_anomaly"] = value.get("anomaly")
    except Exception as error:
        prop["ai_valuation"] = None
        prop["ai_valuation_lower"] = None
        prop["ai_valuation_upper"] = None
        prop["ai_valuation_rate"] = None
        prop["ai_valuation_basis"] = "AI valuation unavailable for this property."
        prop["ai_valuation_level"] = None
        prop["ai_valuation_confidence"] = None
        prop["ai_valuation_model_weight"] = 0
        prop["ai_valuation_anomaly"] = None
        print(f"Card valuation warning for property {prop.get('id')}: {error}")
    return prop


@app.route("/search-properties")
def search_properties():
    args = request.args
    state_filter = sanitize_query_value(args.get("state"))
    city_filter = sanitize_query_value(args.get("city"))
    locality_filter = sanitize_query_value(args.get("locality"))
    listing_type = sanitize_query_value(args.get("listing_type"))
    property_type = sanitize_query_value(args.get("property_type"))
    facing = sanitize_query_value(args.get("facing"))
    furnishing = sanitize_query_value(args.get("furnishing"))

    min_price = safe_float(args.get("min_price") or args.get("min_budget"))
    max_price = safe_float(args.get("max_price") or args.get("budget") or args.get("price"))
    min_area = safe_float(args.get("min_area"))
    max_area = safe_float(args.get("max_area") or args.get("area"))
    bhk = safe_int(args.get("bhk") or args.get("bedrooms"))
    bathrooms = safe_int(args.get("bathrooms"))
    parking = safe_int(args.get("parking"))
    min_age = safe_int(args.get("min_age"))
    max_age = safe_int(args.get("max_age"))

    page = max(1, safe_int(args.get("page")) or 1)
    limit = min(60, max(1, safe_int(args.get("limit")) or 12))

    matched = []
    for prop in all_public_properties():
        if state_filter and state_filter not in prop["state"].lower():
            continue
        if city_filter and city_filter not in prop["city"].lower():
            continue
        if locality_filter and locality_filter not in prop["locality"].lower():
            continue
        if listing_type and listing_type != "all" and listing_type != prop["listing_type"].lower():
            continue
        if property_type and property_type != "all" and property_type not in prop["property_type"].lower():
            continue
        if facing and facing != "all" and facing not in prop["facing"].lower():
            continue
        if furnishing and furnishing != "all" and furnishing not in prop["furnishing"].lower():
            continue
        if min_price is not None and prop["price"] < min_price:
            continue
        if max_price is not None and max_price > 0 and prop["price"] > max_price:
            continue
        if min_area is not None and prop["area"] < min_area:
            continue
        if max_area is not None and max_area > 0 and prop["area"] > max_area:
            continue
        if bhk and bhk > 0 and prop["bedrooms"] < bhk:
            continue
        if bathrooms and bathrooms > 0 and prop["bathrooms"] < bathrooms:
            continue
        if parking and parking > 0 and prop["parking"] < parking:
            continue
        if min_age is not None and prop["property_age"] < min_age:
            continue
        if max_age is not None and prop["property_age"] > max_age:
            continue
        matched.append(prop)

    total = len(matched)
    pages = max(1, (total + limit - 1) // limit)
    page = min(page, pages)
    start = (page - 1) * limit
    page_items = [attach_card_valuation(dict(item)) for item in matched[start:start + limit]]
    return jsonify({
        "success": True,
        "count": total,
        "page": page,
        "limit": limit,
        "total_pages": pages,
        "properties": page_items,
    })


@app.route("/property-rate")
def property_rate():
    city = clean_text(request.args.get("city"))
    locality = clean_text(request.args.get("locality"))
    property_type = clean_text(request.args.get("property_type"))
    price = safe_float(request.args.get("price"))
    area = safe_float(request.args.get("area"))
    if not city:
        return jsonify({"success": False, "error": "City is required."}), 400
    if not property_type:
        return jsonify({"success": False, "error": "Property type is required."}), 400
    if price is None or price <= 0:
        return jsonify({"success": False, "error": "Valid positive price is required."}), 400
    if area is None or area <= 0:
        return jsonify({"success": False, "error": "Valid positive area in sq ft is required."}), 400
    return jsonify({
        "success": True,
        "city": city,
        "locality": locality,
        "property_type": property_type,
        "price": price,
        "area": area,
        "rate_per_sqft": round(calculate_rate(price, area), 2),
    })


@app.route("/reverse-geocode")
def reverse_geocode():
    lat = safe_float(request.args.get("lat"))
    lon = safe_float(request.args.get("lon"))
    if lat is None or lon is None:
        return jsonify({"success": False, "error": "Valid coordinates required."}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"success": False, "error": "Coordinates out of bounds."}), 400
    params = urlencode({"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 18, "addressdetails": 1})
    try:
        req = Request(f"{NOMINATIM_REVERSE_URL}?{params}", headers={"User-Agent": NOMINATIM_USER_AGENT, "Accept": "application/json"})
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        addr = payload.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("municipality") or addr.get("county") or ""
        locality = addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter") or addr.get("residential") or addr.get("city_district") or addr.get("village") or ""
        state = addr.get("state") or infer_state(city)
        return jsonify({"success": True, "state": state, "city": city, "locality": locality, "address": payload.get("display_name", ""), "latitude": lat, "longitude": lon})
    except Exception as error:
        return jsonify({"success": False, "error": f"Reverse geocoding unavailable: {error}"}), 503


@app.route("/location-search")
def location_search():
    query = clean_text(request.args.get("q"))
    city = clean_text(request.args.get("city"))
    if len(query) < 2:
        return jsonify({"success": True, "locations": []})
    search_query = f"{query}, {city}, India" if city else f"{query}, India"
    params = urlencode({"q": search_query, "format": "jsonv2", "addressdetails": 1, "limit": 6, "countrycodes": "in"})
    try:
        req = Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": NOMINATIM_USER_AGENT, "Accept": "application/json"})
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        locations = []
        for result in payload:
            addr = result.get("address", {})
            resolved_city = addr.get("city") or addr.get("town") or addr.get("municipality") or city
            resolved_state = addr.get("state") or infer_state(resolved_city)
            name = addr.get("suburb") or addr.get("neighbourhood") or addr.get("quarter") or addr.get("residential") or addr.get("village") or result.get("name") or result.get("display_name", "").split(",")[0]
            locations.append({"name": name, "city": resolved_city, "state": resolved_state, "address": result.get("display_name", ""), "latitude": safe_float(result.get("lat")), "longitude": safe_float(result.get("lon"))})
        return jsonify({"success": True, "locations": locations})
    except Exception:
        return jsonify({"success": True, "locations": []})


# ============================================================
# AI VALUATION
# ============================================================

@app.route("/predict-price", methods=["POST"])
def predict_price():
    data = request.get_json(silent=True) or {}
    city = clean_text(data.get("city"))
    locality = clean_text(data.get("locality"))
    property_type = clean_text(data.get("property_type")) or "Apartment"
    area = safe_float(data.get("area_sqft") or data.get("area"))
    bhk = safe_float(data.get("bhk") or data.get("bedrooms"))
    bathrooms = safe_float(data.get("bathrooms"))
    balcony = safe_float(data.get("balcony"))
    asking_price = safe_float(data.get("asking_price") or data.get("price"))
    state = clean_text(data.get("state")) or infer_state(city)
    if not city:
        return jsonify({"success": False, "error": "City is required."}), 400
    if not locality:
        return jsonify({"success": False, "error": "Locality is required."}), 400
    if area is None or area <= 0:
        return jsonify({"success": False, "error": "Valid property area in sq ft is required."}), 400
    try:
        return jsonify(estimate_property_value(city, locality, property_type, area, bhk, bathrooms, balcony, asking_price, state))
    except (ValueError, RuntimeError) as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        print("Valuation error:", error)
        return jsonify({"success": False, "error": "Unable to calculate AI valuation."}), 500


@app.route("/api/model-metrics")
def model_metrics():
    metrics = get_model_metrics()
    return jsonify({
        "success": True,
        "metrics": metrics,
        "r2_score": metrics.get("r2_score", metrics.get("r2")),
        "mae": metrics.get("mae"),
        "rmse": metrics.get("rmse"),
        "median_ape": metrics.get("median_ape", metrics.get("med_ape")),
        "within_10_pct": metrics.get("within_10_pct"),
        "within_20_pct": metrics.get("within_20_pct"),
    })


# ============================================================
# SMART RECOMMENDATIONS & COMPARISON
# ============================================================

def recommendation_score(prop, prefs):
    score = 0.0
    reasons = []
    location_weight = 35
    type_weight = 15
    budget_weight = 20
    area_weight = 15
    config_weight = 10
    amenity_weight = 5

    city = prefs.get("city")
    state = prefs.get("state")
    locality = prefs.get("locality")
    listing_type = prefs.get("listing_type")
    property_type = prefs.get("property_type")
    budget = prefs.get("budget")
    area = prefs.get("area")
    bhk = prefs.get("bedrooms")
    bathrooms = prefs.get("bathrooms")
    parking = prefs.get("parking")
    facing = prefs.get("facing")
    furnishing = prefs.get("furnishing")

    if locality:
        if locality == prop["locality"].lower():
            score += location_weight
            reasons.append(f"Exact locality match: {prop['locality']}")
        elif locality in prop["locality"].lower():
            score += location_weight * 0.75
            reasons.append(f"Locality is closely related to {locality.title()}")
    elif city and city in prop["city"].lower():
        score += location_weight
        reasons.append(f"City match: {prop['city']}")
    elif state and state in prop["state"].lower():
        score += location_weight * 0.45
        reasons.append(f"State match: {prop['state']}")

    if listing_type and listing_type != "all" and listing_type == prop["listing_type"].lower():
        score += type_weight * 0.55
        reasons.append(f"Listing type matches ({prop['listing_type']})")
    if property_type and property_type != "all" and property_type in prop["property_type"].lower():
        score += type_weight * 0.45
        reasons.append(f"Property type matches ({prop['property_type']})")

    if budget and budget > 0:
        ratio = prop["price"] / budget
        if ratio <= 1:
            score += budget_weight * max(0.35, 1 - max(0, (1 - ratio)) * 0.7)
            reasons.append(f"Within the stated budget of ₹{budget:,.0f}")
        elif ratio <= 1.10:
            score += budget_weight * 0.35
            reasons.append("Slightly above budget but within a 10% range")

    if area and area > 0:
        if prop["area"] >= area:
            score += area_weight
            reasons.append(f"Area meets the requested {area:,.0f} sq ft minimum")
        elif prop["area"] >= area * 0.9:
            score += area_weight * 0.5
            reasons.append("Area is close to the requested size")

    if bhk and bhk > 0 and prop["bedrooms"] >= bhk:
        score += config_weight * 0.55
        reasons.append(f"Offers at least {bhk} BHK")
    if bathrooms and bathrooms > 0 and prop["bathrooms"] >= bathrooms:
        score += config_weight * 0.25
        reasons.append(f"Has at least {bathrooms} bathrooms")
    if parking and parking > 0 and prop["parking"] >= parking:
        score += amenity_weight * 0.4
        reasons.append(f"Has {prop['parking']} parking space(s)")
    if facing and facing != "all" and facing in prop["facing"].lower():
        score += amenity_weight * 0.25
        reasons.append(f"Facing preference: {prop['facing']}")
    if furnishing and furnishing != "all" and furnishing in prop["furnishing"].lower():
        score += amenity_weight * 0.35
        reasons.append(f"Furnishing preference: {prop['furnishing']}")

    if not reasons:
        reasons.append("Active property available in the marketplace")
    return round(min(100.0, max(0.0, score)), 1), reasons


@app.route("/recommend-properties")
def recommend_properties():
    prefs = {
        "city": sanitize_query_value(request.args.get("city")),
        "state": sanitize_query_value(request.args.get("state")),
        "locality": sanitize_query_value(request.args.get("locality")),
        "listing_type": sanitize_query_value(request.args.get("listing_type")),
        "property_type": sanitize_query_value(request.args.get("property_type")),
        "budget": safe_float(request.args.get("budget")),
        "area": safe_float(request.args.get("area")),
        "bedrooms": safe_int(request.args.get("bedrooms")),
        "bathrooms": safe_int(request.args.get("bathrooms")),
        "parking": safe_int(request.args.get("parking")),
        "facing": sanitize_query_value(request.args.get("facing")),
        "furnishing": sanitize_query_value(request.args.get("furnishing")),
    }
    candidates = []
    for prop in all_public_properties():
        score, reasons = recommendation_score(prop, prefs)
        prop["match_score"] = score
        prop["why_match"] = reasons
        candidates.append(prop)
    candidates.sort(key=lambda p: (-p["match_score"], abs((p["price"] - prefs["budget"]) if prefs["budget"] else 0), p["id"]))
    recommendations = [attach_card_valuation(dict(item)) for item in candidates[:16]]
    return jsonify({"success": True, "count": len(candidates), "recommendations": recommendations})


@app.route("/api/compare-properties", methods=["POST"])
def compare_properties():
    data = request.get_json(silent=True) or {}
    ids = data.get("property_ids")
    if not isinstance(ids, list) or len(ids) < 2:
        return jsonify({"success": False, "error": "Select at least 2 properties to compare."}), 400
    seen = set()
    items = []
    for raw_id in ids[:4]:
        pid = safe_int(raw_id)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        prop = get_property_by_id(pid)
        if not prop:
            continue
        try:
            val = estimate_property_value(prop["city"], prop["locality"], prop["property_type"], prop["area"], prop["bhk"], prop["bathrooms"], asking_price=prop["price"], state=prop["state"])
            prop["ai_valuation"] = val.get("estimated_price")
            prop["ai_diff"] = prop["price"] - val.get("estimated_price", prop["price"])
            prop["ai_status"] = val.get("anomaly", {}).get("status", "No anomaly detected")
            prop["ai_confidence"] = val.get("confidence_level")
            prop["ai_basis"] = val.get("valuation_basis_short") or val.get("valuation_basis")
            prop["ai_valuation_lower"] = val.get("price_range", {}).get("lower")
            prop["ai_valuation_upper"] = val.get("price_range", {}).get("upper")
        except Exception:
            prop["ai_valuation"] = None
            prop["ai_diff"] = None
            prop["ai_status"] = "Estimate unavailable"
            prop["ai_confidence"] = None
            prop["ai_basis"] = None
            prop["ai_valuation_lower"] = None
            prop["ai_valuation_upper"] = None
        items.append(prop)
    if len(items) < 2:
        return jsonify({"success": False, "error": "At least 2 valid properties are required for comparison."}), 400
    return jsonify({"success": True, "count": len(items), "properties": items})


# ============================================================
# AI ASSISTANT
# ============================================================

def ai_assistant():
    """
    Simple customer-facing RealtyKey AI assistant.
    Deterministic and safe for the college project.
    """

    try:
        data = request.get_json(silent=True) or {}

        message = str(
            data.get("message") or ""
        ).strip()

        text = " ".join(
            message.lower().split()
        )

        if not text:
            return jsonify({
                "success": False,
                "error": "Message is required."
            }), 400

        # ----------------------------------------------------
        # LIST PROPERTY
        # ----------------------------------------------------

        if (
            "how do i list a property" in text
            or "how to list a property" in text
            or "how can i list a property" in text
            or "list a property" in text
        ):
            reply = (
                "To list a property on RealtyKey AI:\n"
                "1. Log in to your account.\n"
                "2. Click List Property.\n"
                "3. Choose Sale or Rent and select the property type.\n"
                "4. Enter the property location and details.\n"
                "5. Upload the required property photos.\n"
                "6. Submit the listing.\n"
                "Your valid listing becomes active immediately and follows the 30-day listing lifecycle."
            )

        # ----------------------------------------------------
        # SEARCH
        # ----------------------------------------------------

        elif (
            "how do i search" in text
            or "how to search" in text
            or "search properties" in text
            or "find property" in text
            or "find properties" in text
        ):
            reply = (
                "To search for properties, choose a State, City or Locality. "
                "You can then refine the results using Sale/Rent, property type, "
                "budget, area, BHK, bathrooms, parking, facing, furnishing and "
                "property-age filters."
            )

        # ----------------------------------------------------
        # AI VALUATION
        # ----------------------------------------------------

        elif (
            "ai valuation" in text
            or "price prediction" in text
            or "predict property price" in text
            or "estimate property value" in text
            or "how does valuation work" in text
        ):
            reply = (
                "RealtyKey AI uses a trained machine-learning valuation model "
                "together with geographic benchmark data. It considers property "
                "location, type, area, BHK and bathrooms. The system can use "
                "broader geographic benchmarks when detailed locality data is limited."
            )

        # ----------------------------------------------------
        # COMPARISON
        # ----------------------------------------------------

        elif (
            "compare properties" in text
            or "how do i compare" in text
            or "property comparison" in text
        ):
            reply = (
                "Select 2 to 4 properties using the Compare checkbox. "
                "Then click Compare Now to view their prices, property details "
                "and available AI valuation information side by side."
            )

        # ----------------------------------------------------
        # FAVORITES
        # ----------------------------------------------------

        elif (
            "favorite" in text
            or "favourite" in text
            or "save property" in text
        ):
            reply = (
                "Use the heart button on a property card or property-details page "
                "to save a property. Saved properties remain associated with your account."
            )

        # ----------------------------------------------------
        # CHAT / SELLER
        # ----------------------------------------------------

        elif (
            "chat with seller" in text
            or "contact seller" in text
            or "message seller" in text
        ):
            reply = (
                "Open another user's property and select Chat with Seller. "
                "You can send a quick message or write your own question. "
                "Seller conversations are stored with your account."
            )

        # ----------------------------------------------------
        # OFFERS
        # ----------------------------------------------------

        elif (
            "make an offer" in text
            or "make offer" in text
            or "negotiate" in text
        ):
            reply = (
                "Open a property owned by another user and choose Make an Offer. "
                "Enter your proposed price and submit it. The seller can then accept "
                "or reject the offer."
            )

        # ----------------------------------------------------
        # REPORT
        # ----------------------------------------------------

        elif (
            "report property" in text
            or "report listing" in text
            or "scam" in text
            or "fake listing" in text
            or "suspicious listing" in text
        ):
            reply = (
                "Use Report this Property to report suspicious or scam listings, "
                "fake information, duplicate listings or incorrect property details. "
                "The report is sent for administrator review."
            )

        # ----------------------------------------------------
        # ACCOUNT
        # ----------------------------------------------------

        elif (
            "change password" in text
            or "delete account" in text
            or "logout" in text
            or "account settings" in text
        ):
            reply = (
                "Your account area lets you manage your password, logout, "
                "favorites, listings, messages and notifications. "
                "You can also permanently delete your account."
            )

        # ----------------------------------------------------
        # ABOUT
        # ----------------------------------------------------

        elif (
            "what is realtykey" in text
            or "about realtykey" in text
            or "what does realtykey do" in text
            or "what is this website" in text
        ):
            reply = (
                "RealtyKey AI is a real-estate marketplace designed to make "
                "property decisions smarter. It combines property search, "
                "recommendations, AI valuation, comparison, favorites, "
                "buyer-seller communication and offers in one platform."
            )

        # ----------------------------------------------------
        # GREETING
        # ----------------------------------------------------

        elif text in {
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening"
        }:
            reply = (
                "Hello! I can help you with property search, listing, "
                "AI valuation, comparisons, favorites, seller chat, "
                "offers and reports."
            )

        # ----------------------------------------------------
        # DEFAULT
        # ----------------------------------------------------

        else:
            reply = (
                "I can help with property search, listing, AI valuation, "
                "comparisons, favorites, seller chat, offers and reports. "
                "Try asking something like “How do I list a property?”"
            )

        return jsonify({
            "success": True,
            "reply": reply
        })

    except Exception as error:
        print(
            "AI assistant error:",
            error
        )

        return jsonify({
            "success": False,
            "error": "The AI assistant could not process that request."
        }), 500


# ============================================================
# AI ASSISTANT
# ============================================================
# ============================================================
# AI ASSISTANT
# ============================================================

ASSISTANT_RESPONSES = {
    "greeting":
        "Hello! I can help you use RealtyKey AI for property search, listings, valuation, comparison, favorites, seller chat, offers, reports, and account settings.",

    "about":
        "RealtyKey AI is an AI-powered real estate marketplace that helps users discover properties, compare listings, understand property values, communicate with sellers, and manage their own listings.",

    "search":
        "To search properties, select a State, City, or Locality first. Budget and area are optional. You can then refine results by Sale/Rent, property type, price, BHK, bathrooms, parking, facing, furnishing, and property age.",

    "listing":
        "To list a property:\n"
        "1. Log in to your RealtyKey AI account.\n"
        "2. Click 'List Property'.\n"
        "3. Select Sale or Rent and choose Apartment, House/Villa, or Plot.\n"
        "4. Enter the property location and required details.\n"
        "5. Upload 1–20 JPG, JPEG, PNG, or WEBP photos, up to 10 MB each.\n"
        "6. Submit the listing.\n\n"
        "A valid listing is published directly to the marketplace and has a 30-day active lifecycle.",

    "favorites":
        "Use the heart button on a property card or property-details page to save a property. Your favorites are stored with your account and remain available after you log in again.",

    "chat":
        "Open a property owned by another user and select 'Chat with Seller'. You can use quick messages or type your own message. Conversations are stored in the account and updated through lightweight polling.",

    "offer":
        "Open another user's property and choose 'Make an Offer'. The seller receives an in-app notification and can accept or reject the offer. The buyer then receives the updated offer status.",

    "report":
        "Use 'Report this Property' to report suspicious or scam listings, fake information, duplicate listings, incorrect details, or another issue. Administrators can review reported properties.",

    "account":
        "Your account area provides login/logout, favorites, My Listings, Messages, Change Password, Delete Account, and notifications.",

    "recommendations":
        "Recommended Properties uses your selected location and property preferences such as listing type, property type, budget, area, BHK, bathrooms, parking, facing, and furnishing. Each result includes the reasons why it matched.",

    "compare":
        "Select 2–4 properties using the Compare checkbox. Then click 'Compare Now' to view asking price, AI valuation information, location, type, area, BHK, bathrooms, parking, facing, furnishing, and other available details side by side.",

    "valuation":
        "AI Property Valuation estimates property value using the trained machine-learning model together with geographic benchmark information. The system checks available locality data before falling back to broader geographic coverage.",

    "metrics":
        "The valuation model is evaluated using held-out data. RealtyKey AI can display MAE, RMSE, R², median absolute percentage error, and the percentage of predictions within ±10% and ±20%. These are evaluation measurements, not guarantees for an individual property.",

    "admin":
        "The administrator dashboard provides property management, user management, report review, and marketplace oversight."
}


def assistant_intent(message: str) -> str:
    text = clean_text(message).lower()

    # --------------------------------------------------------
    # EXACT / HIGH PRIORITY INTENTS
    # --------------------------------------------------------

    # Listing must come BEFORE generic words such as "how".
    if any(k in text for k in [
        "how do i list",
        "how do i list a property",
        "how to list",
        "how to list a property",
        "list a property",
        "listing a property",
        "publish a property",
        "sell a property",
        "add a property",
        "list property",
        "sell property",
        "publish property",
        "add property"
    ]):
        return "listing"

    if any(k in text for k in [
        "valuation",
        "predict price",
        "price prediction",
        "estimate value",
        "ai model",
        "model work",
        "machine learning"
    ]):
        if any(k in text for k in [
            "accuracy",
            "accurate",
            "mae",
            "rmse",
            "r2",
            "r²",
            "metric",
            "percentage"
        ]):
            return "metrics"

        return "valuation"

    if any(k in text for k in [
        "recommend",
        "recommendation",
        "suggest property",
        "matching"
    ]):
        return "recommendations"

    if any(k in text for k in [
        "compare",
        "comparison",
        "compare properties"
    ]):
        return "compare"

    if any(k in text for k in [
        "favorite",
        "favourite",
        "saved property",
        "save property"
    ]):
        return "favorites"

    if any(k in text for k in [
        "make an offer",
        "offer",
        "negotiate",
        "accept offer",
        "reject offer"
    ]):
        return "offer"

    if any(k in text for k in [
        "chat",
        "message seller",
        "contact seller",
        "buyer seller"
    ]):
        return "chat"

    if any(k in text for k in [
        "report",
        "scam",
        "fake",
        "duplicate listing",
        "incorrect listing"
    ]):
        return "report"

    if any(k in text for k in [
        "search",
        "find property",
        "filter",
        "browse"
    ]):
        return "search"

    if any(k in text for k in [
        "password",
        "delete account",
        "logout",
        "login",
        "account settings"
    ]):
        return "account"

    if any(k in text for k in [
        "admin",
        "administrator",
        "dashboard"
    ]):
        return "admin"

    if any(k in text for k in [
        "realtykey",
        "what is this",
        "about the platform"
    ]):
        return "about"

    if any(k in text for k in [
        "hello",
        "hi",
        "hey",
        "good morning",
        "good evening"
    ]):
        return "greeting"

    return "about"


@app.route("/api/ai-assistant", methods=["POST"])
def ai_assistant():
    try:
        data = request.get_json(silent=True) or {}
        message = clean_text(data.get("message"))

        if not message:
            return jsonify({
                "success": False,
                "error": "Message is required."
            }), 400

        intent = assistant_intent(message)

        reply = ASSISTANT_RESPONSES.get(
            intent,
            ASSISTANT_RESPONSES["about"]
        )

        return jsonify({
            "success": True,
            "intent": intent,
            "reply": reply
        })

    except Exception:
        app.logger.exception("AI assistant error")
        return jsonify({
            "success": False,
            "error": "The RealtyKey AI assistant is temporarily unavailable."
        }), 500


@app.route("/list-property", methods=["POST"])
def list_property():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login before listing a property."}), 401

    listing_type = clean_text(request.form.get("listing_type")) or "Sale"
    if listing_type.lower() == "sell":
        listing_type = "Sale"
    if listing_type not in {"Sale", "Rent"}:
        return jsonify({"success": False, "error": "Listing type must be Sale or Rent."}), 400

    property_type = clean_text(request.form.get("property_type")) or "Apartment"
    if property_type not in {"Apartment", "House", "Villa", "Plot"}:
        return jsonify({"success": False, "error": "Unsupported property type."}), 400
    city = clean_text(request.form.get("city"))
    locality = clean_text(request.form.get("locality"))
    state = clean_text(request.form.get("state")) or infer_state(city)
    if not city or not locality:
        return jsonify({"success": False, "error": "City and locality are required."}), 400

    price = safe_float(request.form.get("price") or request.form.get("budget"))
    area = safe_float(request.form.get("area"))
    if price is None or price <= 0:
        return jsonify({"success": False, "error": "Valid positive price/rent is required."}), 400
    if area is None or area <= 0:
        return jsonify({"success": False, "error": "Valid positive area is required."}), 400

    facing = clean_text(request.form.get("facing")) or "Not Specified"
    furnishing = clean_text(request.form.get("furnishing")) or ("Not Applicable" if property_type == "Plot" else "Unfurnished")
    parking = safe_int(request.form.get("parking")) or safe_int(request.form.get("parking_spaces")) or 0
    description = clean_text(request.form.get("description"))
    latitude = safe_float(request.form.get("latitude"))
    longitude = safe_float(request.form.get("longitude"))
    location_address = clean_text(request.form.get("location_address")) or f"{locality}, {city}, {state}"

    amenities_raw = clean_text(request.form.get("amenities"))
    try:
        amenities = json.loads(amenities_raw) if amenities_raw.startswith("[") else [x.strip() for x in amenities_raw.split(",") if x.strip()]
    except Exception:
        amenities = [x.strip() for x in amenities_raw.split(",") if x.strip()]

    bhk = safe_int(request.form.get("bhk") or request.form.get("bedrooms")) or 0
    bathrooms = safe_int(request.form.get("bathrooms")) or 0
    property_age = safe_int(request.form.get("property_age")) or 0
    built_up_area = safe_float(request.form.get("built_up_area"))
    carpet_area = safe_float(request.form.get("carpet_area"))
    plot_area = safe_float(request.form.get("plot_area"))
    length = safe_float(request.form.get("length"))
    width = safe_float(request.form.get("width"))
    road_width = safe_float(request.form.get("road_width"))
    floors = safe_int(request.form.get("floors") or request.form.get("number_of_floors"))
    floor_number = safe_int(request.form.get("floor_number"))
    total_floors = safe_int(request.form.get("total_floors"))

    if property_type in {"House", "Villa"}:
        built_up_area = built_up_area or area
        carpet_area = carpet_area or round(built_up_area * 0.85, 1)
        plot_area = plot_area or built_up_area
        bhk = bhk or 3
        bathrooms = bathrooms or 2
        floors = floors or 1
        total_floors = total_floors or floors
    elif property_type == "Apartment":
        built_up_area = built_up_area or area
        carpet_area = carpet_area or round(built_up_area * 0.85, 1)
        bhk = bhk or 2
        bathrooms = bathrooms or 2
        floor_number = floor_number if floor_number is not None else 1
        total_floors = total_floors or 5
    else:
        plot_area = plot_area or area
        bhk = 0
        bathrooms = 0
        property_age = 0

    uploaded_files = [f for f in request.files.getlist("images") if f and f.filename]
    if not uploaded_files:
        return jsonify({"success": False, "error": "Please upload at least 1 property image."}), 400
    if len(uploaded_files) > MAX_IMAGES:
        return jsonify({"success": False, "error": f"Maximum {MAX_IMAGES} images allowed."}), 400
    for image in uploaded_files:
        valid, error = validate_image(image)
        if not valid:
            return jsonify({"success": False, "error": error}), 400

    property_id = next_property_id()
    prop_dir = UPLOAD_FOLDER / str(property_id)
    prop_dir.mkdir(parents=True, exist_ok=False)
    image_urls = []

    try:
        for image in uploaded_files:
            safe_name = secure_filename(image.filename)
            suffix = Path(safe_name).suffix.lower()
            filename = f"{uuid4().hex}{suffix}"
            image.save(prop_dir / filename)
            image_urls.append(f"/uploads/properties/{property_id}/{filename}")

        user = find_user(user_id) or {}
        owner_name = clean_text(user.get("name")) or clean_text(session.get("user_name")) or "Property Owner"
        owner_email = clean_text(user.get("email")) or clean_text(session.get("user_email"))
        created = now_iso()
        expires = expiry_iso(30)
        document = {
            "property_id": property_id,
            "owner_id": user_id,
            "owner_name": owner_name,
            "owner_email": owner_email,
            "listing_type": listing_type,
            "property_type": property_type,
            "state": state,
            "city": city,
            "locality": locality,
            "location_address": location_address,
            "latitude": latitude,
            "longitude": longitude,
            "price": price,
            "budget": price,
            "area": area,
            "built_up_area": built_up_area,
            "carpet_area": carpet_area,
            "plot_area": plot_area,
            "length": length,
            "width": width,
            "road_width": road_width,
            "bhk": bhk,
            "bedrooms": bhk,
            "bathrooms": bathrooms,
            "parking": parking,
            "facing": facing,
            "furnishing": furnishing,
            "property_age": property_age,
            "floors": floors,
            "floor_number": floor_number,
            "total_floors": total_floors,
            "floor_position": (f"Floor {floor_number} of {total_floors}" if property_type == "Apartment" and floor_number is not None else "Independent" if property_type in {"House", "Villa"} else ""),
            "amenities": amenities,
            "description": description,
            "images": image_urls,
            "image_count": len(image_urls),
            "views": 0,
            "status": "active",
            "created_at": created,
            "expires_at": expires,
            "updated_at": created,
        }
        properties_collection.insert_one(document)
        return jsonify({"success": True, "message": "Property published successfully and is now active on the marketplace!", "property_id": property_id, "status": "active", "expires_at": expires, "image_count": len(image_urls)}), 201
    except Exception as error:
        print("Property listing error:", error)
        delete_property_assets(property_id)
        return jsonify({"success": False, "error": "Unable to save property listing."}), 500


# ============================================================
# PROPERTY DETAILS / FAVORITES
# ============================================================

@app.route("/property/<int:property_id>")
def property_details(property_id: int):
    prop = get_property_by_id(property_id)
    if not prop:
        return jsonify({"success": False, "error": "Property not found."}), 404

    viewer_id = require_login()
    session_key = f"viewed_{property_id}"
    if not session.get(session_key) and viewer_id != prop.get("owner_id"):
        session[session_key] = True
        try:
            properties_collection.update_one({"property_id": property_id}, {"$inc": {"views": 1}})
            prop["views"] += 1
        except Exception:
            pass
    return jsonify({"success": True, "property": prop})


@app.route("/listed-properties")
def listed_properties():
    items = [p for p in all_public_properties() if p.get("is_user_listing")]
    return jsonify({"success": True, "count": len(items), "properties": items})


@app.route("/api/favorites", methods=["GET"])
def get_favorites():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login to view favorites."}), 401
    docs = list(favorites_collection.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1))
    props = []
    for fav in docs:
        prop = get_property_by_id(safe_int(fav.get("property_id")) or 0)
        if prop:
            props.append(prop)
    return jsonify({"success": True, "count": len(props), "properties": props})


@app.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login to manage favorites."}), 401
    data = request.get_json(silent=True) or {}
    property_id = safe_int(data.get("property_id"))
    if not property_id or not get_property_by_id(property_id):
        return jsonify({"success": False, "error": "Valid active property ID required."}), 400
    existing = favorites_collection.find_one({"user_id": user_id, "property_id": property_id})
    if existing:
        favorites_collection.delete_one({"_id": existing["_id"]})
        return jsonify({"success": True, "favorited": False})
    favorites_collection.update_one({"user_id": user_id, "property_id": property_id}, {"$setOnInsert": {"created_at": now_iso()}}, upsert=True)
    return jsonify({"success": True, "favorited": True})


# ============================================================
# MY LISTINGS
# ============================================================

@app.route("/api/my-listings")
def my_listings():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login to manage listings."}), 401
    purge_expired_listings()
    docs = list(properties_collection.find({"owner_id": user_id}, {"_id": 0}).sort("created_at", -1))
    props = [normalize_property(d) for d in docs]
    return jsonify({"success": True, "count": len(props), "properties": props})


@app.route("/api/my-listings/<int:property_id>", methods=["DELETE"])
def delete_my_listing(property_id: int):
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    prop = properties_collection.find_one({"property_id": property_id})
    if not prop:
        return jsonify({"success": False, "error": "Property not found."}), 404
    if clean_text(prop.get("owner_id")) != user_id and not is_admin():
        return jsonify({"success": False, "error": "You are not authorized to delete this property."}), 403
    properties_collection.delete_one({"property_id": property_id})
    favorites_collection.delete_many({"property_id": property_id})
    reports_collection.delete_many({"property_id": property_id})
    conversations_collection.delete_many({"property_id": property_id})
    messages_collection.delete_many({"property_id": property_id})
    offers_collection.delete_many({"property_id": property_id})
    delete_property_assets(property_id)
    return jsonify({"success": True, "message": "Property deleted successfully."})


# ============================================================
# CHAT / MESSAGES
# ============================================================

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    query = {"$or": [{"buyer_id": user_id}, {"owner_id": user_id}]}
    docs = list(conversations_collection.find(query, {"_id": 0}).sort("updated_at", -1))
    for doc in docs:
        doc["property"] = get_property_by_id(safe_int(doc.get("property_id")) or 0)
        messages = doc.get("messages") or []
        doc["last_message"] = messages[-1] if messages else None
        doc["message_count"] = len(messages)
    return jsonify({"success": True, "count": len(docs), "conversations": docs})


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    data = request.get_json(silent=True) or {}
    property_id = safe_int(data.get("property_id"))
    text_val = clean_text(data.get("message"))
    if not property_id or not text_val:
        return jsonify({"success": False, "error": "Property ID and message required."}), 400
    prop = get_property_by_id(property_id)
    if not prop:
        return jsonify({"success": False, "error": "Property not found."}), 404
    owner_id = clean_text(prop.get("owner_id"))
    if not owner_id:
        return jsonify({"success": False, "error": "This property does not support direct owner chat."}), 400
    if owner_id == user_id:
        return jsonify({"success": False, "error": "You cannot initiate a chat with yourself.", "own_property": True}), 400

    buyer_name = clean_text(session.get("user_name")) or "Buyer"
    now = now_iso()
    msg = {"message_id": uuid4().hex, "sender_id": user_id, "sender_name": buyer_name, "text": text_val, "created_at": now}
    query = {"property_id": property_id, "buyer_id": user_id, "owner_id": owner_id}
    conv = conversations_collection.find_one(query)
    if conv:
        cid = conv["conversation_id"]
        conversations_collection.update_one({"conversation_id": cid}, {"$push": {"messages": msg}, "$set": {"updated_at": now}})
    else:
        cid = uuid4().hex
        conversations_collection.insert_one({"conversation_id": cid, "property_id": property_id, "buyer_id": user_id, "buyer_name": buyer_name, "owner_id": owner_id, "owner_name": prop.get("owner_name", "Seller"), "messages": [msg], "created_at": now, "updated_at": now})
    messages_collection.insert_one({**msg, "conversation_id": cid, "property_id": property_id})
    create_notification(owner_id, "message", f"New Message from {buyer_name}", f"Regarding {prop['locality']}, {prop['city']}: {text_val[:80]}", f"messages.html?cid={cid}")
    return jsonify({"success": True, "conversation_id": cid})


@app.route("/api/conversations/<conversation_id>")
def get_conversation(conversation_id: str):
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    doc = conversations_collection.find_one({"conversation_id": conversation_id}, {"_id": 0})
    if not doc:
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    participants = {clean_text(doc.get("buyer_id")), clean_text(doc.get("owner_id"))}
    if user_id not in participants and not is_admin():
        return jsonify({"success": False, "error": "Access denied."}), 403
    doc["property"] = get_property_by_id(safe_int(doc.get("property_id")) or 0)
    return jsonify({"success": True, "conversation": doc})


@app.route("/api/conversations/<conversation_id>/messages", methods=["POST"])
def send_conversation_message(conversation_id: str):
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    conv = conversations_collection.find_one({"conversation_id": conversation_id})
    if not conv:
        return jsonify({"success": False, "error": "Conversation not found."}), 404
    if user_id not in {clean_text(conv.get("buyer_id")), clean_text(conv.get("owner_id"))} and not is_admin():
        return jsonify({"success": False, "error": "Access denied."}), 403
    data = request.get_json(silent=True) or {}
    text_val = clean_text(data.get("message"))
    if not text_val:
        return jsonify({"success": False, "error": "Message cannot be empty."}), 400
    sender_name = clean_text(session.get("user_name")) or "User"
    recipient_id = conv.get("owner_id") if user_id == conv.get("buyer_id") else conv.get("buyer_id")
    now = now_iso()
    msg = {"message_id": uuid4().hex, "sender_id": user_id, "sender_name": sender_name, "text": text_val, "created_at": now}
    conversations_collection.update_one({"conversation_id": conversation_id}, {"$push": {"messages": msg}, "$set": {"updated_at": now}})
    messages_collection.insert_one({**msg, "conversation_id": conversation_id, "property_id": conv.get("property_id")})
    create_notification(str(recipient_id), "message", f"Message from {sender_name}", text_val[:100], f"messages.html?cid={conversation_id}")
    return jsonify({"success": True, "message": msg})


# ============================================================
# OFFERS
# ============================================================

@app.route("/api/offers", methods=["POST"])
def make_offer():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    data = request.get_json(silent=True) or {}
    property_id = safe_int(data.get("property_id"))
    offered_price = safe_float(data.get("offered_price"))
    if not property_id or offered_price is None or offered_price <= 0:
        return jsonify({"success": False, "error": "Valid property ID and offered price required."}), 400
    prop = get_property_by_id(property_id)
    if not prop:
        return jsonify({"success": False, "error": "Property not found."}), 404
    seller_id = clean_text(prop.get("owner_id"))
    if not seller_id or seller_id == user_id:
        return jsonify({"success": False, "error": "You cannot make an offer on your own listing."}), 400
    offer_id = uuid4().hex
    now = now_iso()
    buyer_name = clean_text(session.get("user_name")) or "Buyer"
    doc = {"offer_id": offer_id, "property_id": property_id, "property_title": f"{prop['locality']}, {prop['city']}", "buyer_id": user_id, "buyer_name": buyer_name, "seller_id": seller_id, "seller_name": prop.get("owner_name", "Seller"), "offered_price": offered_price, "status": "pending", "created_at": now, "updated_at": now}
    offers_collection.insert_one(doc)
    create_notification(seller_id, "offer", f"New Offer: ₹{offered_price:,.0f}", f"{buyer_name} submitted an offer on {prop['locality']}, {prop['city']}.", f"messages.html?property_id={property_id}")
    return jsonify({"success": True, "offer_id": offer_id, "message": "Offer submitted to seller."}), 201


@app.route("/api/offers")
def list_offers():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    prop_id = safe_int(request.args.get("property_id"))
    query = {"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]}
    if prop_id:
        query["property_id"] = prop_id
    offers = list(offers_collection.find(query, {"_id": 0}).sort("created_at", -1))
    return jsonify({"success": True, "count": len(offers), "offers": offers})


@app.route("/api/offers/<offer_id>/respond", methods=["POST"])
def respond_offer(offer_id: str):
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    data = request.get_json(silent=True) or {}
    action = clean_text(data.get("action")).lower()
    if action not in {"accept", "reject"}:
        return jsonify({"success": False, "error": "Action must be 'accept' or 'reject'."}), 400
    offer = offers_collection.find_one({"offer_id": offer_id})
    if not offer:
        return jsonify({"success": False, "error": "Offer not found."}), 404
    if clean_text(offer.get("seller_id")) != user_id and not is_admin():
        return jsonify({"success": False, "error": "Only the seller can respond to this offer."}), 403
    if offer.get("status") != "pending":
        return jsonify({"success": False, "error": "This offer has already been processed."}), 409
    new_status = "accepted" if action == "accept" else "rejected"
    offers_collection.update_one({"offer_id": offer_id}, {"$set": {"status": new_status, "updated_at": now_iso()}})
    create_notification(str(offer.get("buyer_id")), f"offer_{new_status}", f"Offer {new_status.capitalize()}!", f"Your offer of ₹{offer.get('offered_price', 0):,.0f} on {offer.get('property_title', 'property')} was {new_status}.", f"messages.html?property_id={offer.get('property_id')}")
    return jsonify({"success": True, "status": new_status, "message": f"Offer {new_status} successfully."})


# ============================================================
# NOTIFICATIONS / REPORTS
# ============================================================

@app.route("/api/notifications")
def get_notifications():
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    items = list(notifications_collection.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(40))
    unread = notifications_collection.count_documents({"user_id": user_id, "read": False})
    return jsonify({"success": True, "count": len(items), "unread": unread, "notifications": items})


@app.route("/api/notifications/<notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id: str):
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401
    notifications_collection.update_one({"notification_id": notification_id, "user_id": user_id}, {"$set": {"read": True}})
    return jsonify({"success": True})


@app.route("/api/properties/<int:property_id>/report", methods=["POST"])
def report_property(property_id: int):
    user_id = require_login()
    if not user_id:
        return jsonify({"success": False, "error": "Please login to report a property."}), 401
    prop = get_property_by_id(property_id)
    if not prop:
        return jsonify({"success": False, "error": "Property not found."}), 404
    if clean_text(prop.get("owner_id")) == user_id:
        return jsonify({"success": False, "error": "You cannot report your own listing."}), 400
    data = request.get_json(silent=True) or {}
    category = clean_text(data.get("category") or data.get("reason"))
    details = clean_text(data.get("details"))
    if not category:
        return jsonify({"success": False, "error": "Please select a valid report category."}), 400
    reports_collection.insert_one({"report_id": uuid4().hex, "property_id": property_id, "property_title": f"{prop['locality']}, {prop['city']}", "reported_by": user_id, "category": category, "reason": category, "details": details, "status": "open", "created_at": now_iso()})
    return jsonify({"success": True, "message": "Property report submitted for admin review."}), 201


# ============================================================
# ADMIN
# ============================================================

@app.route("/api/admin/summary")
def admin_summary():
    denied = require_admin()
    if denied:
        return denied
    purge_expired_listings()
    return jsonify({"success": True, "users": users_collection.count_documents({}), "properties": properties_collection.count_documents({}), "reports": reports_collection.count_documents({"status": "open"}), "conversations": conversations_collection.count_documents({}), "offers": offers_collection.count_documents({})})


@app.route("/api/admin/users")
def admin_users():
    denied = require_admin()
    if denied:
        return denied
    users = []
    admin_email = clean_text(os.getenv("ADMIN_EMAIL")).lower()
    for user in users_collection.find({}, {"password_hash": 0}).sort("created_at", -1):
        user["id"] = str(user.pop("_id", ""))
        user["role"] = "admin" if clean_text(user.get("email")).lower() == admin_email and admin_email else user.get("role", "user")
        users.append(user)
    return jsonify({"success": True, "count": len(users), "users": users})


@app.route("/api/admin/users/<user_id>/status", methods=["POST"])
def admin_user_status(user_id: str):
    denied = require_admin()
    if denied:
        return denied
    from bson import ObjectId
    data = request.get_json(silent=True) or {}
    status = clean_text(data.get("status")).lower()
    if status not in {"active", "inactive"}:
        return jsonify({"success": False, "error": "Status must be active or inactive."}), 400
    user = None
    if ObjectId.is_valid(user_id):
        user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        user = users_collection.find_one({"user_id": user_id})
    if not user:
        return jsonify({"success": False, "error": "User not found."}), 404
    admin_email = clean_text(os.getenv("ADMIN_EMAIL")).lower()
    if admin_email and clean_text(user.get("email")).lower() == admin_email:
        return jsonify({"success": False, "error": "The configured administrator account cannot be deactivated."}), 403
    users_collection.update_one({"_id": user["_id"]}, {"$set": {"status": status, "updated_at": now_iso()}})
    return jsonify({"success": True, "status": status})


@app.route("/api/admin/properties")
def admin_properties():
    denied = require_admin()
    if denied:
        return denied
    purge_expired_listings()
    props = [normalize_property(d) for d in properties_collection.find({}, {"_id": 0}).sort("created_at", -1)]
    return jsonify({"success": True, "count": len(props), "properties": props})


@app.route("/api/admin/properties/<int:property_id>", methods=["DELETE"])
def admin_delete_property(property_id: int):
    denied = require_admin()
    if denied:
        return denied
    prop = properties_collection.find_one({"property_id": property_id})
    if not prop:
        return jsonify({"success": False, "error": "Property not found."}), 404
    properties_collection.delete_one({"property_id": property_id})
    favorites_collection.delete_many({"property_id": property_id})
    reports_collection.delete_many({"property_id": property_id})
    conversations_collection.delete_many({"property_id": property_id})
    messages_collection.delete_many({"property_id": property_id})
    offers_collection.delete_many({"property_id": property_id})
    delete_property_assets(property_id)
    return jsonify({"success": True, "message": f"Property #{property_id} removed by administrator."})


@app.route("/api/admin/reports")
def admin_reports():
    denied = require_admin()
    if denied:
        return denied
    reports = list(reports_collection.find({}, {"_id": 0}).sort("created_at", -1))
    return jsonify({"success": True, "count": len(reports), "reports": reports})


@app.route("/api/admin/reports/<report_id>/resolve", methods=["POST"])
def admin_resolve_report(report_id: str):
    denied = require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    resolution = clean_text(data.get("action")) or "reviewed"
    result = reports_collection.update_one({"report_id": report_id, "status": "open"}, {"$set": {"status": "resolved", "resolution": resolution, "resolved_at": now_iso()}})
    if result.matched_count == 0:
        return jsonify({"success": False, "error": "Open report not found."}), 404
    return jsonify({"success": True, "message": "Report marked as resolved."})


@app.route("/api/admin/reports/property/<int:property_id>/resolve", methods=["POST"])
def admin_resolve_property_reports(property_id: int):
    denied = require_admin()
    if denied:
        return denied
    reports_collection.update_many({"property_id": property_id, "status": "open"}, {"$set": {"status": "resolved", "resolution": "reviewed", "resolved_at": now_iso()}})
    return jsonify({"success": True, "message": "Open reports for the property were resolved."})


# Compatibility with the previous frontend implementation.
@app.route("/api/admin/reports/<property_id>/resolve-legacy", methods=["POST"])
def admin_resolve_report_legacy(property_id: str):
    denied = require_admin()
    if denied:
        return denied
    pid = safe_int(property_id)
    reports_collection.update_many({"property_id": pid, "status": "open"}, {"$set": {"status": "resolved", "resolution": "reviewed", "resolved_at": now_iso()}})
    return jsonify({"success": True, "message": "Reports marked as resolved."})


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify({"success": False, "error": "Upload request is too large. Maximum total request size is 220 MB and each image is limited to 10 MB."}), 413


if __name__ == "__main__":
    print("Starting RealtyKey AI on http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
