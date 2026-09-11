console.log("HomeSense AI JavaScript connected!");


// =====================================================
// GLOBAL ELEMENTS
// =====================================================

const button =
    document.getElementById("searchButton");

const result =
    document.getElementById("result");


// =====================================================
// PROPERTY IMAGE
// =====================================================

function getPropertyImage(propertyType) {

    const type =
        String(propertyType).toLowerCase();

    if (type === "apartment") {

        return "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1000&q=85";

    }

    if (type === "plot") {

        return "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1000&q=85";

    }

    return "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1000&q=85";
}


// =====================================================
// FORMAT PRICE
// =====================================================

function formatPrice(price) {

    return "₹" +
        Number(price).toLocaleString("en-IN");
}


// =====================================================
// PROPERTY DETAILS URL
// =====================================================

function getDetailsUrl(property) {

    const params =
        new URLSearchParams({

            id: property.id,

            city: property.city,

            locality:
                property.locality || "",

            property_type:
                property.property_type,

            area:
                property.area,

            budget:
                property.budget,

            bedrooms:
                property.bedrooms,

            bathrooms:
                property.bathrooms || 0,

            parking:
                property.parking || 0,

            furnishing:
                property.furnishing || "",

            property_age:
                property.property_age || 0,

            match_score:
                property.match_score || 0
        });

    return `property-details.html?${params.toString()}`;
}


// =====================================================
// SEARCH PROPERTIES
// =====================================================

if (button && result) {

    button.addEventListener(
        "click",
        async function () {

            const city =
                document
                    .getElementById("city")
                    .value
                    .trim();

            const propertyType =
                document
                    .getElementById("propertyType")
                    .value;

            const budget =
                document
                    .getElementById("budget")
                    .value;

            const area =
                document
                    .getElementById("area")
                    .value;

            const bedrooms =
                document
                    .getElementById("bedrooms")
                    .value;


            // -----------------------------------------
            // VALIDATION
            // -----------------------------------------

            if (!city || !budget || !area) {

                result.innerHTML = `

                    <div class="result-empty">

                        <h3>
                            Please complete your search
                        </h3>

                        <p>
                            Enter your city, budget and area
                            to find suitable properties.
                        </p>

                    </div>

                `;

                return;
            }


            // -----------------------------------------
            // LOADING
            // -----------------------------------------

            result.innerHTML = `

                <div class="result-empty">

                    <h3>
                        Finding your best properties...
                    </h3>

                    <p>
                        HomeSense AI is analysing
                        your requirements.
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


                const response =
                    await fetch(url);


                const data =
                    await response.json();


                // -----------------------------------------
                // ERROR
                // -----------------------------------------

                if (
                    !response.ok ||
                    data.error
                ) {

                    result.innerHTML = `

                        <div class="result-empty">

                            <h3>
                                Something went wrong
                            </h3>

                            <p>
                                ${
                                    data.error ||
                                    "Unable to find properties."
                                }
                            </p>

                        </div>

                    `;

                    return;
                }


                // -----------------------------------------
                // NO RESULTS
                // -----------------------------------------

                if (data.count === 0) {

                    result.innerHTML = `

                        <div class="result-empty">

                            <h3>
                                No suitable properties found
                            </h3>

                            <p>
                                Try changing your budget, area,
                                city or property type.
                            </p>

                        </div>

                    `;

                    return;
                }


                // -----------------------------------------
                // RESULT HEADER
                // -----------------------------------------

                let html = `

                    <div class="result-heading">

                        <div>

                            <span class="section-label">
                                HOMESENSE AI RECOMMENDATIONS
                            </span>

                            <h2>
                                Properties selected for you
                            </h2>

                            <p>
                                ${data.count}
                                properties match your requirements.
                            </p>

                        </div>

                    </div>

                    <div class="property-grid">

                `;


                // -----------------------------------------
                // PROPERTY CARDS
                // -----------------------------------------

                data.recommendations.forEach(
                    function (property, index) {

                        const image =
                            getPropertyImage(
                                property.property_type
                            );


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

                                        ${
                                            index === 0
                                                ? "BEST MATCH"
                                                : "AI MATCH"
                                        }

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

                                        ${
                                            property.locality ||
                                            property.city
                                        }

                                    </h3>


                                    <p class="property-location">

                                        📍

                                        ${
                                            property.locality
                                                ? property.locality + ", "
                                                : ""
                                        }

                                        ${property.city}

                                    </p>


                                    <div class="property-meta">

                                        <span>
                                            📐 ${property.area} sq ft
                                        </span>


                                        ${
                                            property.bedrooms > 0
                                                ? `

                                                    <span>
                                                        🛏 ${property.bedrooms} Beds
                                                    </span>

                                                  `
                                                : ""
                                        }


                                        ${
                                            property.bathrooms > 0
                                                ? `

                                                    <span>
                                                        🚿 ${property.bathrooms} Baths
                                                    </span>

                                                  `
                                                : ""
                                        }

                                    </div>


                                    <div class="property-price-row">

                                        <strong>

                                            ${formatPrice(
                                                property.budget
                                            )}

                                        </strong>


                                        <span>

                                            ${
                                                property.furnishing ||
                                                ""
                                            }

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
                    }
                );


                html += `
                    </div>
                `;


                result.innerHTML =
                    html;


                // -----------------------------------------
                // SCROLL
                // -----------------------------------------

                result.scrollIntoView({
                    behavior: "smooth",
                    block: "start"
                });


            } catch (error) {

                console.error(
                    "Search error:",
                    error
                );


                result.innerHTML = `

                    <div class="result-empty">

                        <h3>
                            Backend connection error
                        </h3>

                        <p>
                            Please make sure the Flask server
                            is running on port 5000.
                        </p>

                    </div>

                `;
            }

        }
    );
}


// =====================================================
// FEATURED PROPERTY CARDS
// =====================================================

function setupFeaturedProperties() {

    const cards =
        document.querySelectorAll(
            ".property-card"
        );


    cards.forEach(
        function (card) {

            if (
                card.closest("#result")
            ) {
                return;
            }


            const title =
                card.querySelector("h3");


            const category =
                card.querySelector(
                    ".property-category"
                );


            const location =
                card.querySelector(
                    ".property-location"
                );


            const meta =
                card.querySelectorAll(
                    ".property-meta span"
                );


            const price =
                card.querySelector(
                    ".property-price-row strong"
                );


            if (
                !title ||
                !category ||
                !location ||
                !price
            ) {
                return;
            }


            let city =
                location.textContent
                    .replace("📍", "")
                    .trim();


            let area = "1000";


            if (meta[0]) {

                const areaText =
                    meta[0]
                        .textContent
                        .replace(/[^\d]/g, "");


                if (areaText) {

                    area =
                        areaText;

                }

            }


            let bedrooms = "0";


            if (meta[1]) {

                const bedroomText =
                    meta[1]
                        .textContent
                        .replace(/[^\d]/g, "");


                if (bedroomText) {

                    bedrooms =
                        bedroomText;

                }

            }


            const property = {

                id: 1,

                city:
                    city,

                locality:
                    title.textContent.trim(),

                property_type:
                    category.textContent.trim(),

                area:
                    area,

                budget:
                    price.textContent
                        .replace(/[^\d]/g, "") ||
                    "5000000",

                bedrooms:
                    bedrooms,

                bathrooms:
                    0,

                parking:
                    0,

                furnishing:
                    "",

                property_age:
                    0,

                match_score:
                    95

            };


            const url =
                getDetailsUrl(property);


            card.style.cursor =
                "pointer";


            card.addEventListener(
                "click",
                function () {

                    window.location.href =
                        url;

                }
            );


            // -----------------------------------------
            // DETAILS LINK
            // -----------------------------------------

            const content =
                card.querySelector(
                    ".property-content"
                );


            if (
                content &&
                !content.querySelector(
                    ".featured-details-link"
                )
            ) {

                const link =
                    document.createElement(
                        "a"
                    );


                link.href =
                    url;


                link.className =
                    "text-link featured-details-link";


                link.textContent =
                    "View Property Details →";


                link.style.display =
                    "inline-block";


                link.style.marginTop =
                    "16px";


                content.appendChild(
                    link
                );

            }

        }
    );
}


// =====================================================
// FAVORITE BUTTONS
// =====================================================

function setupFavoriteButtons() {

    const favoriteButtons =
        document.querySelectorAll(
            ".favorite-button"
        );


    favoriteButtons.forEach(
        function (favoriteButton) {

            favoriteButton.addEventListener(
                "click",
                function (event) {

                    event.stopPropagation();


                    favoriteButton.classList.toggle(
                        "active"
                    );


                    if (
                        favoriteButton.classList.contains(
                            "active"
                        )
                    ) {

                        favoriteButton.textContent =
                            "♥";

                    } else {

                        favoriteButton.textContent =
                            "♡";

                    }

                }
            );

        }
    );
}


// =====================================================
// PAGE LOAD
// =====================================================

document.addEventListener(
    "DOMContentLoaded",
    function () {

        setupFeaturedProperties();

        setupFavoriteButtons();

    }
);


// =====================================================
// AI PRICE PREDICTION
// =====================================================

const predictButton =
    document.getElementById(
        "predictButton"
    );


const predictionResult =
    document.getElementById(
        "predictionResult"
    );


function formatPredictedPrice(price) {

    return "₹" +
        Number(price).toLocaleString(
            "en-IN",
            {
                maximumFractionDigits: 0
            }
        );
}


if (
    predictButton &&
    predictionResult
) {

    predictButton.addEventListener(
        "click",
        async function () {

            const city =
                document
                    .getElementById(
                        "predictionCity"
                    )
                    .value
                    .trim();


            const locality =
                document
                    .getElementById(
                        "predictionLocality"
                    )
                    .value
                    .trim();


            const propertyType =
                document
                    .getElementById(
                        "predictionPropertyType"
                    )
                    .value;


            const bhk =
                document
                    .getElementById(
                        "predictionBhk"
                    )
                    .value;


            const area =
                document
                    .getElementById(
                        "predictionArea"
                    )
                    .value;


            const bathrooms =
                document
                    .getElementById(
                        "predictionBathrooms"
                    )
                    .value;


            const balcony =
                document
                    .getElementById(
                        "predictionBalcony"
                    )
                    .value;


            // -----------------------------------------
            // VALIDATION
            // -----------------------------------------

            if (
                !city ||
                !locality ||
                !area
            ) {

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


            if (
                Number(area) <= 0
            ) {

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


            // -----------------------------------------
            // DISABLE BUTTON
            // -----------------------------------------

            predictButton.disabled =
                true;


            predictionResult.innerHTML = `

                <div class="prediction-loading">

                    <div class="prediction-spinner"></div>

                    <h3>
                        Analysing property...
                    </h3>

                    <p>
                        HomeSense AI is estimating
                        the property value.
                    </p>

                </div>

            `;


            // -----------------------------------------
            // API REQUEST
            // -----------------------------------------

            try {

                const response =
                    await fetch(
                        "http://127.0.0.1:5000/predict-price",
                        {

                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json"
                            },

                            body:
                                JSON.stringify({

                                    city:
                                        city,

                                    locality:
                                        locality,

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


                // -----------------------------------------
                // API ERROR
                // -----------------------------------------

                if (
                    !response.ok ||
                    !data.success
                ) {

                    throw new Error(
                        data.error ||
                        "Unable to predict property price."
                    );

                }


                // -----------------------------------------
                // SUCCESS
                // -----------------------------------------

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

                predictButton.disabled =
                    false;

            }

        }
    );
}


// =====================================================
// PROPERTY IMAGE UPLOAD
// =====================================================

const listingImages =
    document.getElementById(
        "listingImages"
    );


const imagePreview =
    document.getElementById(
        "imagePreview"
    );


const imageUploadInfo =
    document.getElementById(
        "imageUploadInfo"
    );


// =====================================================
// UPLOAD LIMITS
// =====================================================

const MAX_IMAGES =
    20;


// 100 MB PER IMAGE

const MAX_IMAGE_SIZE =
    100 * 1024 * 1024;


// Selected image files

let selectedImages =
    [];


// =====================================================
// UPDATE FILE INPUT
// =====================================================

function updateImageInput() {

    if (!listingImages) {
        return;
    }


    const dataTransfer =
        new DataTransfer();


    selectedImages.forEach(
        function (file) {

            dataTransfer.items.add(
                file
            );

        }
    );


    listingImages.files =
        dataTransfer.files;
}


// =====================================================
// RENDER IMAGE PREVIEWS
// =====================================================

function renderImagePreviews() {

    if (
        !imagePreview ||
        !imageUploadInfo
    ) {
        return;
    }


    imagePreview.innerHTML =
        "";


    if (
        selectedImages.length === 0
    ) {

        imageUploadInfo.textContent =
            "No photos selected";

        return;
    }


    imageUploadInfo.textContent =
        `${selectedImages.length} / ${MAX_IMAGES} photos selected`;


    selectedImages.forEach(
        function (file, index) {

            const preview =
                document.createElement(
                    "div"
                );


            preview.className =
                "image-preview-item";


            const image =
                document.createElement(
                    "img"
                );


            image.src =
                URL.createObjectURL(
                    file
                );


            image.alt =
                `Property photo ${index + 1}`;


            const removeButton =
                document.createElement(
                    "button"
                );


            removeButton.type =
                "button";


            removeButton.className =
                "image-remove-button";


            removeButton.textContent =
                "×";


            removeButton.title =
                "Remove image";


            removeButton.addEventListener(
                "click",
                function () {

                    selectedImages.splice(
                        index,
                        1
                    );


                    updateImageInput();


                    renderImagePreviews();

                }
            );


            preview.appendChild(
                image
            );


            preview.appendChild(
                removeButton
            );


            imagePreview.appendChild(
                preview
            );

        }
    );
}


// =====================================================
// IMAGE FILE SELECTION
// =====================================================

if (listingImages) {

    listingImages.addEventListener(
        "change",
        function () {

            const files =
                Array.from(
                    listingImages.files
                );


            // -----------------------------------------
            // MAX 20 IMAGES
            // -----------------------------------------

            if (
                selectedImages.length +
                files.length >
                MAX_IMAGES
            ) {

                alert(
                    "You can upload a maximum of 20 images per property."
                );


                updateImageInput();

                return;
            }


            // -----------------------------------------
            // VALIDATE EACH IMAGE
            // -----------------------------------------

            for (
                const file of files
            ) {

                const isImage =
                    [
                        "image/jpeg",
                        "image/png",
                        "image/webp"
                    ].includes(
                        file.type
                    );


                // INVALID FORMAT

                if (!isImage) {

                    alert(
                        `${file.name} is not a supported image format. Please use JPG, PNG or WEBP.`
                    );

                    continue;
                }


                // -----------------------------------------
                // 100 MB SIZE LIMIT
                // -----------------------------------------

                if (
                    file.size >
                    MAX_IMAGE_SIZE
                ) {

                    alert(
                        `${file.name} is larger than 100 MB. Please select an image below 100 MB.`
                    );

                    continue;
                }


                // -----------------------------------------
                // DUPLICATE CHECK
                // -----------------------------------------

                const duplicate =
                    selectedImages.some(
                        function (existingFile) {

                            return (
                                existingFile.name === file.name &&
                                existingFile.size === file.size &&
                                existingFile.lastModified === file.lastModified
                            );

                        }
                    );


                if (duplicate) {

                    alert(
                        `${file.name} has already been selected.`
                    );

                    continue;
                }


                // -----------------------------------------
                // ADD IMAGE
                // -----------------------------------------

                selectedImages.push(
                    file
                );

            }


            updateImageInput();

            renderImagePreviews();

        }
    );
}


// =====================================================
// LIST YOUR PROPERTY
// =====================================================

const propertyListingForm =
    document.getElementById(
        "propertyListingForm"
    );


const listingSubmitButton =
    document.getElementById(
        "listingSubmitButton"
    );


const listingResult =
    document.getElementById(
        "listingResult"
    );


if (
    propertyListingForm &&
    listingSubmitButton &&
    listingResult
) {

    propertyListingForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();


            // -----------------------------------------
            // READ FORM DATA
            // -----------------------------------------

            const ownerId =
                document
                    .getElementById(
                        "listingOwnerId"
                    )
                    .value
                    .trim();


            const listingType =
                document
                    .getElementById(
                        "listingType"
                    )
                    .value;


            const city =
                document
                    .getElementById(
                        "listingCity"
                    )
                    .value
                    .trim();


            const locality =
                document
                    .getElementById(
                        "listingLocality"
                    )
                    .value
                    .trim();


            const propertyType =
                document
                    .getElementById(
                        "listingPropertyType"
                    )
                    .value;


            const area =
                document
                    .getElementById(
                        "listingArea"
                    )
                    .value;


            const price =
                document
                    .getElementById(
                        "listingPrice"
                    )
                    .value;


            const bedrooms =
                document
                    .getElementById(
                        "listingBedrooms"
                    )
                    .value;


            const bathrooms =
                document
                    .getElementById(
                        "listingBathrooms"
                    )
                    .value;


            const parking =
                document
                    .getElementById(
                        "listingParking"
                    )
                    .value;


            const furnishing =
                document
                    .getElementById(
                        "listingFurnishing"
                    )
                    .value;


            const description =
                document
                    .getElementById(
                        "listingDescription"
                    )
                    .value
                    .trim();


            // -----------------------------------------
            // CLIENT VALIDATION
            // -----------------------------------------

            if (
                !ownerId ||
                !city ||
                !locality ||
                !area ||
                !price ||
                !description
            ) {

                listingResult.innerHTML = `

                    <div class="listing-error">

                        <h3>
                            Complete the listing form
                        </h3>

                        <p>
                            Please fill in all required
                            property information.
                        </p>

                    </div>

                `;

                return;
            }


            if (
                Number(area) <= 0 ||
                Number(price) <= 0
            ) {

                listingResult.innerHTML = `

                    <div class="listing-error">

                        <h3>
                            Invalid property value
                        </h3>

                        <p>
                            Area and price must be greater
                            than zero.
                        </p>

                    </div>

                `;

                return;
            }


            // -----------------------------------------
            // IMAGE VALIDATION
            // -----------------------------------------

            if (
                selectedImages.length === 0
            ) {

                listingResult.innerHTML = `

                    <div class="listing-error">

                        <h3>
                            Add property photos
                        </h3>

                        <p>
                            Please upload at least one
                            property photo.
                        </p>

                    </div>

                `;

                return;
            }


            if (
                selectedImages.length >
                MAX_IMAGES
            ) {

                listingResult.innerHTML = `

                    <div class="listing-error">

                        <h3>
                            Too many photos
                        </h3>

                        <p>
                            You can upload a maximum
                            of 20 photos.
                        </p>

                    </div>

                `;

                return;
            }


            // -----------------------------------------
            // FINAL IMAGE SIZE CHECK
            // -----------------------------------------

            const oversizedImage =
                selectedImages.find(
                    function (file) {

                        return (
                            file.size >
                            MAX_IMAGE_SIZE
                        );

                    }
                );


            if (oversizedImage) {

                listingResult.innerHTML = `

                    <div class="listing-error">

                        <h3>
                            Image size limit exceeded
                        </h3>

                        <p>
                            ${oversizedImage.name}
                            is larger than 100 MB.
                            Please remove it and select
                            a smaller image.
                        </p>

                    </div>

                `;

                return;
            }


            // -----------------------------------------
            // LOADING
            // -----------------------------------------

            listingSubmitButton.disabled =
                true;


            listingSubmitButton.innerHTML =
                "Uploading property...";


            listingResult.innerHTML = `

                <div class="listing-success">

                    <h3>
                        Uploading your property...
                    </h3>

                    <p>
                        HomeSense AI is securely uploading
                        your property information and photos.
                    </p>

                </div>

            `;


            // -----------------------------------------
            // FORM DATA
            // -----------------------------------------

            const formData =
                new FormData();


            formData.append(
                "owner_id",
                ownerId
            );


            formData.append(
                "listing_type",
                listingType
            );


            formData.append(
                "city",
                city
            );


            formData.append(
                "locality",
                locality
            );


            formData.append(
                "property_type",
                propertyType
            );


            formData.append(
                "area",
                Number(area)
            );


            formData.append(
                "price",
                Number(price)
            );


            formData.append(
                "bedrooms",
                Number(bedrooms)
            );


            formData.append(
                "bathrooms",
                Number(bathrooms)
            );


            formData.append(
                "parking",
                Number(parking)
            );


            formData.append(
                "furnishing",
                furnishing
            );


            formData.append(
                "description",
                description
            );


            // -----------------------------------------
            // ADD IMAGES
            // -----------------------------------------

            selectedImages.forEach(
                function (file) {

                    formData.append(
                        "images",
                        file
                    );

                }
            );


            // -----------------------------------------
            // API REQUEST
            // -----------------------------------------

            try {

                const response =
                    await fetch(
                        "http://127.0.0.1:5000/list-property",
                        {

                            method:
                                "POST",

                            body:
                                formData

                        }
                    );


                const data =
                    await response.json();


                // -----------------------------------------
                // API ERROR
                // -----------------------------------------

                if (
                    !response.ok ||
                    !data.success
                ) {

                    throw new Error(
                        data.error ||
                        "Unable to submit property."
                    );

                }


                // -----------------------------------------
                // SUCCESS
                // -----------------------------------------

                listingResult.innerHTML = `

                    <div class="listing-success">

                        <h3>
                            Property submitted successfully
                        </h3>

                        <p>
                            Your property and photos have
                            been stored successfully.
                        </p>

                        <span class="listing-property-id">

                            Property ID:
                            ${data.property_id}

                            &nbsp; • &nbsp;

                            Photos:
                            ${data.image_count}

                            &nbsp; • &nbsp;

                            Status:
                            ${data.status}

                        </span>

                    </div>

                `;


                // -----------------------------------------
                // RESET FORM
                // -----------------------------------------

                propertyListingForm.reset();


                selectedImages =
                    [];


                updateImageInput();


                renderImagePreviews();


                document.getElementById(
                    "listingType"
                ).value =
                    "Sell";


                // -----------------------------------------
                // SCROLL RESULT
                // -----------------------------------------

                listingResult.scrollIntoView({
                    behavior:
                        "smooth",

                    block:
                        "center"
                });


            } catch (error) {

                console.error(
                    "Property listing error:",
                    error
                );


                listingResult.innerHTML = `

                    <div class="listing-error">

                        <h3>
                            Property submission failed
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

                listingSubmitButton.disabled =
                    false;


                listingSubmitButton.innerHTML =
                    `
                        Submit Property
                        <span>→</span>
                    `;

            }

        }
    );
}