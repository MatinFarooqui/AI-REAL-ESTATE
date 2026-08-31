console.log("JavaScript is connected!");

const button = document.getElementById("searchButton");
const result = document.getElementById("result");

button.addEventListener("click", async function() {

    const city = document.getElementById("city").value;
    const propertyType = document.getElementById("propertyType").value;
    const budget = document.getElementById("budget").value;
    const area = document.getElementById("area").value;
    const bedrooms = document.getElementById("bedrooms").value;

    if (!budget || !area) {
        result.innerHTML = "Please enter budget and area.";
        return;
    }

    try {

        const response = await fetch(
            `http://127.0.0.1:5000/property-rate?city=${city}&property_type=${propertyType}&price=${budget}&area=${area}&bedrooms=${bedrooms}`
        );

        const data = await response.json();

        if (data.error) {
            result.innerHTML = data.error;
            return;
        }

        result.innerHTML = `
            <h3>Property Result</h3>
            <p>City: ${data.city}</p>
            <p>Property Type: ${data.property_type}</p>
            <p>Budget: ₹${data.price}</p>
            <p>Area: ${data.area} sq ft</p>
            <p>Bedrooms: ${data.bedrooms}</p>
            <p>Rate per sq ft: ₹${data.rate_per_sqft}</p>
        `;

    } catch (error) {

        result.innerHTML = "Unable to connect to the backend.";

        console.error(error);
    }
});