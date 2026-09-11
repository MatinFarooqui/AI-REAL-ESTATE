from pathlib import Path
from uuid import uuid4
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import os

from flask import Flask, jsonify, request, send_from_directory
import pandas as pd
import joblib
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from property import calculate_rate
from mongodb import db, test_connection, properties_collection
from auth import auth_bp


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "data" / "properties.csv"

MODEL_PATH = BASE_DIR / "ml" / "real_estate_price_model_v2.pkl"

UPLOAD_FOLDER = BASE_DIR / "uploads" / "properties"


# ============================================================
# IMAGE SETTINGS
# ============================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "webp"
}

ALLOWED_IMAGE_MIMETYPES = {
    "image/jpeg",
    "image/png",
    "image/webp"
}

MAX_IMAGES = 20

MAX_IMAGE_SIZE = 100 * 1024 * 1024

MAX_REQUEST_SIZE = 2.1 * 1024 * 1024 * 1024


UPLOAD_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)


# ============================================================
# SESSION CONFIGURATION
# ============================================================

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "homesense-ai-development-secret"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = False


# ============================================================
# FILE CONFIGURATION
# ============================================================

app.config["UPLOAD_FOLDER"] = str(
    UPLOAD_FOLDER
)

app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_SIZE


# ============================================================
# REGISTER AUTHENTICATION
# ============================================================

app.register_blueprint(
    auth_bp,
    url_prefix="/auth"
)


# ============================================================
# HELPERS
# ============================================================

def allowed_image_extension(filename):
    """
    Check whether the uploaded image has
    an allowed file extension.
    """

    if not filename or "." not in filename:
        return False

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    return extension in ALLOWED_IMAGE_EXTENSIONS


def validate_image(file):
    """
    Validate uploaded image.
    """

    if not file:
        return False, "Invalid image file."

    if not file.filename:
        return False, "Image filename is missing."

    if not allowed_image_extension(
        file.filename
    ):
        return False, (
            "Only JPG, JPEG, PNG and WEBP images are allowed."
        )

    if file.mimetype not in ALLOWED_IMAGE_MIMETYPES:
        return False, "Invalid image format."

    return True, None


def safe_float(value):
    """
    Convert a value to float safely.
    """

    try:

        if value is None or value == "":
            return None

        return float(value)

    except (ValueError, TypeError):

        return None


def safe_int(value):
    """
    Convert a value to integer safely.
    """

    try:

        if value is None or value == "":
            return None

        return int(float(value))

    except (ValueError, TypeError):

        return None


# ============================================================
# MONGODB CONNECTION TEST
# ============================================================

try:

    test_connection()

except Exception as error:

    print(
        "MongoDB connection warning:",
        error
    )


# ============================================================
# LOAD ML MODEL
# ============================================================

price_model = None

try:

    if MODEL_PATH.exists():

        price_model = joblib.load(
            MODEL_PATH
        )

        print(
            "ML price prediction model loaded successfully."
        )

    else:

        print(
            f"ML model not found at: {MODEL_PATH}"
        )

except Exception as error:

    print(
        "ML model loading error:",
        error
    )


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return jsonify({

        "message": "HomeSense AI backend is running",

        "status": "success"

    })


# ============================================================
# SERVE PROPERTY IMAGES
# ============================================================

@app.route(
    "/uploads/properties/<int:property_id>/<filename>"
)
def serve_property_image(
    property_id,
    filename
):

    property_folder = (
        UPLOAD_FOLDER
        / str(property_id)
    )

    return send_from_directory(
        property_folder,
        filename
    )


# ============================================================
# PROPERTY RATE
# ============================================================

@app.route("/property-rate")
def property_rate():

    city = request.args.get(
        "city",
        ""
    )

    property_type = request.args.get(
        "property_type",
        ""
    )

    price = safe_float(
        request.args.get("price")
    )

    area = safe_float(
        request.args.get("area")
    )


    if not city:

        return jsonify({

            "error": "City is required."

        }), 400


    if not property_type:

        return jsonify({

            "error": "Property type is required."

        }), 400


    if price is None or area is None or area <= 0:

        return jsonify({

            "error": "Valid price and area are required."

        }), 400


    result = calculate_rate(
        price,
        area
    )


    return jsonify({

        "city": city,

        "property_type": property_type,

        "price": price,

        "area": area,

        "rate_per_sqft": result

    })


# ============================================================
# SEARCH PROPERTIES
# ============================================================

@app.route("/search-properties")
def search_properties():

    city = request.args.get(
        "city",
        ""
    ).strip().lower()

    property_type = request.args.get(
        "property_type",
        ""
    ).strip().lower()

    price = safe_float(
        request.args.get("price")
    )

    area = safe_float(
        request.args.get("area")
    )

    bedrooms = safe_int(
        request.args.get("bedrooms")
    )


    if not DATA_PATH.exists():

        return jsonify({

            "error": "Property data file not found."

        }), 500


    try:

        df = pd.read_csv(
            DATA_PATH
        )

    except Exception as error:

        return jsonify({

            "error": (
                f"Unable to read property data: {error}"
            )

        }), 500


    result = df.copy()


    if city:

        result = result[

            result["city"]
            .astype(str)
            .str.lower()
            .str.contains(
                city,
                na=False
            )

        ]


    if property_type:

        result = result[

            result["property_type"]
            .astype(str)
            .str.lower()
            .str.contains(
                property_type,
                na=False
            )

        ]


    if price is not None and "price" in result.columns:

        result = result[

            pd.to_numeric(
                result["price"],
                errors="coerce"
            ) <= price

        ]


    if area is not None and "area" in result.columns:

        result = result[

            pd.to_numeric(
                result["area"],
                errors="coerce"
            ) >= area

        ]


    if bedrooms is not None and "bedrooms" in result.columns:

        result = result[

            pd.to_numeric(
                result["bedrooms"],
                errors="coerce"
            ) >= bedrooms

        ]


    properties = result.fillna(
        ""
    ).to_dict(
        orient="records"
    )


    return jsonify({

        "count": len(properties),

        "properties": properties

    })


# ============================================================
# REVERSE GEOCODING
# GPS -> CITY / LOCALITY / ADDRESS
# ============================================================

@app.route("/reverse-geocode")
def reverse_geocode():

    latitude = safe_float(
        request.args.get("lat")
    )

    longitude = safe_float(
        request.args.get("lon")
    )


    if latitude is None or longitude is None:

        return jsonify({

            "success": False,

            "error": (
                "Valid latitude and longitude are required."
            )

        }), 400


    if not (-90 <= latitude <= 90):

        return jsonify({

            "success": False,

            "error": "Invalid latitude."

        }), 400


    if not (-180 <= longitude <= 180):

        return jsonify({

            "success": False,

            "error": "Invalid longitude."

        }), 400


    try:

        query_parameters = urlencode({

            "format": "jsonv2",

            "lat": latitude,

            "lon": longitude,

            "zoom": 18,

            "addressdetails": 1

        })


        url = (
            "https://nominatim.openstreetmap.org/reverse?"
            + query_parameters
        )


        request_object = Request(

            url,

            headers={

                "User-Agent": (
                    "HomeSenseAI/1.0 "
                    "(real-estate-location-feature)"
                ),

                "Accept": "application/json"

            }

        )


        with urlopen(

            request_object,

            timeout=10

        ) as response:

            raw_data = response.read().decode(
                "utf-8"
            )


        location_data = json.loads(
            raw_data
        )


        address = location_data.get(
            "address",
            {}
        )


        # ----------------------------------------------------
        # CITY
        # ----------------------------------------------------

        city = (

            address.get("city")

            or address.get("town")

            or address.get("municipality")

            or address.get("village")

            or address.get("county")

            or ""

        )


        # ----------------------------------------------------
        # LOCALITY
        # ----------------------------------------------------

        locality = (

            address.get("suburb")

            or address.get("neighbourhood")

            or address.get("quarter")

            or address.get("residential")

            or address.get("city_district")

            or ""

        )


        # ----------------------------------------------------
        # FULL ADDRESS
        # ----------------------------------------------------

        full_address = location_data.get(
            "display_name",
            ""
        )


        return jsonify({

            "success": True,

            "city": city,

            "locality": locality,

            "address": full_address

        })


    except Exception as error:

        print(
            "Reverse geocoding error:",
            error
        )


        return jsonify({

            "success": False,

            "error": (
                "Unable to determine the location. "
                "Please enter City and Locality manually."
            )

        }), 500


# ============================================================
# LIST PROPERTY
# ============================================================

@app.route(
    "/list-property",
    methods=["POST"]
)
def list_property():

    required_fields = [

        "owner_id",

        "listing_type",

        "city",

        "locality",

        "property_type",

        "area",

        "price",

        "bedrooms",

        "bathrooms",

        "parking",

        "furnishing",

        "description"

    ]


    # --------------------------------------------------------
    # CHECK REQUIRED FIELDS
    # --------------------------------------------------------

    for field in required_fields:

        value = request.form.get(
            field,
            ""
        ).strip()


        if not value:

            return jsonify({

                "success": False,

                "error": (
                    f"{field} is required."
                )

            }), 400


    # --------------------------------------------------------
    # GET IMAGES
    # --------------------------------------------------------

    images = request.files.getlist(
        "images"
    )


    if not images:

        return jsonify({

            "success": False,

            "error": (
                "At least one property image is required."
            )

        }), 400


    if len(images) > MAX_IMAGES:

        return jsonify({

            "success": False,

            "error": (
                f"Maximum {MAX_IMAGES} images are allowed."
            )

        }), 400


    # --------------------------------------------------------
    # VALIDATE NUMERIC DATA
    # --------------------------------------------------------

    area = safe_float(
        request.form.get("area")
    )

    price = safe_float(
        request.form.get("price")
    )

    bedrooms = safe_int(
        request.form.get("bedrooms")
    )

    bathrooms = safe_int(
        request.form.get("bathrooms")
    )


    if area is None or area <= 0:

        return jsonify({

            "success": False,

            "error": (
                "Area must be a valid positive number."
            )

        }), 400


    if price is None or price <= 0:

        return jsonify({

            "success": False,

            "error": (
                "Price must be a valid positive number."
            )

        }), 400


    if bedrooms is None or bedrooms < 0:

        return jsonify({

            "success": False,

            "error": (
                "Bedrooms must be a valid number."
            )

        }), 400


    if bathrooms is None or bathrooms < 0:

        return jsonify({

            "success": False,

            "error": (
                "Bathrooms must be a valid number."
            )

        }), 400


    # --------------------------------------------------------
    # VALIDATE IMAGES
    # --------------------------------------------------------

    for image in images:

        valid, error_message = validate_image(
            image
        )


        if not valid:

            return jsonify({

                "success": False,

                "error": error_message

            }), 400


        image.seek(
            0,
            2
        )

        image_size = image.tell()

        image.seek(0)


        if image_size > MAX_IMAGE_SIZE:

            return jsonify({

                "success": False,

                "error": (
                    "Each image must be below "
                    f"{MAX_IMAGE_SIZE // (1024 * 1024)} MB."
                )

            }), 400


    # --------------------------------------------------------
    # CREATE PROPERTY ID
    # --------------------------------------------------------

    existing_count = properties_collection.count_documents({})

    property_id = existing_count + 1


    while properties_collection.find_one({

        "property_id": property_id

    }):

        property_id += 1


    # --------------------------------------------------------
    # CREATE PROPERTY FOLDER
    # --------------------------------------------------------

    property_folder = (

        UPLOAD_FOLDER
        / str(property_id)

    )


    property_folder.mkdir(

        parents=True,

        exist_ok=True

    )


    # --------------------------------------------------------
    # SAVE IMAGES
    # --------------------------------------------------------

    image_urls = []


    for image in images:

        original_name = secure_filename(
            image.filename
        )


        extension = Path(
            original_name
        ).suffix.lower()


        unique_filename = (

            f"{uuid4().hex}"
            f"{extension}"

        )


        image_path = (

            property_folder
            / unique_filename

        )


        image.save(
            image_path
        )


        image_url = (

            f"/uploads/properties/"
            f"{property_id}/"
            f"{unique_filename}"

        )


        image_urls.append(
            image_url
        )


    # --------------------------------------------------------
    # PROPERTY DATA
    # --------------------------------------------------------

    property_document = {

        "property_id": property_id,

        "owner_id": request.form.get(
            "owner_id"
        ).strip(),

        "listing_type": request.form.get(
            "listing_type"
        ).strip(),

        "city": request.form.get(
            "city"
        ).strip(),

        "locality": request.form.get(
            "locality"
        ).strip(),

        "property_type": request.form.get(
            "property_type"
        ).strip(),

        "area": area,

        "price": price,

        "bedrooms": bedrooms,

        "bathrooms": bathrooms,

        "parking": request.form.get(
            "parking"
        ).strip(),

        "furnishing": request.form.get(
            "furnishing"
        ).strip(),

        "description": request.form.get(
            "description"
        ).strip(),

        "images": image_urls,

        "image_count": len(image_urls),

        "status": "pending",

        "ai_price_prediction": None,

        "ai_recommendation_score": None,

        "created_at": pd.Timestamp.utcnow().isoformat()

    }


    # --------------------------------------------------------
    # SAVE DETECTED ADDRESS
    # --------------------------------------------------------

    location_address = request.form.get(

        "location_address",

        ""

    ).strip()


    if location_address:

        property_document[
            "location_address"
        ] = location_address


    # --------------------------------------------------------
    # INSERT INTO MONGODB
    # --------------------------------------------------------

    try:

        properties_collection.insert_one(
            property_document
        )

    except Exception as error:

        try:

            for image_file in property_folder.iterdir():

                image_file.unlink()

            property_folder.rmdir()

        except Exception:
            pass


        return jsonify({

            "success": False,

            "error": (
                f"Unable to save property: {error}"
            )

        }), 500


    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "message": (
            "Property listed successfully."
        ),

        "property_id": property_id,

        "status": "pending",

        "image_count": len(image_urls),

        "city": property_document["city"],

        "locality": property_document["locality"]

    }), 201


# ============================================================
# RECOMMEND PROPERTIES
# ============================================================

@app.route("/recommend-properties")
def recommend_properties():

    city = request.args.get(
        "city",
        ""
    ).strip().lower()

    property_type = request.args.get(
        "property_type",
        ""
    ).strip().lower()

    budget = safe_float(
        request.args.get("budget")
    )


    if not DATA_PATH.exists():

        return jsonify({

            "error": (
                "Property data file not found."
            )

        }), 500


    try:

        df = pd.read_csv(
            DATA_PATH
        )

    except Exception as error:

        return jsonify({

            "error": str(error)

        }), 500


    result = df.copy()


    if city:

        result = result[

            result["city"]
            .astype(str)
            .str.lower()
            .str.contains(
                city,
                na=False
            )

        ]


    if property_type:

        result = result[

            result["property_type"]
            .astype(str)
            .str.lower()
            .str.contains(
                property_type,
                na=False
            )

        ]


    if budget is not None and "price" in result.columns:

        result = result[

            pd.to_numeric(
                result["price"],
                errors="coerce"
            ) <= budget

        ]


    properties = result.fillna(
        ""
    ).to_dict(
        orient="records"
    )


    return jsonify({

        "count": len(properties),

        "recommendations": properties

    })


# ============================================================
# PROPERTY DETAILS
# ============================================================

@app.route(
    "/property/<int:property_id>"
)
def property_details(property_id):

    property_data = properties_collection.find_one({

        "property_id": property_id

    })


    if not property_data:

        return jsonify({

            "error": "Property not found."

        }), 404


    property_data["_id"] = str(

        property_data["_id"]

    )


    return jsonify(
        property_data
    )


# ============================================================
# AI PRICE PREDICTION
# ============================================================

@app.route(
    "/predict-price",
    methods=["POST"]
)
def predict_price():

    if price_model is None:

        return jsonify({

            "success": False,

            "error": (
                "Price prediction model is not available."
            )

        }), 500


    data = request.get_json(
        silent=True
    )


    if not data:

        return jsonify({

            "success": False,

            "error": (
                "JSON request body is required."
            )

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


    for field in required_fields:

        if field not in data:

            return jsonify({

                "success": False,

                "error": (
                    f"{field} is required."
                )

            }), 400


    try:

        input_data = pd.DataFrame([{

            "city": data["city"],

            "locality": data["locality"],

            "property_type": data["property_type"],

            "bhk": float(
                data["bhk"]
            ),

            "area_sqft": float(
                data["area_sqft"]
            ),

            "bathrooms": float(
                data["bathrooms"]
            ),

            "balcony": float(
                data["balcony"]
            )

        }])


        prediction = price_model.predict(
            input_data
        )[0]


        return jsonify({

            "success": True,

            "predicted_price": float(
                prediction
            )

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "error": str(error)

        }), 400


# ============================================================
# MONGODB STATUS
# ============================================================

@app.route("/mongodb-status")
def mongodb_status():

    try:

        test_connection()


        return jsonify({

            "success": True,

            "mongodb": "connected"

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "mongodb": "disconnected",

            "error": str(error)

        }), 500


# ============================================================
# FILE TOO LARGE
# ============================================================

@app.errorhandler(413)
def request_entity_too_large(error):

    return jsonify({

        "success": False,

        "error": (
            "Uploaded files are too large. "
            "Please reduce the image size."
        )

    }), 413


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )