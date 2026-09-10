console.log("AI Real Estate JavaScript connected!");

const button = document.getElementById("searchButton");
const result = document.getElementById("result");

// ==========================================
// PROPERTY IMAGE
// ==========================================

function getPropertyImage(propertyType) {
    const type = String(propertyType).toLowerCase();

    if (type === "apartment") {
        return "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1000&q=85";
    }

    if (type === "plot") {
        return "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1000&q=85";
    }

    return "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=85";
}

// ==========================================
// FORMAT PRICE
// ==========================================

function formatPrice(price) {
    return "₹" + Number(price).toLocaleString("en-IN");
}

// ==========================================
// PROPERTY DETAILS URL
// ==========================================

function getDetailsUrl(property) {
    const params = new URLSearchParams({
        id: property.id,
        city: property.city,
        locality: property.locality || "",
        property_type: property.property_type,
        area: property.area,
        budget: property.budget,
        bedrooms: property.bedrooms,
        bathrooms: property.bathrooms || 0,
        parking: property.parking || 0,
        furnishing: property.furnishing || "",
        property_age: property.property_age || 0,
        match_score: property.match_score || 0
    });

    return `property-details.html?${params.toString()}`;
}

// ==========================================
// SEARCH PROPERTIES
// ==========================================

if (button && result) {

    button.addEventListener("click", async function () {

        const city = document.getElementById("city").value.trim();
        const propertyType = document.getElementById("propertyType").value;
        const budget = document.getElementById("budget").value;
        const area = document.getElementById("area").value;
        const bedrooms = document.getElementById("bedrooms").value;

        // --------------------------------------
        // VALIDATION
        // --------------------------------------

        if (!city || !budget || !area) {

            result.innerHTML = `
                <div class="result-empty">
                    <h3>Please complete your search</h3>
                    <p>
                        Enter your city, budget and area
                        to find suitable properties.
                    </p>
                </div>
            `;

            return;
        }

        // --------------------------------------
        // LOADING
        // --------------------------------------

        result.innerHTML = `
            <div class="result-empty">
                <h3>Finding your best properties...</h3>
                <p>
                    Our AI recommendation engine is
                    analysing your requirements.
                </p>
            </div>
        `;

        try {

            const url =
                `http://127.0.0.1:5000/recommend-properties` +
                `?city=${encodeURIComponent(city)}` +
                `&property_type=${encodeURIComponent(propertyType)}` +
                `&budget=${encodeURIComponent(budget)}` +
                `&area=${encodeURIComponent(area)}` +
                `&bedrooms=${encodeURIComponent(bedrooms)}`;

            const response = await fetch(url);

            const data = await response.json();

            // --------------------------------------
            // ERROR
            // --------------------------------------

            if (!response.ok || data.error) {

                result.innerHTML = `
                    <div class="result-empty">
                        <h3>Something went wrong</h3>
                        <p>
                            ${data.error || "Unable to find properties."}
                        </p>
                    </div>
                `;

                return;
            }

            // --------------------------------------
            // NO RESULTS
            // --------------------------------------

            if (data.count === 0) {

                result.innerHTML = `
                    <div class="result-empty">
                        <h3>No suitable properties found</h3>
                        <p>
                            Try changing your budget, area,
                            city or property type.
                        </p>
                    </div>
                `;

                return;
            }

            // --------------------------------------
            // RESULT HEADER
            // --------------------------------------

            let html = `
                <div class="result-heading">

                    <div>
                        <span class="section-label">
                            AI RECOMMENDATIONS
                        </span>

                        <h2>Properties selected for you</h2>

                        <p>
                            ${data.count}
                            properties match your requirements.
                        </p>
                    </div>

                </div>

                <div class="property-grid">
            `;

            // --------------------------------------
            // PROPERTY CARDS
            // --------------------------------------

            data.recommendations.forEach(function (property, index) {

                const image =
                    getPropertyImage(property.property_type);

                const detailsUrl =
                    getDetailsUrl(property);

                html += `
                    <article class="property-card">

                        <div class="property-image">

                            <img
                                src="${image}"
                                alt="${property.property_type} in ${property.city}"
                            >

                            <span class="property-badge">
                                ${index === 0 ? "BEST MATCH" : "AI MATCH"}
                            </span>

                        </div>

                        <div class="property-content">

                            <div class="property-top">

                                <span class="property-category">
                                    ${property.property_type}
                                </span>

                                <span class="match-score">
                                    ${property.match_score}% Match
                                </span>

                            </div>

                            <h3>
                                ${property.locality || property.city}
                            </h3>

                            <p class="property-location">
                                📍
                                ${property.locality
                                    ? property.locality + ", "
                                    : ""}
                                ${property.city}
                            </p>

                            <div class="property-meta">

                                <span>
                                    📐 ${property.area} sq ft
                                </span>

                                ${
                                    property.bedrooms > 0
                                        ? `<span>🛏 ${property.bedrooms} Beds</span>`
                                        : ""
                                }

                                ${
                                    property.bathrooms > 0
                                        ? `<span>🚿 ${property.bathrooms} Baths</span>`
                                        : ""
                                }

                            </div>

                            <div class="property-price-row">

                                <strong>
                                    ${formatPrice(property.budget)}
                                </strong>

                                <span>
                                    ${property.furnishing || ""}
                                </span>

                            </div>

                            <a
                                href="${detailsUrl}"
                                class="text-link"
                            >
                                View Property Details →
                            </a>

                        </div>

                    </article>
                `;
            });

            html += `</div>`;

            result.innerHTML = html;

            // --------------------------------------
            // SCROLL TO RESULTS
            // --------------------------------------

            result.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        } catch (error) {

            console.error("Search error:", error);

            result.innerHTML = `
                <div class="result-empty">

                    <h3>Backend connection error</h3>

                    <p>
                        Please make sure the Flask server
                        is running on port 5000.
                    </p>

                </div>
            `;
        }

    });

}

// ==========================================
// FEATURED PROPERTY CARDS
// ==========================================

function setupFeaturedProperties() {

    const cards =
        document.querySelectorAll(".property-card");

    cards.forEach(function (card) {

        // Don't modify cards generated by search.
        if (card.closest("#result")) {
            return;
        }

        const title =
            card.querySelector("h3");

        const category =
            card.querySelector(".property-category");

        const location =
            card.querySelector(".property-location");

        const meta =
            card.querySelectorAll(".property-meta span");

        const price =
            card.querySelector(".property-price-row strong");

        if (!title || !category || !location || !price) {
            return;
        }

        let city =
            location.textContent
                .replace("📍", "")
                .trim();

        let area = "1000";

        if (meta[0]) {

            const areaText =
                meta[0].textContent
                    .replace(/[^\d]/g, "");

            if (areaText) {
                area = areaText;
            }
        }

        let bedrooms = "0";

        if (meta[1]) {

            const bedroomText =
                meta[1].textContent
                    .replace(/[^\d]/g, "");

            if (bedroomText) {
                bedrooms = bedroomText;
            }
        }

        const property = {

            id: 1,

            city: city,

            locality:
                title.textContent.trim(),

            property_type:
                category.textContent.trim(),

            area: area,

            budget:
                price.textContent
                    .replace(/[^\d]/g, "") || "5000000",

            bedrooms: bedrooms,

            bathrooms: 0,

            parking: 0,

            furnishing: "",

            property_age: 0,

            match_score: 95
        };

        const url =
            getDetailsUrl(property);

        card.style.cursor = "pointer";

        card.addEventListener("click", function () {

            window.location.href = url;

        });

        // Add visible details link

        const content =
            card.querySelector(".property-content");

        if (
            content &&
            !content.querySelector(".featured-details-link")
        ) {

            const link =
                document.createElement("a");

            link.href = url;

            link.className =
                "text-link featured-details-link";

            link.textContent =
                "View Property Details →";

            link.style.display =
                "inline-block";

            link.style.marginTop =
                "16px";

            content.appendChild(link);
        }

    });
}

// ==========================================
// PAGE LOAD
// ==========================================

document.addEventListener(
    "DOMContentLoaded",
    setupFeaturedProperties
);

// ==========================================
// AI PRICE PREDICTION
// ==========================================

const predictButton =
    document.getElementById("predictButton");

const predictionResult =
    document.getElementById("predictionResult");

function formatPredictedPrice(price) {

    return "₹" +
        Number(price).toLocaleString("en-IN", {
            maximumFractionDigits: 0
        });
}

if (predictButton && predictionResult) {

    predictButton.addEventListener(
        "click",
        async function () {

            const city =
                document
                    .getElementById("predictionCity")
                    .value
                    .trim();

            const locality =
                document
                    .getElementById("predictionLocality")
                    .value
                    .trim();

            const propertyType =
                document
                    .getElementById("predictionPropertyType")
                    .value;

            const bhk =
                document
                    .getElementById("predictionBhk")
                    .value;

            const area =
                document
                    .getElementById("predictionArea")
                    .value;

            const bathrooms =
                document
                    .getElementById("predictionBathrooms")
                    .value;

            const balcony =
                document
                    .getElementById("predictionBalcony")
                    .value;

            // --------------------------------------
            // VALIDATION
            // --------------------------------------

            if (!city || !locality || !area) {

                predictionResult.innerHTML = `
                    <div class="prediction-error">

                        <div class="prediction-ai-icon">
                            !
                        </div>

                        <h3>
                            Complete your property details
                        </h3>

                        <p>
                            Please enter the city, locality
                            and area before requesting an
                            AI price estimate.
                        </p>

                    </div>
                `;

                return;
            }

            if (Number(area) <= 0) {

                predictionResult.innerHTML = `
                    <div class="prediction-error">

                        <div class="prediction-ai-icon">
                            !
                        </div>

                        <h3>
                            Enter a valid area
                        </h3>

                        <p>
                            Property area must be greater
                            than zero.
                        </p>

                    </div>
                `;

                return;
            }

            // --------------------------------------
            // DISABLE BUTTON
            // --------------------------------------

            predictButton.disabled = true;

            predictionResult.innerHTML = `
                <div class="prediction-loading">

                    <div class="prediction-spinner"></div>

                    <h3>
                        Analysing property...
                    </h3>

                    <p>
                        Our AI model is estimating
                        the property value.
                    </p>

                </div>
            `;

            // --------------------------------------
            // API REQUEST
            // --------------------------------------

            try {

                const response =
                    await fetch(
                        "http://127.0.0.1:5000/predict-price",
                        {
                            method: "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body: JSON.stringify({

                                city: city,

                                locality: locality,

                                property_type:
                                    propertyType,

                                bhk:
                                    Number(bhk),

                                area_sqft:
                                    Number(area),

                                bathrooms:
                                    Number(bathrooms),

                                balcony:
                                    Number(balcony)
                            })
                        }
                    );

                const data =
                    await response.json();

                // --------------------------------------
                // API ERROR
                // --------------------------------------

                if (
                    !response.ok ||
                    !data.success
                ) {

                    throw new Error(
                        data.error ||
                        "Unable to predict property price."
                    );
                }

                // --------------------------------------
                // SUCCESS
                // --------------------------------------

                predictionResult.innerHTML = `
                    <div class="prediction-success">

                        <div class="prediction-ai-icon">
                            AI
                        </div>

                        <span class="prediction-subtitle">
                            AI ESTIMATED PROPERTY VALUE
                        </span>

                        <strong class="predicted-price">
                            ${formatPredictedPrice(
                                data.predicted_price
                            )}
                        </strong>

                        <p>
                            Estimated value based on the
                            property characteristics provided.
                        </p>

                    </div>
                `;

            } catch (error) {

                console.error(
                    "Price prediction error:",
                    error
                );

                predictionResult.innerHTML = `
                    <div class="prediction-error">

                        <div class="prediction-ai-icon">
                            !
                        </div>

                        <h3>
                            Prediction unavailable
                        </h3>

                        <p>
                            ${
                                error.message ||
                                "Please make sure the Flask backend is running on port 5000."
                            }
                        </p>

                    </div>
                `;

            } finally {

                predictButton.disabled = false;

            }

        }
    );

}