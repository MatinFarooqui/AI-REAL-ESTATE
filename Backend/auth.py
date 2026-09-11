from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import re

from mongodb import db

auth_bp = Blueprint("auth", __name__)
users_collection = db["users"]


def valid_email(email):
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return re.match(pattern, email) is not None


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


@auth_bp.route("/signup", methods=["POST"])
def signup():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "Request body is required."
        }), 400

    name = clean_text(data.get("name"))
    email = clean_text(data.get("email")).lower()
    password = clean_text(data.get("password"))

    if not name:
        return jsonify({
            "success": False,
            "error": "Name is required."
        }), 400

    if not email:
        return jsonify({
            "success": False,
            "error": "Email is required."
        }), 400

    if not valid_email(email):
        return jsonify({
            "success": False,
            "error": "Please enter a valid email address."
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "error": "Password must contain at least 6 characters."
        }), 400

    existing_user = users_collection.find_one({
        "email": email
    })

    if existing_user:
        return jsonify({
            "success": False,
            "error": "An account with this email already exists."
        }), 409

    password_hash = generate_password_hash(password)

    user_document = {
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "role": "user",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active"
    }

    try:

        result = users_collection.insert_one(user_document)

        user_id = str(result.inserted_id)

        return jsonify({
            "success": True,
            "message": "Account created successfully.",
            "user": {
                "id": user_id,
                "name": name,
                "email": email
            }
        }), 201

    except Exception as error:

        print("Signup error:", error)

        return jsonify({
            "success": False,
            "error": "Unable to create account."
        }), 500


@auth_bp.route("/login", methods=["POST"])
def login():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success": False,
            "error": "Request body is required."
        }), 400

    email = clean_text(data.get("email")).lower()
    password = clean_text(data.get("password"))

    if not email or not password:
        return jsonify({
            "success": False,
            "error": "Email and password are required."
        }), 400

    user = users_collection.find_one({
        "email": email
    })

    if not user:
        return jsonify({
            "success": False,
            "error": "Invalid email or password."
        }), 401

    if user.get("status") != "active":
        return jsonify({
            "success": False,
            "error": "This account is not active."
        }), 403

    password_hash = user.get("password_hash", "")

    if not check_password_hash(password_hash, password):
        return jsonify({
            "success": False,
            "error": "Invalid email or password."
        }), 401

    session["user_id"] = str(user["_id"])
    session["user_name"] = user.get("name", "")
    session["user_email"] = user.get("email", "")

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": str(user["_id"]),
            "name": user.get("name", ""),
            "email": user.get("email", "")
        }
    })


@auth_bp.route("/me", methods=["GET"])
def current_user():

    user_id = session.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "logged_in": False
        }), 401

    return jsonify({
        "success": True,
        "logged_in": True,
        "user": {
            "id": user_id,
            "name": session.get("user_name", ""),
            "email": session.get("user_email", "")
        }
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })