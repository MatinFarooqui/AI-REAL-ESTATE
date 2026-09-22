# RealtyKey AI
### Smarter Property Decisions

RealtyKey AI is an AI-powered real estate platform developed as a final-year engineering project. It combines property discovery, intelligent recommendations, machine-learning-based valuation, property comparison, favorites, direct buyer-seller communication, offers, reporting, and user property listings in one platform.

The project is designed to demonstrate how **web development, machine learning, databases, APIs, and cloud/deployment concepts** can work together in a real-world application.

---

## Project Overview

Traditional property platforms mainly focus on listing and searching properties. RealtyKey AI extends this workflow by adding intelligent features that help users understand and evaluate properties.

The platform allows users to:

- Search properties by State, City, and Locality
- Refine results using price, area, BHK, bathrooms, parking, facing, furnishing, and property-age filters
- View detailed property information and images
- Calculate property rate per square foot
- Estimate property value using a machine-learning valuation engine
- View valuation range, confidence, geographic coverage, and supporting factors
- Compare 2–4 properties side by side
- Receive explainable property recommendations
- Save properties to Favorites
- List and publish their own properties
- Upload multiple property images
- Detect property location using GPS
- Chat directly with property owners
- Make and manage property offers
- Report suspicious or incorrect listings
- Receive account and marketplace notifications
- Manage listings through My Listings
- Use an AI Assistant for platform guidance
- Manage users, properties, and reports through an Admin Dashboard

---

## Main Features

### 1. Property Search

Users can browse active marketplace properties using:

- State
- City
- Locality
- Sale / Rent
- Property Type
- Minimum / Maximum Price
- Area
- BHK
- Bathrooms
- Parking
- Facing
- Furnishing
- Property Age

The platform also supports location-based browsing and GPS-assisted location detection.

---

### 2. Property Rate Calculator

The Rate Calculator calculates the property's price per square foot using:

`Total Price ÷ Area`

Example:

`₹7,500,000 ÷ 1,200 sq ft = ₹6,250 / sq ft`

---

### 3. AI Property Valuation

RealtyKey AI uses a trained machine-learning model together with geographic benchmark information to estimate property value.

The valuation workflow considers information such as:

- State
- City
- Locality
- Property Type
- Area
- BHK
- Bathrooms
- Available geographic benchmark data

The system can use broader geographic coverage when detailed locality-level data is limited.

The valuation interface can display:

- Estimated Market Value
- Estimated Price Range
- Rate per Square Foot
- Confidence Level
- Geographic Coverage Level
- Valuation Factors
- Model Weight
- Benchmark Information
- Validation Metrics
- Asking-price anomaly information when an asking price is supplied

The asking price is checked separately for anomaly analysis and is not intended to directly determine the estimated value.

---

### 4. Explainable Recommendations

The recommendation engine matches properties with user preferences such as:

- Location
- Listing type
- Property type
- Budget
- Area
- BHK
- Bathrooms
- Parking
- Facing
- Furnishing

Each recommendation can include reasons explaining why the property matched the selected requirements.

---

### 5. Property Comparison

Users can select **2 to 4 properties** and compare them side by side.

Comparison information includes:

- Asking Price
- AI Estimated Value
- AI Price Range
- AI Confidence
- AI Status
- Location
- Property Type
- Listing Type
- Area
- BHK
- Bathrooms
- Parking
- Facing
- Furnishing
- Property Details

---

### 6. User Property Listings

Authenticated users can publish properties directly to the marketplace.

Supported property types:

- Apartment
- House / Villa
- Plot

Users can provide:

- Listing Type
- Price / Rent
- Location
- Property Details
- Description
- Amenities
- GPS Coordinates
- Property Images

Published listings have an active lifecycle and can be managed through **My Listings**.

---

### 7. Favorites

Users can save properties using the Favorites feature.

Saved properties remain associated with the authenticated user's account.

---

### 8. Buyer-Seller Communication

Users can communicate directly regarding user-owned marketplace listings.

The platform supports:

- Buyer-seller chat
- Quick messages
- Stored conversations
- Message notifications
- Conversation history

---

### 9. Offers

Buyers can submit an offer for a user-owned property.

Sellers can:

- Accept an offer
- Reject an offer

Offer status changes are stored and reflected through the application.

---

### 10. Property Reporting

Users can report potentially problematic listings.

Supported report categories include:

- Suspicious / Scam
- Fake Information
- Duplicate Listing
- Incorrect Details
- Other

Reports are available for administrator review.

---

### 11. AI Assistant

The RealtyKey AI Assistant provides deterministic platform guidance for common questions about:

- Property Search
- Property Listing
- AI Valuation
- Property Comparison
- Recommendations
- Favorites
- Chat
- Offers
- Reports
- Account Settings
- Platform Information

The assistant is designed as a lightweight project feature without requiring a paid external generative-AI service.

---

### 12. Admin Dashboard

The Admin Dashboard provides administrative controls for:

- User management
- User property management
- Report review
- Property removal
- User activation / deactivation
- Report resolution
- Marketplace oversight

Administrative functions are restricted to the configured administrator account.

---

## Technology Stack

### Frontend
- HTML5
- CSS3
- JavaScript
- Responsive UI
- Fetch API

### Backend
- Python
- Flask
- REST-style API endpoints

### Database
- MongoDB Atlas
- PyMongo

### Machine Learning
- Python
- Pandas
- Scikit-learn
- Random Forest-based property valuation
- Geographic benchmark-based valuation logic

### Location Services
- Browser Geolocation API
- OpenStreetMap / Nominatim

### Development Tools
- Visual Studio Code
- Git
- GitHub

---

## System Architecture

```text
                    ┌─────────────────────────┐
                    │       User / Browser    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ HTML / CSS / JavaScript │
                    │       Frontend          │
                    └────────────┬────────────┘
                                 │
                         HTTP / Fetch API
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │      Flask Backend      │
                    │        Python           │
                    └───────┬─────────┬───────┘
                            │         │
              ┌─────────────┘         └─────────────┐
              ▼                                       ▼
    ┌──────────────────┐                  ┌────────────────────┐
    │   MongoDB Atlas  │                  │ ML Valuation Engine│
    │ Users / Listings │                  │ Random Forest +    │
    │ Messages / Offers│                  │ Geographic Data    │
    └──────────────────┘                  └────────────────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │ OpenStreetMap /    │
                  │ Nominatim Services │
                  └────────────────────┘