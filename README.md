# RealtyKey AI

**Smarter Property Decisions**

An AI-enabled real-estate platform for discovering and comparing properties, managing listings, and estimating property values with a trained machine-learning model.

**Live Demo:** [realtykey-ai.vercel.app](https://realtykey-ai.vercel.app)<br>
**Repository:** [MatinFarooqui/AI-REAL-ESTATE](https://github.com/MatinFarooqui/AI-REAL-ESTATE)

## Overview

RealtyKey AI is a functional final-year B.Tech project that brings property search, user listings, buyer-seller communication, recommendations, and valuation into one web application. The browser frontend uses HTML, CSS, and JavaScript; a Flask application provides the API and integrates with MongoDB, the valuation engine, geocoding, and Vercel Blob uploads.

## Key Features

- Account signup, login, session-based authentication, and account management
- Property browsing by state, city, and locality, with price, area, type, and property-detail filters
- Property detail pages, rate-per-square-foot calculator, and GPS-assisted location lookup
- Authenticated property listings with image uploads stored in Vercel Blob
- V6 machine-learning valuation combined with geographic benchmarks
- Property recommendations with match explanations
- Favorites and side-by-side comparison of two to four properties
- Buyer-seller conversations, offers, and marketplace notifications
- Property reporting and administrator controls for users, listings, and reports
- A deterministic assistant for guidance on platform workflows

## AI Valuation

The valuation engine loads the V6 bundle first and retains a V2 fallback. V6 is a scikit-learn Random Forest regression model with a preprocessing component and geographic benchmark tables. The prediction inputs are city, locality, property type, BHK, area, bathrooms, and balcony. The engine blends the model estimate with a benchmark selected from locality, city, state, or national coverage, then returns an estimate and range with coverage and explanatory information. If an asking price is provided, it is evaluated separately for an anomaly indication.

The production artifact is `ml/real_estate_price_model_v6.pkl` (approximately 114 MB). It is not committed to Git; obtain the project artifact separately and place it at that exact path before running valuation locally or creating a Vercel deployment that needs it. Do not retrain the model as part of normal setup. No validation metrics are quoted here; the application reads them from the model bundle.

## Technology Stack

- **Frontend:** HTML5, CSS3, JavaScript, Fetch API
- **Backend:** Python 3.13–3.14, Flask
- **Database:** MongoDB Atlas, PyMongo
- **Machine learning:** scikit-learn, pandas, NumPy, joblib; Random Forest regression
- **Cloud and deployment:** Vercel Python and Node.js functions
- **Image storage:** Vercel Blob using the `@vercel/blob` SDK
- **Location services:** Browser Geolocation API, OpenStreetMap Nominatim
- **Version control:** Git and GitHub

## Architecture

```text
Browser (HTML/CSS/JavaScript)
  ├── HTTP requests ──> Flask API
  │                       ├── MongoDB Atlas: accounts, listings, conversations,
  │                       │   offers, favorites, reports, and notifications
  │                       ├── V6 valuation engine + geographic benchmarks
  │                       └── OpenStreetMap Nominatim for geocoding
  └── Image selection ──> Vercel Blob upload function ──> Vercel Blob
                          └── Uploaded public URLs are submitted to Flask
```

The Blob function verifies the existing Flask session through `/auth/me`, prepares a short-lived signed upload URL, and the browser uploads the image directly to Blob. Flask validates the resulting public Blob URLs when saving a listing.

## Project Structure

```text
AI-REAL-ESTATE/
├── Backend/                 Flask app, authentication, MongoDB, valuation
├── api/                     Vercel Blob upload function
├── data/                    Property data and prepared ML training data
├── frontend/                HTML pages, shared CSS, and JavaScript
├── ml/                      Model training scripts
│   └── real_estate_price_model_v6.pkl  Local deployment artifact; not in Git
├── package.json             Node dependency for Vercel Blob
├── pyproject.toml           Python dependencies and Vercel entrypoint
├── requirements.txt         Python dependency list
├── .env.example             Environment-variable template
└── README.md
```

## Local Setup

### Prerequisites

- Python `>=3.13,<3.15`
- Node.js 20 or newer and npm
- A MongoDB Atlas connection string
- The V6 model artifact at `ml/real_estate_price_model_v6.pkl`

### Install and run

Create a virtual environment, install the Python and Node dependencies, and prepare a local environment file:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
```

Set the required values in `.env`, including `MONGO_URI` and `SECRET_KEY`. Set `ADMIN_EMAIL` if this installation needs an administrator account. SMTP settings are needed for email verification. Then run:

```powershell
python -m Backend.app
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The Flask server serves the frontend and API. The Blob upload endpoint is a Vercel function; test the complete cloud upload flow in the linked Vercel environment with Blob storage configured. Do not put production credentials in source control.

### Environment variables

Names used by the application include:

- `MONGO_URI` — required MongoDB connection string
- `SECRET_KEY` — Flask session signing key; set a stable secret for deployed use
- `ADMIN_EMAIL` — email address granted the administrator role
- `SESSION_COOKIE_SECURE` — secure-cookie setting
- `APP_BASE_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_SSL`, `EMAIL_FROM` — email verification configuration
- `BLOB_READ_WRITE_TOKEN` — Vercel Blob access token; configure it in the Vercel environment, not in Git

See [.env.example](.env.example) for variable names without credentials.

## Deployment

The application is deployed on Vercel at [https://realtykey-ai.vercel.app](https://realtykey-ai.vercel.app). The Vercel Python entrypoint is `Backend.app:app`; the Blob upload endpoint is deployed from `api/blob-upload.js`.

A manual production deployment uses the existing Vercel project and requires the V6 artifact to be present in the deployment source:

```powershell
vercel deploy --prod --archive=tgz
```

The model is deliberately not tracked in this repository because of its size. A source checkout without the artifact will not have V6 valuation until the artifact is supplied through the project's existing deployment process.

## Screenshots

No application screenshots are currently included in the repository.

## Future Scope

- Evaluate additional property data sources and model calibration approaches
- Extend recommendation explanations and user preference controls
- Improve deployment observability and artifact distribution

## Project Status

RealtyKey AI is a functional, deployed final-year project. The linked demo reflects the current application; the trained model artifact is maintained separately from Git source.
