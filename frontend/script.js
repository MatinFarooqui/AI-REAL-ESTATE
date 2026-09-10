console.log("AI Real Estate JavaScript connected!");

const button = document.getElementById("searchButton");
const result = document.getElementById("result");

button.addEventListener("click", async function () {

    const city = document.getElementById("city").value.trim();
    const propertyType = document.getElementById("propertyType").value;
    const budget = document.getElementById("budget").value;
    const area = document.getElementById("area").value;
    const bedrooms = document.getElementById("bedrooms").value;

    if (!city || !budget || !area) {
        result.innerHTML = `
            <p>Please enter city, budget and area.</p>
        `;
        return;
    }

    result.innerHTML = `
        <p>Finding the best properties for you...</p>
    `;

    try {

        const url =
            `http://127.0.0.1:5000/recommend-properties?city=${encodeURIComponent(city)}&property_type=${encodeURIComponent(propertyType)}&budget=${budget}&area=${area}&bedrooms=${bedrooms}`;

        const response = await fetch(url);

        const data = await response.json();

        if (!response.ok || data.error) {
            result.innerHTML = `
                <p>${data.error || "Something went wrong."}</p>
            `;
            return;
        }

        if (data.count === 0) {
            result.innerHTML = `
                <h3>No Suitable Properties Found</h3>
                <p>Try changing your budget, area or property type.</p>
            `;
            return;
        }

        let html = `
            <h3>Recommended Properties</h3>
            <p>${data.count} properties found for you.</p>
        `;

        data.recommendations.forEach(function (property, index) {

            html += `
                <div class="property-card">

                    <div class="property-header">
                        <h4>${index === 0 ? "🏆 Best Match" : "Recommended Property"}</h4>
                        <span>${property.match_score}% Match</span>
                    </div>

                    <h2>${property.property_type}</h2>

                    <p>📍 ${property.city}</p>

                    <p>📐 ${property.area} sq ft</p>

                    <p>💰 ₹${property.budget.toLocaleString("en-IN")}</p>

                    <p>🛏️ ${property.bedrooms} Bedrooms</p>

                    <p><strong>AI Match Score:</strong> ${property.match_score}%</p>

                </div>
            `;

        });

        result.innerHTML = html;

    } catch (error) {

        console.error(error);

        result.innerHTML = `
            <h3>Backend Connection Error</h3>
            <p>Make sure the Flask server is running.</p>
        `;
    }
});