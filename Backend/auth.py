from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from Backend.mongodb import db

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

auth_bp = Blueprint("auth", __name__)
users_collection = db["users"]


def clean_text(value) -> str:
    return str(value or "").strip()


def valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def normalize_phone(phone) -> str:
    value = clean_text(phone)
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if len(digits) == 10:
        return "+91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    return ""


def resolve_role(user_email: str, stored_role: str = "user") -> str:
    admin_email = clean_text(os.getenv("ADMIN_EMAIL")).lower()
    if admin_email and clean_text(user_email).lower() == admin_email:
        return "admin"
    return stored_role if stored_role in {"user", "admin"} else "user"


def find_user_by_identifier(identifier):
    value = clean_text(identifier)
    if not value:
        return None
    if "@" in value:
        return users_collection.find_one({"email": value.lower()})
    phone = normalize_phone(value)
    if phone:
        return users_collection.find_one({"phone": phone})
    return users_collection.find_one({"email": value.lower()})


def get_user_by_session_id(user_id: str):
    if not user_id:
        return None
    if ObjectId.is_valid(user_id):
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            return user
    return users_collection.find_one({"user_id": str(user_id)})


@auth_bp.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"success": False, "error": "Request body is required."}), 400

    name = clean_text(data.get("name"))
    email = clean_text(data.get("email")).lower()
    phone_input = clean_text(data.get("phone"))
    phone = normalize_phone(phone_input)
    password = clean_text(data.get("password"))

    if not name:
        return jsonify({"success": False, "error": "Full name is required."}), 400
    if not valid_email(email):
        return jsonify({"success": False, "error": "Please enter a valid email address."}), 400
    if phone_input and not phone:
        return jsonify({"success": False, "error": "Please enter a valid 10-digit mobile number."}), 400
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must contain at least 6 characters."}), 400

    duplicate_conditions = [{"email": email}]
    if phone:
        duplicate_conditions.append({"phone": phone})

    try:
        if users_collection.find_one({"$or": duplicate_conditions}):
            return jsonify({"success": False, "error": "An account with this email or mobile number already exists."}), 409

        role = resolve_role(email, "user")
        document = {
            "name": name,
            "email": email,
            "password_hash": generate_password_hash(password),
            "role": role,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if phone:
            document["phone"] = phone

        result = users_collection.insert_one(document)
        user_id = str(result.inserted_id)

        # Do not auto-login. Let the user explicitly log in after signup.
        return jsonify({
            "success": True,
            "message": "Account created successfully. You can now log in.",
            "user": {
                "id": user_id,
                "name": name,
                "email": email,
                "phone": phone,
                "role": role,
            },
        }), 201
    except Exception as error:
        print("Signup error:", error)
        return jsonify({"success": False, "error": "Unable to create account right now."}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"success": False, "error": "Request body is required."}), 400

    identifier = clean_text(data.get("identifier") or data.get("email"))
    password = clean_text(data.get("password"))
    if not identifier or not password:
        return jsonify({"success": False, "error": "Email/mobile number and password are required."}), 400

    try:
        user = find_user_by_identifier(identifier)
    except Exception as error:
        print("Login database error:", error)
        return jsonify({"success": False, "error": "Authentication service is temporarily unavailable."}), 503

    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"success": False, "error": "Invalid email/mobile number or password."}), 401
    if user.get("status", "active") != "active":
        return jsonify({"success": False, "error": "This account is not active."}), 403

    role = resolve_role(user.get("email", ""), user.get("role", "user"))
    user_id = str(user.get("_id") or user.get("user_id"))
    session.clear()
    session["user_id"] = user_id
    session["user_name"] = user.get("name", "")
    session["user_email"] = user.get("email", "")
    session["user_phone"] = user.get("phone", "")
    session["user_role"] = role
    session.permanent = False

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "user": {
            "id": user_id,
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "role": role,
        },
    })


@auth_bp.route("/me", methods=["GET"])
def current_user():
    user_id = clean_text(session.get("user_id"))
    if not user_id:
        return jsonify({"success": False, "logged_in": False}), 401

    try:
        user = get_user_by_session_id(user_id)
    except Exception:
        user = None

    if not user or user.get("status", "active") != "active":
        session.clear()
        return jsonify({"success": False, "logged_in": False}), 401

    role = resolve_role(user.get("email", ""), user.get("role", "user"))
    session["user_role"] = role
    session["user_name"] = user.get("name", "")
    session["user_email"] = user.get("email", "")
    session["user_phone"] = user.get("phone", "")

    return jsonify({
        "success": True,
        "logged_in": True,
        "user": {
            "id": user_id,
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "role": role,
        },
    })


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})


@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    user_id = clean_text(session.get("user_id"))
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401

    data = request.get_json(silent=True) or {}
    current_password = clean_text(data.get("current_password"))
    new_password = clean_text(data.get("new_password"))
    if not current_password or not new_password:
        return jsonify({"success": False, "error": "Current and new passwords are required."}), 400
    if len(new_password) < 6:
        return jsonify({"success": False, "error": "New password must be at least 6 characters."}), 400

    user = get_user_by_session_id(user_id)
    if not user or not check_password_hash(user.get("password_hash", ""), current_password):
        return jsonify({"success": False, "error": "Incorrect current password."}), 400

    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": generate_password_hash(new_password), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return jsonify({"success": True, "message": "Password updated successfully."})


@auth_bp.route("/delete-account", methods=["POST"])
def delete_account():
    user_id = clean_text(session.get("user_id"))
    if not user_id:
        return jsonify({"success": False, "error": "Please login."}), 401

    data = request.get_json(silent=True) or {}
    password = clean_text(data.get("password"))
    if not password:
        return jsonify({"success": False, "error": "Password confirmation is required to delete your account."}), 400

    user = get_user_by_session_id(user_id)
    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify({"success": False, "error": "Incorrect password."}), 401

    upload_dir = BASE_DIR / "uploads" / "properties"
    user_properties = list(db["properties"].find({"owner_id": user_id}, {"property_id": 1}))
    for prop in user_properties:
        pid = prop.get("property_id")
        if not pid:
            continue
        folder = upload_dir / str(pid)
        if folder.exists():
            for image_path in folder.glob("*"):
                try:
                    image_path.unlink()
                except OSError:
                    pass
            try:
                folder.rmdir()
            except OSError:
                pass

    db["properties"].delete_many({"owner_id": user_id})
    db["favorites"].delete_many({"user_id": user_id})
    db["conversations"].delete_many({"$or": [{"buyer_id": user_id}, {"owner_id": user_id}]})
    db["messages"].delete_many({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]})
    db["offers"].delete_many({"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]})
    db["notifications"].delete_many({"user_id": user_id})
    db["reports"].delete_many({"reported_by": user_id})
    users_collection.delete_one({"_id": user["_id"]})

    session.clear()
    return jsonify({"success": True, "message": "Account and associated data deleted successfully."})
