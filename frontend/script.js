"use strict";

console.log("RealtyKey AI: Smarter Property Decisions connected");

const FALLBACK_IMAGES = {
    apartment: "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=1200&q=85",
    plot: "https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=1200&q=85",
    house: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=85"
};

let currentUser = null;
let currentSearchPage = 1;
const comparePropertyIds = new Set();
let locationHierarchyData = {};
let activeChatPollInterval = null;
let locationSearchTimers = new WeakMap();

// ============================================================
// GENERIC HELPERS
// ============================================================

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};
    try {
        data = await response.json();
    } catch {
        data = { success: false, error: `Server returned HTTP ${response.status}.` };
    }
    if (!response.ok) {
        throw new Error(data.error || `Request failed with HTTP ${response.status}.`);
    }
    return data;
}

function formatPrice(value) {
    const num = Number(value || 0);
    if (num >= 10000000) return `₹${(num / 10000000).toFixed(2)} Cr`;
    if (num >= 100000) return `₹${(num / 100000).toFixed(2)} Lakh`;
    return `₹${num.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatPriceFull(value) {
    return `₹${Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatDate(value) {
    if (!value) return "";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function getPropertyId(property) {
    return Number(property?.property_id ?? property?.id ?? 0);
}

function getDetailsUrl(property) {
    return `property-details.html?id=${encodeURIComponent(getPropertyId(property))}`;
}

function getPropertyImage(property) {
    if (Array.isArray(property?.images) && property.images.length && property.images[0]) return property.images[0];
    const type = String(property?.property_type || "house").toLowerCase();
    if (type === "apartment") return FALLBACK_IMAGES.apartment;
    if (type === "plot") return FALLBACK_IMAGES.plot;
    return FALLBACK_IMAGES.house;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setInputValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value == null ? "" : value;
}

function showAuthModal(title, message) {
    const modal = document.getElementById("authModal");
    if (!modal) {
        alert(`${title}\n\n${message}`);
        return;
    }
    setText("authModalTitle", title);
    setText("authModalMessage", message);
    modal.classList.add("active");
}

function closeAuthModal() {
    document.getElementById("authModal")?.classList.remove("active");
}

// ============================================================
// AUTHENTICATION
// ============================================================

async function getCurrentUser() {
    try {
        const data = await fetchJson("/auth/me", { credentials: "include" });
        currentUser = data.logged_in ? data.user : null;
    } catch {
        currentUser = null;
    }
    return currentUser;
}

function ensureAuthLinks() {
    const guest = document.getElementById("guestAuth");
    const userMenu = document.getElementById("userMenu");
    const userName = document.getElementById("userName");
    const avatar = document.getElementById("userAvatar");

    if (guest) guest.style.display = currentUser ? "none" : "flex";
    if (userMenu) userMenu.style.display = currentUser ? "flex" : "none";

    if (!currentUser) return;

    if (userName) userName.textContent = currentUser.name || "Account";
    if (avatar) avatar.textContent = (currentUser.name || "U").slice(0, 1).toUpperCase();

    const links = document.querySelector(".dynamic-account-links");
    if (links && !document.getElementById("favoritesNavLink")) {
        const fav = document.createElement("a");
        fav.id = "favoritesNavLink";
        fav.href = "#favoritesSection";
        fav.className = "auth-link";
        fav.textContent = "Favorites";
        links.insertBefore(fav, links.firstChild);
    }

    if (currentUser.role === "admin" && !document.getElementById("adminNavLink")) {
        const adminLink = document.createElement("a");
        adminLink.id = "adminNavLink";
        adminLink.href = "admin.html";
        adminLink.className = "auth-link admin-nav-link";
        adminLink.textContent = "Admin";
        userMenu?.parentNode?.insertBefore(adminLink, userMenu);
    }

    loadNotifications();
}

function setupAuthActions() {
    const logoutBtn = document.getElementById("logoutButton");
    logoutBtn?.addEventListener("click", async () => {
        try { await fetch("/auth/logout", { method: "POST", credentials: "include" }); } finally { window.location.href = "index.html"; }
    });

    const accountBtn = document.getElementById("accountMenuBtn");
    const accountDropdown = document.getElementById("accountSettingsDropdown");
    if (accountBtn && accountDropdown) {
        accountBtn.addEventListener("click", e => {
            e.stopPropagation();
            accountDropdown.style.display = accountDropdown.style.display === "none" ? "block" : "none";
        });
        document.addEventListener("click", e => {
            if (!accountDropdown.contains(e.target) && e.target !== accountBtn) accountDropdown.style.display = "none";
        });
    }

    const changeBtn = document.getElementById("openChangePasswordBtn");
    const changeModal = document.getElementById("changePasswordModal");
    changeBtn?.addEventListener("click", () => changeModal?.classList.add("active"));
    document.getElementById("closeChangePassword")?.addEventListener("click", () => changeModal?.classList.remove("active"));
    document.getElementById("changePasswordForm")?.addEventListener("submit", async e => {
        e.preventDefault();
        const status = document.getElementById("changePassStatus");
        if (status) status.textContent = "Updating password...";
        try {
            await fetchJson("/auth/change-password", {
                method: "POST", credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    current_password: document.getElementById("currPassInput")?.value || "",
                    new_password: document.getElementById("newPassInput")?.value || ""
                })
            });
            if (status) status.textContent = "✓ Password updated successfully.";
            setTimeout(() => {
                changeModal?.classList.remove("active");
                e.target.reset();
                if (status) status.textContent = "";
            }, 1200);
        } catch (err) {
            if (status) status.textContent = `✕ ${err.message}`;
        }
    });

    const deleteBtn = document.getElementById("openDeleteAccountBtn");
    const deleteModal = document.getElementById("deleteAccountModal");
    deleteBtn?.addEventListener("click", () => deleteModal?.classList.add("active"));
    document.getElementById("closeDeleteAccount")?.addEventListener("click", () => deleteModal?.classList.remove("active"));
    document.getElementById("deleteAccountForm")?.addEventListener("submit", async e => {
        e.preventDefault();
        if (!confirm("This permanently deletes your account, listings and associated app data. Continue?")) return;
        const status = document.getElementById("deleteAccountStatus");
        if (status) status.textContent = "Deleting account...";
        try {
            await fetchJson("/auth/delete-account", {
                method: "POST", credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ password: document.getElementById("deletePassInput")?.value || "" })
            });
            alert("Your account has been deleted.");
            window.location.href = "index.html";
        } catch (err) {
            if (status) status.textContent = `✕ ${err.message}`;
        }
    });

    document.querySelectorAll(".protected-action").forEach(element => {
        if (element.dataset.authBound) return;
        element.dataset.authBound = "1";
        element.addEventListener("click", event => {
            if (currentUser) return;
            event.preventDefault();
            showAuthModal("Login required", `Please login to ${element.dataset.action || "continue"}.`);
        });
    });
}

function setupAuthModal() {
    document.getElementById("closeAuthModal")?.addEventListener("click", closeAuthModal);
    const modal = document.getElementById("authModal");
    modal?.addEventListener("click", e => { if (e.target === modal) closeAuthModal(); });
}

// ============================================================
// NOTIFICATIONS
// ============================================================

async function loadNotifications() {
    if (!currentUser) return;
    try {
        const data = await fetchJson("/api/notifications", { credentials: "include" });
        const unread = Number(data.unread || 0);
        const badge = document.getElementById("notifBadge");
        const count = document.getElementById("unreadCountText");
        const list = document.getElementById("notifList");
        if (badge) { badge.textContent = unread; badge.style.display = unread ? "flex" : "none"; }
        if (count) count.textContent = `${unread} unread`;
        if (!list) return;
        if (!data.notifications?.length) {
            list.innerHTML = `<p style="font-size:12px;color:#94a3b8;text-align:center;padding:12px">No notifications</p>`;
            return;
        }
        list.innerHTML = data.notifications.map(n => `
            <div class="notif-item ${n.read ? "" : "unread"}" data-id="${escapeHtml(n.notification_id)}" data-link="${escapeHtml(n.link || "")}">
                <strong style="display:block;color:#1e293b;font-size:13px">${escapeHtml(n.title)}</strong>
                <span style="display:block;color:#64748b;font-size:12px;margin-top:2px">${escapeHtml(n.body)}</span>
                <small style="display:block;color:#94a3b8;font-size:10px;margin-top:4px">${formatDate(n.created_at)}</small>
            </div>
        `).join("");
        list.querySelectorAll(".notif-item").forEach(item => item.addEventListener("click", async () => {
            await fetch(`/api/notifications/${encodeURIComponent(item.dataset.id)}/read`, { method: "POST", credentials: "include" });
            const link = item.dataset.link;
            if (link) window.location.href = link;
            else loadNotifications();
        }));
    } catch { /* non-fatal */ }
}

function setupNotificationsDropdown() {
    const btn = document.getElementById("notifButton");
    const dropdown = document.getElementById("notifDropdown");
    if (!btn || !dropdown) return;
    btn.addEventListener("click", e => { e.stopPropagation(); dropdown.classList.toggle("active"); if (dropdown.classList.contains("active")) loadNotifications(); });
    document.addEventListener("click", e => { if (!dropdown.contains(e.target) && e.target !== btn) dropdown.classList.remove("active"); });
}

// ============================================================
// LOCATION / SEARCH
// ============================================================

async function loadLocationHierarchy() {
    try {
        const data = await fetchJson("/location-hierarchy");
        locationHierarchyData = data.hierarchy || {};
        const select = document.getElementById("searchState");
        if (select && Object.keys(locationHierarchyData).length) {
            const old = select.value;
            const states = Object.keys(locationHierarchyData).sort();
            select.innerHTML = `<option value="">All States</option>` + states.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
            if (states.includes(old)) select.value = old;
        }
        bindHierarchyCityHints();
    } catch {
        locationHierarchyData = {};
    }
}

function bindHierarchyCityHints() {
    const cityInput = document.getElementById("searchCity");
    if (!cityInput || cityInput.dataset.hierarchyBound) return;
    cityInput.dataset.hierarchyBound = "1";
    const update = () => {
        const state = document.getElementById("searchState")?.value || "";
        if (!state || !locationHierarchyData[state]) return;
        const cities = Object.keys(locationHierarchyData[state]).sort();
        cityInput.setAttribute("list", "realtykey-city-options");
        let datalist = document.getElementById("realtykey-city-options");
        if (!datalist) { datalist = document.createElement("datalist"); datalist.id = "realtykey-city-options"; document.body.appendChild(datalist); }
        datalist.innerHTML = cities.map(c => `<option value="${escapeHtml(c)}"></option>`).join("");
    };
    document.getElementById("searchState")?.addEventListener("change", update);
    update();
}

function addOptionalSearchFilters() {
    const panel = document.getElementById("optionalFiltersPanel");
    if (!panel || document.getElementById("filterBathrooms")) return;
    const fields = [
        ["filterBathrooms", "BATHROOMS", "number", "Min baths"],
        ["filterParking", "PARKING", "number", "Min spaces"],
        ["filterMaxArea", "MAX AREA (SQ FT)", "number", "Sq ft"],
        ["filterMinAge", "MIN AGE (YEARS)", "number", "Min age"],
        ["filterMaxAge", "MAX AGE (YEARS)", "number", "Max age"]
    ];
    fields.forEach(([id, label, type, placeholder]) => {
        const wrap = document.createElement("div");
        wrap.className = "search-field";
        wrap.innerHTML = `<label for="${id}">${label}</label><input id="${id}" type="${type}" min="0" placeholder="${placeholder}">`;
        panel.appendChild(wrap);
    });
}

function getSearchParams(page) {
    return new URLSearchParams({
        page,
        limit: 12,
        state: document.getElementById("searchState")?.value || "",
        city: document.getElementById("searchCity")?.value.trim() || "",
        locality: document.getElementById("searchLocality")?.value.trim() || "",
        listing_type: document.getElementById("filterListingType")?.value || "all",
        property_type: document.getElementById("filterPropertyType")?.value || "all",
        min_price: document.getElementById("filterMinPrice")?.value || "",
        max_price: document.getElementById("filterMaxPrice")?.value || "",
        min_area: document.getElementById("filterMinArea")?.value || "",
        max_area: document.getElementById("filterMaxArea")?.value || "",
        bhk: document.getElementById("filterBhk")?.value || "0",
        bathrooms: document.getElementById("filterBathrooms")?.value || "",
        parking: document.getElementById("filterParking")?.value || "",
        facing: document.getElementById("filterFacing")?.value || "all",
        furnishing: document.getElementById("filterFurnishing")?.value || "all",
        min_age: document.getElementById("filterMinAge")?.value || "",
        max_age: document.getElementById("filterMaxAge")?.value || ""
    });
}

function buildPropertyCard(property, options = {}) {
    const id = getPropertyId(property);
    const image = getPropertyImage(property);
    const title = property.title || property.locality || property.city || property.property_type || "Property";
    const fullLocation = [property.locality, property.city, property.state].filter(Boolean).join(", ");
    const compared = comparePropertyIds.has(id);
    const badge = options.badge || (property.is_user_listing ? "DIRECT LISTING" : "MARKETPLACE");
    const isOwn = currentUser && String(currentUser.id) === String(property.owner_id);
    const aiValue = property.ai_valuation;
    const aiBasis = property.ai_valuation_basis || "AI valuation basis unavailable";
    const aiRange = property.ai_valuation_lower != null && property.ai_valuation_upper != null
        ? `${formatPrice(property.ai_valuation_lower)} – ${formatPrice(property.ai_valuation_upper)}`
        : "Range unavailable";

    return `
        <article class="property-card" data-property-id="${id}">
            <label class="card-compare-check" title="Compare side-by-side">
                <input type="checkbox" class="compare-card-checkbox" data-id="${id}" ${compared ? "checked" : ""}>
                Compare
            </label>
            <div class="property-image">
                <img src="${escapeHtml(image)}" alt="${escapeHtml(property.property_type || "Property")} in ${escapeHtml(property.city || "")}" loading="lazy">
                <span class="property-badge">${escapeHtml(badge)}</span>
                ${isOwn ? `<span class="your-listing-badge">YOUR LISTING</span>` : `<button type="button" class="favorite-button" data-property-id="${id}" aria-label="Save property">♡</button>`}
            </div>
            <div class="property-content">
                <div class="property-top">
                    <span class="property-category">${escapeHtml(property.property_type)} • ${escapeHtml(property.listing_type || "Sale")}</span>
                    ${property.match_score != null ? `<span class="match-score">Match ${escapeHtml(property.match_score)}</span>` : ""}
                </div>
                <h3>${escapeHtml(title)}</h3>
                <p class="property-card-location">📍 ${escapeHtml(fullLocation)}</p>
                <div class="property-meta">
                    <span>📐 ${Number(property.area || 0).toLocaleString("en-IN")} sq ft</span>
                    ${property.bedrooms ? `<span>🛏 ${escapeHtml(property.bedrooms)} BHK</span>` : ""}
                    ${property.bathrooms ? `<span>🚿 ${escapeHtml(property.bathrooms)} Baths</span>` : ""}
                    ${property.parking ? `<span>🚗 ${escapeHtml(property.parking)} Park</span>` : ""}
                </div>
                <div class="property-features-chips">
                    ${property.facing && property.facing !== "Not Specified" ? `<span class="feature-pill">🧭 ${escapeHtml(property.facing)}</span>` : ""}
                    ${property.furnishing && property.furnishing !== "Not Applicable" ? `<span class="feature-pill">${escapeHtml(property.furnishing)}</span>` : ""}
                    ${property.property_age ? `<span class="feature-pill">${escapeHtml(property.property_age)} yrs</span>` : ""}
                </div>
                <div class="property-price-row">
                    <strong>${formatPrice(property.price)}</strong>
                    <span class="property-rent-label">${property.listing_type === "Rent" ? "/ month" : ""}</span>
                </div>
                ${aiValue != null ? `
                    <div class="card-ai-valuation">
                        <div class="card-ai-valuation-top">
                            <span class="card-ai-label">REALTYKEY AI VALUE</span>
                            <span class="card-ai-confidence">${escapeHtml(property.ai_valuation_confidence || "Model")}</span>
                        </div>
                        <strong>${formatPrice(aiValue)}</strong>
                        <span class="card-ai-range">Estimated range: ${aiRange}</span>
                        <span class="card-ai-basis">Basis: ${escapeHtml(aiBasis)}</span>
                    </div>
                ` : `
                    <div class="card-ai-valuation unavailable">
                        <span class="card-ai-label">REALTYKEY AI VALUE</span>
                        <span class="card-ai-basis">AI valuation is unavailable for this property.</span>
                    </div>
                `}
                <a class="text-link" href="${getDetailsUrl(property)}" style="margin-top:12px;display:inline-block">View Property Details →</a>
            </div>
        </article>`;
}

async function runSearch(page = 1) {
    currentSearchPage = page;
    const grid = document.getElementById("propertiesGrid");
    if (!grid) return { count: 0 };
    grid.innerHTML = `<div class="result-empty" style="grid-column:1/-1"><h3>Searching properties...</h3><p>Loading active marketplace listings.</p></div>`;
    try {
        const data = await fetchJson(`/search-properties?${getSearchParams(page).toString()}`);
        const countText = document.getElementById("searchCountSubtitle");
        if (countText) countText.textContent = `${data.count} active marketplace properties found`;
        if (!data.count) {
            grid.innerHTML = `<div class="result-empty" style="grid-column:1/-1"><h3>No matching properties</h3><p>Try a broader city/locality or remove optional filters.</p></div>`;
            document.getElementById("paginationContainer")?.style.setProperty("display", "none");
            return data;
        }
        grid.innerHTML = data.properties.map(p => buildPropertyCard(p)).join("");
        bindCardInteractions();
        await loadFavoriteState();
        const pagination = document.getElementById("paginationContainer");
        if (pagination) {
            pagination.style.display = data.total_pages > 1 ? "flex" : "none";
            setText("pageInfoText", `Page ${data.page} of ${data.total_pages}`);
            const prev = document.getElementById("prevPageBtn");
            const next = document.getElementById("nextPageBtn");
            if (prev) { prev.disabled = data.page <= 1; prev.onclick = () => runSearch(data.page - 1); }
            if (next) { next.disabled = data.page >= data.total_pages; next.onclick = () => runSearch(data.page + 1); }
        }
        return data;
    } catch (err) {
        grid.innerHTML = `<div class="result-empty" style="grid-column:1/-1"><h3>Search error</h3><p>${escapeHtml(err.message)}</p></div>`;
        return { count: 0 };
    }
}

function bindCardInteractions() {
    document.querySelectorAll(".favorite-button[data-property-id]").forEach(btn => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = "1";
        btn.addEventListener("click", e => { e.preventDefault(); e.stopPropagation(); toggleFavorite(Number(btn.dataset.propertyId), btn); });
    });
    document.querySelectorAll(".compare-card-checkbox").forEach(chk => {
        if (chk.dataset.bound) return;
        chk.dataset.bound = "1";
        chk.addEventListener("change", () => {
            const id = Number(chk.dataset.id);
            if (chk.checked) {
                if (comparePropertyIds.size >= 4) { alert("You can compare up to 4 properties."); chk.checked = false; return; }
                comparePropertyIds.add(id);
            } else comparePropertyIds.delete(id);
            updateCompareFloatingBar();
        });
    });
}

function setupSearchSection() {
    addOptionalSearchFilters();
    document.getElementById("searchSubmitBtn")?.addEventListener("click", async () => { await runSearch(1); await loadRecommendations(); });
    document.getElementById("toggleFiltersBtn")?.addEventListener("click", () => document.getElementById("optionalFiltersPanel")?.classList.toggle("active"));
    document.getElementById("resetSearchBtn")?.addEventListener("click", () => {
        ["searchCity", "searchLocality", "filterMinPrice", "filterMaxPrice", "filterMinArea", "filterMaxArea", "filterBathrooms", "filterParking", "filterMinAge", "filterMaxAge"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; });
        ["filterListingType", "filterPropertyType", "filterFacing", "filterFurnishing"].forEach(id => { const el = document.getElementById(id); if (el) el.value = "all"; });
        if (document.getElementById("filterBhk")) document.getElementById("filterBhk").value = "0";
        if (document.getElementById("searchState")) document.getElementById("searchState").value = "";
        document.querySelectorAll(".location-chip").forEach(c => c.classList.remove("active"));
        document.querySelector(".location-chip[data-state='']")?.classList.add("active");
        runSearch(1);
        loadRecommendations();
    });
    document.querySelectorAll(".location-chip").forEach(chip => chip.addEventListener("click", () => {
        document.querySelectorAll(".location-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        const state = document.getElementById("searchState"); if (state) state.value = chip.dataset.state || "";
        const city = document.getElementById("searchCity"); if (city) city.value = chip.dataset.city || "";
        const locality = document.getElementById("searchLocality"); if (locality) locality.value = chip.dataset.locality || "";
        runSearch(1);
        loadRecommendations();
    }));
    const gpsBtn = document.getElementById("useGpsBtn");
    gpsBtn?.addEventListener("click", () => {
        if (!navigator.geolocation) { alert("Geolocation is not supported by this browser."); return; }
        gpsBtn.disabled = true; gpsBtn.textContent = "📍 Detecting...";
        navigator.geolocation.getCurrentPosition(async pos => {
            try {
                const data = await fetchJson(`/reverse-geocode?lat=${encodeURIComponent(pos.coords.latitude)}&lon=${encodeURIComponent(pos.coords.longitude)}`);
                if (data.state && document.getElementById("searchState")) document.getElementById("searchState").value = data.state;
                if (data.city && document.getElementById("searchCity")) document.getElementById("searchCity").value = data.city;
                if (data.locality && document.getElementById("searchLocality")) document.getElementById("searchLocality").value = data.locality;
                await runSearch(1);
                await loadRecommendations();
            } catch { alert("Unable to resolve your GPS location. You can type a location manually."); }
            finally { gpsBtn.disabled = false; gpsBtn.textContent = "📍 Use GPS"; }
        }, () => { alert("Location permission was denied or timed out."); gpsBtn.disabled = false; gpsBtn.textContent = "📍 Use GPS"; });
    });
    return runSearch(1);
}

// ============================================================
// LOCATION AUTOCOMPLETE
// ============================================================

function attachLocationAutocomplete(inputId, cityId, stateId = null) {
    const input = document.getElementById(inputId);
    if (!input || input.dataset.autocompleteBound) return;
    input.dataset.autocompleteBound = "1";
    input.style.position = "relative";
    const wrapper = document.createElement("div");
    wrapper.style.position = "relative";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    let panel = document.createElement("div");
    panel.className = "location-suggestions";
    panel.style.display = "none";
    wrapper.appendChild(panel);

    const close = () => { panel.style.display = "none"; panel.innerHTML = ""; };
    const search = async () => {
        const q = input.value.trim();
        if (q.length < 2) { close(); return; }
        const city = document.getElementById(cityId)?.value.trim() || "";
        try {
            const data = await fetchJson(`/location-search?q=${encodeURIComponent(q)}&city=${encodeURIComponent(city)}`);
            if (!data.locations?.length) { close(); return; }
            panel.innerHTML = data.locations.map(loc => `<button type="button" class="location-suggestion" data-name="${escapeHtml(loc.name)}" data-city="${escapeHtml(loc.city)}" data-state="${escapeHtml(loc.state)}"><strong>${escapeHtml(loc.name)}</strong><small>${escapeHtml(loc.address)}</small></button>`).join("");
            panel.style.display = "block";
            panel.querySelectorAll(".location-suggestion").forEach(btn => btn.addEventListener("click", () => {
                input.value = btn.dataset.name || "";
                const cityInput = document.getElementById(cityId); if (cityInput && btn.dataset.city) cityInput.value = btn.dataset.city;
                const st = stateId ? document.getElementById(stateId) : null; if (st && btn.dataset.state) st.value = btn.dataset.state;
                close();
            }));
        } catch { close(); }
    };
    input.addEventListener("input", () => {
        clearTimeout(locationSearchTimers.get(input));
        locationSearchTimers.set(input, setTimeout(search, 350));
    });
    document.addEventListener("click", e => { if (!wrapper.contains(e.target)) close(); });
}

function setupLocationAutocomplete() {
    attachLocationAutocomplete("searchCity", "searchCity", "searchState");
    attachLocationAutocomplete("searchLocality", "searchCity", "searchState");
    attachLocationAutocomplete("propCity", "propCity", "propState");
    attachLocationAutocomplete("propLocality", "propCity", "propState");
}

// ============================================================
// FAVORITES
// ============================================================

async function toggleFavorite(propertyId, button) {
    if (!currentUser) { showAuthModal("Login required", "Please login to save properties to Favorites."); return; }
    try {
        const data = await fetchJson("/api/favorites/toggle", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ property_id: propertyId }) });
        button.classList.toggle("active", data.favorited);
        button.textContent = data.favorited ? "♥" : "♡";
        if (document.getElementById("favoritesSection")) loadFavorites();
    } catch (err) { alert(err.message); }
}

async function loadFavoriteState() {
    if (!currentUser) return;
    try {
        const data = await fetchJson("/api/favorites", { credentials: "include" });
        const ids = new Set((data.properties || []).map(getPropertyId));
        document.querySelectorAll(".favorite-button[data-property-id]").forEach(btn => {
            const active = ids.has(Number(btn.dataset.propertyId));
            btn.classList.toggle("active", active); btn.textContent = active ? "♥" : "♡";
        });
    } catch { /* non-fatal */ }
}

function setupFavoritesSection() {
    const home = document.getElementById("home");
    if (!home || document.getElementById("favoritesSection")) return;
    const section = document.createElement("section");
    section.id = "favoritesSection";
    section.className = "properties-section";
    section.innerHTML = `
        <div class="section-header"><div><span class="section-label">SAVED PROPERTIES</span><h2>Favorites</h2><p style="color:#64748b;font-size:14px;margin-top:4px">Your saved properties persist with your account.</p></div></div>
        <div class="property-grid" id="favoritesGrid"></div>`;
    const rec = document.getElementById("recommendationsSection");
    (rec || home.lastElementChild)?.insertAdjacentElement("afterend", section);
    if (!currentUser) {
        section.innerHTML += `<div style="margin-top:10px"></div>`;
        return;
    }
    loadFavorites();
}

async function loadFavorites() {
    const grid = document.getElementById("favoritesGrid");
    if (!grid) return;
    if (!currentUser) { grid.innerHTML = `<div class="result-empty" style="grid-column:1/-1"><h3>Login to view Favorites</h3><p>Save properties and they will stay attached to your account.</p></div>`; return; }
    try {
        const data = await fetchJson("/api/favorites", { credentials: "include" });
        if (!data.properties?.length) { grid.innerHTML = `<div class="result-empty" style="grid-column:1/-1"><h3>No saved properties yet</h3><p>Use the heart button on any property card.</p></div>`; return; }
        grid.innerHTML = data.properties.map(p => buildPropertyCard(p, { badge: "FAVORITE" })).join("");
        bindCardInteractions();
        await loadFavoriteState();
    } catch (err) { grid.innerHTML = `<div class="result-empty" style="grid-column:1/-1"><h3>Favorites unavailable</h3><p>${escapeHtml(err.message)}</p></div>`; }
}

// ============================================================
// RATE CALCULATOR & VALUATION
// ============================================================

function setupRateCalculator() {
    const btn = document.getElementById("calcSubmitBtn");
    if (!btn || btn.dataset.bound) return;

    btn.dataset.bound = "1";

    btn.addEventListener("click", async () => {
        const city = document.getElementById("calcCity")?.value.trim() || "";
        const locality = document.getElementById("calcLocality")?.value.trim() || "";
        const type = document.getElementById("calcType")?.value || "Apartment";
        const area = Number(document.getElementById("calcArea")?.value || 0);
        const price = Number(document.getElementById("calcPrice")?.value || 0);

        if (!city || area <= 0 || price <= 0) {
            alert("Enter a valid city, positive area and positive price.");
            return;
        }

        btn.disabled = true;

        try {
            const data = await fetchJson(
                `/property-rate?${new URLSearchParams({
                    city,
                    locality,
                    property_type: type,
                    area,
                    price
                })}`
            );

            setText(
                "calcRateValue",
                `₹${Number(data.rate_per_sqft).toLocaleString("en-IN")} / sq ft`
            );

            setText(
                "calcBreakdownText",
                `${area.toLocaleString("en-IN")} sq ft ${type} in ${
                    locality ? `${locality}, ` : ""
                }${city}, priced at ${formatPrice(price)}.`
            );

            const box = document.getElementById("calcResult");

            if (box) {
                box.style.display = "block";
            }
        } catch (err) {
            alert(err.message);
        } finally {
            btn.disabled = false;
        }
    });
}

function confidenceClass(value) {
    const text = String(value || "").toLowerCase();

    if (text.includes("high")) {
        return "confidence-high";
    }

    if (text.includes("moderate") || text.includes("medium")) {
        return "confidence-moderate";
    }

    if (text.includes("fair")) {
        return "confidence-fair";
    }

    return "confidence-broader";
}

function renderValuationResult(data, resultBox) {
    const range = data?.price_range || {};
    const metrics = data?.model_metrics || {};
    const confidence = data?.confidence_level || "Unavailable";
    const factors = Array.isArray(data?.factors) ? data.factors : [];

    resultBox.style.display = "block";

    setText(
        "valEstimatedPrice",
        formatPriceFull(data?.estimated_price)
    );

    setText(
        "valPriceRange",
        `${formatPrice(range.lower)} - ${formatPrice(range.upper)}`
    );

    setText(
        "valRateSqft",
        `₹${Number(data?.rate_per_sqft || 0).toLocaleString("en-IN")} / sq ft`
    );

    setText(
        "valCoverageLevel",
        String(data?.fallback_level || "Not specified").replaceAll("_", " ")
    );

    setText(
        "valCoverageExplanation",
        data?.coverage_explanation ||
        data?.why_estimate ||
        "The estimate combines the model output with the strongest available geographic benchmark data."
    );

    const badge = document.getElementById("valConfidenceBadge");

    if (badge) {
        badge.className = `confidence-badge ${confidenceClass(confidence)}`;
        badge.textContent = confidence;
    }

    const factorsList = document.getElementById("valFactorsList");

    if (factorsList) {
        factorsList.innerHTML = factors.length
            ? factors.map(item => `<li>${escapeHtml(item)}</li>`).join("")
            : `<li>Location, property type, area and available configuration data were considered.</li>`;
    }

    const anomalyBox = document.getElementById("valAnomalyBox");
    const anomaly = data?.anomaly;

    if (anomalyBox) {
        if (anomaly?.status || anomaly?.message) {
            const badgeClass = String(
                anomaly.badge || "fair"
            )
                .toLowerCase()
                .replace(/[^a-z-]/g, "");

            const safeClass = ["fair", "high", "low"].includes(badgeClass)
                ? badgeClass
                : "fair";

            anomalyBox.className = `anomaly-alert-box anomaly-${safeClass}`;

            anomalyBox.innerHTML = `
                <strong>${escapeHtml(
                    anomaly.status || "Asking-price check"
                )}</strong>
                <span>${escapeHtml(
                    anomaly.message ||
                    "The asking price was compared with the estimated market value."
                )}</span>
            `;

            anomalyBox.style.display = "flex";
        } else {
            anomalyBox.className = "";
            anomalyBox.innerHTML = "";
            anomalyBox.style.display = "none";
        }
    }

    let extra = document.getElementById("valExtraExplanation");

    if (!extra) {
        extra = document.createElement("div");
        extra.id = "valExtraExplanation";
        extra.style.cssText =
            "margin-top:18px;" +
            "padding-top:16px;" +
            "border-top:1px solid rgba(255,255,255,.10);" +
            "color:#cbd5e1;" +
            "font-size:12px;" +
            "line-height:1.65;";

        resultBox.appendChild(extra);
    }

    const modelWeight = Number(data?.model_weight || 0);
    const benchmarkCount = Number(data?.benchmark_sample_count || 0);
    const r2 = metrics.r2_score ?? metrics.r2;
    const mae = metrics.mae;
    const rmse = metrics.rmse;
    const medianApe = metrics.median_ape ?? metrics.med_ape;

    extra.innerHTML = `
        <strong style="display:block;color:#93c5fd;margin-bottom:5px">
            Why this estimate
        </strong>
        <span>${escapeHtml(data?.why_estimate || "")}</span>

        <br><br>

        <strong style="display:block;color:#93c5fd;margin-bottom:5px">
            Calculation basis
        </strong>
        <span>${escapeHtml(data?.valuation_basis || "")}</span>

        <br><br>

        <strong style="display:block;color:#93c5fd;margin-bottom:5px">
            Model & benchmark detail
        </strong>
        <span>
            ${
                modelWeight
                    ? `ML model weight: ${Math.round(modelWeight * 100)}%`
                    : "ML model weight unavailable"
            }
            ${
                benchmarkCount
                    ? ` • ${benchmarkCount.toLocaleString("en-IN")} benchmark records`
                    : ""
            }
            ${
                data?.model_price != null
                    ? ` • Raw ML output: ${formatPrice(data.model_price)}`
                    : ""
            }
        </span>

        <br><br>

        <strong style="display:block;color:#93c5fd;margin-bottom:5px">
            Validation metrics
        </strong>
        <span>
            R² ${r2 != null ? Number(r2).toFixed(3) : "—"}
            • MAE ${mae != null ? formatPrice(mae) : "—"}
            • RMSE ${rmse != null ? formatPrice(rmse) : "—"}
            • Median absolute % error ${
                medianApe != null
                    ? Number(medianApe).toFixed(1) + "%"
                    : "—"
            }
        </span>

        <br><br>

        <small style="color:#94a3b8">
            The asking price is checked after prediction. It is not used to
            determine the estimated market value itself.
        </small>
    `;
}

async function runValuationFromButton(btn, resultBox) {
    const payload = {
        state: document.getElementById("valState")?.value.trim() || "",
        city: document.getElementById("valCity")?.value.trim() || "",
        locality: document.getElementById("valLocality")?.value.trim() || "",
        property_type:
            document.getElementById("valType")?.value || "Apartment",
        area_sqft:
            Number(document.getElementById("valArea")?.value || 0),
        bhk:
            Number(document.getElementById("valBhk")?.value || 0),
        bathrooms:
            Number(document.getElementById("valBaths")?.value || 0),
        asking_price:
            Number(
                document.getElementById("valAskingPrice")?.value || 0
            ) || null
    };

    if (
        !payload.city ||
        !payload.locality ||
        payload.area_sqft <= 0
    ) {
        resultBox.style.display = "block";

        resultBox.innerHTML = `
            <div class="comparison-error">
                <h3>Complete the required details</h3>
                <p>
                    Enter the city, locality and a valid built-up area.
                </p>
            </div>
        `;

        return;
    }

    btn.disabled = true;
    btn.textContent = "Computing AI Valuation...";

    resultBox.style.display = "block";

    resultBox.innerHTML = `
        <div class="comparison-loading">
            <span class="mini-spinner"></span>
            <p>Calculating the property estimate…</p>
        </div>
    `;

    try {
        const data = await fetchJson("/predict-price", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        renderValuationResult(data, resultBox);

    } catch (err) {
        resultBox.style.display = "block";

        resultBox.innerHTML = `
            <div class="comparison-error">
                <h3>AI valuation unavailable</h3>
                <p>${escapeHtml(err.message)}</p>
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = "Run AI Valuation Estimate →";
    }
}

function setupValuationTool() {
    const btn = document.getElementById("valSubmitBtn");
    const resultBox = document.getElementById("valResultBox");

    if (!btn || !resultBox || btn.dataset.valuationBound === "1") {
        return;
    }

    btn.dataset.valuationBound = "1";

    btn.onclick = async function (event) {
        event.preventDefault();

        const payload = {
            state: document.getElementById("valState")?.value.trim() || "",
            city: document.getElementById("valCity")?.value.trim() || "",
            locality: document.getElementById("valLocality")?.value.trim() || "",
            property_type:
                document.getElementById("valType")?.value || "Apartment",
            area_sqft:
                Number(document.getElementById("valArea")?.value || 0),
            bhk:
                Number(document.getElementById("valBhk")?.value || 0),
            bathrooms:
                Number(document.getElementById("valBaths")?.value || 0),
            asking_price:
                Number(
                    document.getElementById("valAskingPrice")?.value || 0
                ) || null
        };

        /* Required fields */
        if (
            !payload.city ||
            !payload.locality ||
            payload.area_sqft <= 0
        ) {
            resultBox.style.display = "block";

            resultBox.innerHTML = `
                <div class="comparison-error">
                    <h3>Complete the required details</h3>
                    <p>
                        Enter the city, locality and a valid built-up area.
                    </p>
                </div>
            `;

            return;
        }

        btn.disabled = true;
        btn.textContent = "Computing AI Valuation...";

        /* Make sure the result panel is visible */
        resultBox.style.display = "block";

        resultBox.innerHTML = `
            <div class="prediction-loading">
                <div class="prediction-spinner"></div>
                <p>Calculating property value using RealtyKey AI...</p>
            </div>
        `;

        try {
            const data = await fetchJson("/predict-price", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const range = data.price_range || {};
            const metrics = data.model_metrics || {};
            const anomaly = data.anomaly;
            const factors = Array.isArray(data.factors)
                ? data.factors
                : [];

            resultBox.innerHTML = `
                <div class="valuation-price-hero">
                    <div>
                        <small style="color:#94a3b8;font-weight:700;text-transform:uppercase;">
                            Estimated Market Value
                        </small>

                        <div class="price-display" id="valEstimatedPrice">
                            ${formatPriceFull(data.estimated_price)}
                        </div>
                    </div>

                    <div>
                        <span class="confidence-badge ${
                            String(data.confidence_level || "")
                                .toLowerCase()
                                .includes("high")
                                ? "confidence-high"
                                : String(data.confidence_level || "")
                                    .toLowerCase()
                                    .includes("moderate")
                                    ? "confidence-moderate"
                                    : String(data.confidence_level || "")
                                        .toLowerCase()
                                        .includes("fair")
                                        ? "confidence-fair"
                                        : "confidence-broader"
                        }">
                            ${escapeHtml(
                                data.confidence_level || "Unavailable"
                            )}
                        </span>
                    </div>
                </div>

                <div class="valuation-details-grid">
                    <div class="val-stat-box">
                        <small>Price Range</small>
                        <strong>
                            ${formatPrice(range.lower)}
                            -
                            ${formatPrice(range.upper)}
                        </strong>
                    </div>

                    <div class="val-stat-box">
                        <small>Estimated Rate / Sq Ft</small>
                        <strong>
                            ₹${Number(
                                data.rate_per_sqft || 0
                            ).toLocaleString("en-IN")} / sq ft
                        </strong>
                    </div>

                    <div class="val-stat-box">
                        <small>Data Coverage Level</small>
                        <strong>
                            ${escapeHtml(
                                String(
                                    data.fallback_level ||
                                    "Unavailable"
                                ).replaceAll("_", " ")
                            )}
                        </strong>
                    </div>

                    <div class="val-stat-box">
                        <small>ML Model Weight</small>
                        <strong>
                            ${Math.round(
                                Number(data.model_weight || 0) * 100
                            )}%
                        </strong>
                    </div>
                </div>

                <p style="color:#cbd5e1;font-size:13px;line-height:1.7;margin-bottom:12px;">
                    ${escapeHtml(
                        data.coverage_explanation ||
                        data.why_estimate ||
                        "Estimate calculated using available geographic and machine-learning data."
                    )}
                </p>

                ${
                    anomaly
                        ? `
                            <div class="anomaly-alert-box anomaly-${
                                ["fair", "high", "low"].includes(
                                    String(anomaly.badge || "").toLowerCase()
                                )
                                    ? String(anomaly.badge).toLowerCase()
                                    : "fair"
                            }">
                                <strong>
                                    ${escapeHtml(
                                        anomaly.status || "Price Check"
                                    )}
                                </strong>

                                <span>
                                    ${escapeHtml(
                                        anomaly.message || ""
                                    )}
                                </span>
                            </div>
                        `
                        : ""
                }

                ${
                    factors.length
                        ? `
                            <div style="margin-top:18px;">
                                <strong style="color:#93c5fd;font-size:13px;text-transform:uppercase;">
                                    Valuation Factors Considered
                                </strong>

                                <ul class="factors-list">
                                    ${factors
                                        .map(
                                            factor =>
                                                `<li>${escapeHtml(
                                                    factor
                                                )}</li>`
                                        )
                                        .join("")}
                                </ul>
                            </div>
                        `
                        : ""
                }

                <div style="
                    margin-top:20px;
                    padding-top:16px;
                    border-top:1px solid rgba(255,255,255,.10);
                    color:#cbd5e1;
                    font-size:12px;
                    line-height:1.7;
                ">
                    ${
                        data.why_estimate
                            ? `
                                <strong style="color:#93c5fd;">
                                    Why this estimate
                                </strong>
                                <br>
                                ${escapeHtml(data.why_estimate)}
                                <br><br>
                            `
                            : ""
                    }

                    ${
                        data.valuation_basis
                            ? `
                                <strong style="color:#93c5fd;">
                                    Calculation basis
                                </strong>
                                <br>
                                ${escapeHtml(data.valuation_basis)}
                                <br><br>
                            `
                            : ""
                    }

                    <strong style="color:#93c5fd;">
                        Validation metrics
                    </strong>
                    <br>

                    R² ${
                        metrics.r2_score != null
                            ? Number(metrics.r2_score).toFixed(3)
                            : "—"
                    }

                    • MAE ${
                        metrics.mae != null
                            ? formatPrice(metrics.mae)
                            : "—"
                    }

                    • RMSE ${
                        metrics.rmse != null
                            ? formatPrice(metrics.rmse)
                            : "—"
                    }

                    • Median absolute % error ${
                        metrics.median_ape != null
                            ? Number(metrics.median_ape).toFixed(1) + "%"
                            : "—"
                    }

                    <br><br>

                    <small style="color:#94a3b8;">
                        The asking price is checked separately for anomaly
                        analysis and does not determine the estimated value.
                    </small>
                </div>
            `;

        } catch (err) {
            resultBox.style.display = "block";

            resultBox.innerHTML = `
                <div class="prediction-error">
                    <div class="prediction-ai-icon">AI</div>
                    <h3>AI valuation unavailable</h3>
                    <p>${escapeHtml(err.message)}</p>
                </div>
            `;
        } finally {
            btn.disabled = false;
            btn.textContent = "Run AI Valuation Estimate →";
        }
    };
}
// ============================================================
// RECOMMENDATIONS & COMPARISON
// ============================================================

async function getBrowserRecommendationLocation() {
    if (!navigator.geolocation) return null;
    return new Promise(resolve => {
        navigator.geolocation.getCurrentPosition(
            async position => {
                try {
                    const data = await fetchJson(`/reverse-geocode?lat=${encodeURIComponent(position.coords.latitude)}&lon=${encodeURIComponent(position.coords.longitude)}`);
                    if (data?.success && (data.city || data.state)) {
                        resolve({
                            state: data.state || "",
                            city: data.city || "",
                            locality: data.locality || "",
                            latitude: position.coords.latitude,
                            longitude: position.coords.longitude,
                        });
                        return;
                    }
                } catch {}
                resolve(null);
            },
            () => resolve(null),
            { enableHighAccuracy: false, timeout: 8000, maximumAge: 10 * 60 * 1000 }
        );
    });
}

async function loadRecommendations() {
    const grid = document.getElementById("recommendationsGrid");

    if (!grid) {
        return;
    }

    try {
        const params = new URLSearchParams();

        const map = [
            ["state", "searchState"],
            ["city", "searchCity"],
            ["locality", "searchLocality"],
            ["listing_type", "filterListingType"],
            ["property_type", "filterPropertyType"],
            ["budget", "filterMaxPrice"],
            ["area", "filterMinArea"],
            ["bedrooms", "filterBhk"],
            ["bathrooms", "filterBathrooms"],
            ["parking", "filterParking"],
            ["facing", "filterFacing"],
            ["furnishing", "filterFurnishing"]
        ];

        map.forEach(function ([param, id]) {
            const element = document.getElementById(id);

            if (
                element &&
                element.value &&
                element.value !== "all" &&
                element.value !== "0"
            ) {
                params.set(
                    param,
                    element.value
                );
            }
        });

        const data = await fetchJson(
            `/recommend-properties?${params.toString()}`
        );

        if (!data.recommendations?.length) {
            grid.innerHTML = `
                <div class="result-empty recommendation-empty">
                    <h3>No recommendations yet</h3>
                    <p>Set a location or optional filters above.</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = data.recommendations
            .slice(0, 8)
            .map(function (property) {

                const reasons = (
                    property.why_match || []
                );

                return `
                    <div class="recommendation-card-wrapper">

                        ${buildPropertyCard(
                            property,
                            {
                                badge: "SMART MATCH"
                            }
                        )}

                        ${
                            reasons.length
                                ? `
                                    <div class="recommendation-reason">
                                        <strong>Why it matched</strong>
                                        <div>
                                            ${reasons
                                                .map(function (reason) {
                                                    return `
                                                        <span>
                                                            ${escapeHtml(reason)}
                                                        </span>
                                                    `;
                                                })
                                                .join("")}
                                        </div>
                                    </div>
                                `
                                : ""
                        }

                    </div>
                `;
            })
            .join("");

        bindCardInteractions();

        await loadFavoriteState();

    } catch (error) {

        console.error(
            "Recommendation loading error:",
            error
        );

        grid.innerHTML = `
            <div class="result-empty recommendation-empty">
                <h3>Recommendations unavailable</h3>
                <p>Use the property search above to browse manually.</p>
            </div>
        `;
    }
}


   function comparisonSupportedOnPage() {
    return Boolean(
        document.getElementById("propertiesGrid") ||
        document.getElementById("recommendationsGrid") ||
        document.getElementById("favoritesGrid") ||
        document.querySelector(".compare-card-checkbox")
    );
}

function ensureComparisonUI() {
    if (!comparisonSupportedOnPage()) {
        return {
            bar: null,
            modal: null
        };
    }

    let bar =
        document.getElementById("compareFloatingBar");

    if (!bar) {
        bar = document.createElement("div");
        bar.id = "compareFloatingBar";
        document.body.appendChild(bar);
    }

    if (!bar.querySelector(".compare-floating-inner")) {
        bar.innerHTML = `
            <div class="compare-floating-inner">
                <div class="compare-floating-summary">
                    <strong id="compareSelectedCount">
                        0 properties selected
                    </strong>

                    <span>
                        Select 2–4 properties to compare.
                    </span>
                </div>

                <div class="compare-floating-actions">
                    <button
                        type="button"
                        class="compare-clear-btn"
                        id="compareClearBtn"
                    >
                        Clear
                    </button>

                    <button
                        type="button"
                        class="compare-now-btn"
                        id="compareNowBtn"
                    >
                        Compare Now
                    </button>
                </div>
            </div>
        `;
    }

    let modal =
        document.getElementById("compareModal");

    if (!modal) {
        modal = document.createElement("div");
        modal.id = "compareModal";
        modal.className = "overlay-modal";

        modal.innerHTML = `
            <div
                class="overlay-modal-card compare-modal-card"
                role="dialog"
                aria-modal="true"
                aria-labelledby="compareModalTitle"
            >
                <button
                    type="button"
                    class="modal-x"
                    id="closeCompareModal"
                    aria-label="Close comparison"
                >
                    ×
                </button>

                <div class="compare-modal-header">
                    <span class="section-label">
                        PROPERTY COMPARISON
                    </span>

                    <h2 id="compareModalTitle">
                        Compare selected properties
                    </h2>

                    <p>
                        Side-by-side asking prices,
                        AI valuation and property details.
                    </p>
                </div>

                <div
                    id="compareModalContent"
                    class="compare-modal-content"
                ></div>
            </div>
        `;

        document.body.appendChild(modal);

    } else {
        modal.classList.add("overlay-modal");

        modal
            .querySelector(".overlay-modal-card")
            ?.classList.add("compare-modal-card");

        modal
            .querySelector("#compareModalContent")
            ?.classList.add("compare-modal-content");
    }

    return {
        bar,
        modal
    };
}

function updateCompareFloatingBar() {
    const { bar } = ensureComparisonUI();

    if (!bar) {
        return;
    }

    const count =
        comparePropertyIds.size;

    bar.classList.toggle(
        "active",
        count > 0
    );

    setText(
        "compareSelectedCount",
        `${count} propert${
            count === 1 ? "y" : "ies"
        } selected`
    );

    const btn =
        document.getElementById("compareNowBtn");

    if (btn) {
        btn.disabled = count < 2;
    }
}

function closeCompareModal() {
    document
        .getElementById("compareModal")
        ?.classList.remove("active");
}

function setupComparison() {
    const ui = ensureComparisonUI();

    if (!ui.bar || !ui.modal) {
        return;
    }

    const { modal } = ui;

    const clear =
        document.getElementById("compareClearBtn");

    const now =
        document.getElementById("compareNowBtn");

    const content =
        document.getElementById("compareModalContent");

    if (modal.dataset.bound === "1") {
        return;
    }

    modal.dataset.bound = "1";

    document
        .getElementById("closeCompareModal")
        ?.addEventListener(
            "click",
            closeCompareModal
        );

    modal.addEventListener(
        "click",
        event => {
            if (event.target === modal) {
                closeCompareModal();
            }
        }
    );

    clear?.addEventListener(
        "click",
        () => {
            comparePropertyIds.clear();

            document
                .querySelectorAll(".compare-card-checkbox")
                .forEach(checkbox => {
                    checkbox.checked = false;
                });

            closeCompareModal();

            if (content) {
                content.innerHTML = "";
            }

            updateCompareFloatingBar();
        }
    );

    now?.addEventListener(
        "click",
        async () => {
            if (comparePropertyIds.size < 2) {
                alert(
                    "Select at least 2 properties to compare."
                );
                return;
            }

            modal.classList.add("active");

            if (content) {
                content.innerHTML = `
                    <div class="comparison-loading">
                        <span class="mini-spinner"></span>
                        <p>Preparing comparison…</p>
                    </div>
                `;
            }

            requestAnimationFrame(() => {
                const box =
                    modal.querySelector(
                        ".compare-modal-card"
                    );

                if (box) {
                    box.scrollTop = 0;
                }
            });

            try {
                const data =
                    await fetchJson(
                        "/api/compare-properties",
                        {
                            method: "POST",
                            headers: {
                                "Content-Type":
                                    "application/json"
                            },
                            body: JSON.stringify({
                                property_ids:
                                    Array.from(
                                        comparePropertyIds
                                    )
                            })
                        }
                    );

                const props =
                    data.properties || [];

                if (props.length < 2) {
                    throw new Error(
                        "At least 2 valid properties are required for comparison."
                    );
                }

                const headers =
                    props
                        .map(
                            p => `
                                <th>
                                    <div class="compare-property-head">
                                        <img
                                            src="${escapeHtml(
                                                getPropertyImage(p)
                                            )}"
                                            alt=""
                                        >

                                        <span>
                                            ${escapeHtml(
                                                p.locality ||
                                                p.city ||
                                                "Property"
                                            )}
                                        </span>

                                        <small>
                                            #${escapeHtml(p.id)}
                                        </small>
                                    </div>
                                </th>
                            `
                        )
                        .join("");

                const row =
                    (label, fn) =>
                        `
                            <tr>
                                <th>${label}</th>

                                ${props
                                    .map(
                                        p =>
                                            `<td>${fn(p)}</td>`
                                    )
                                    .join("")}
                            </tr>
                        `;

                content.innerHTML = `
                    <div class="compare-table-wrap">
                        <table class="compare-modal-table">

                            <thead>
                                <tr>
                                    <th>Attribute</th>
                                    ${headers}
                                </tr>
                            </thead>

                            <tbody>

                                ${row(
                                    "Asking Price",
                                    p =>
                                        `<strong>${formatPrice(
                                            p.price
                                        )}</strong>`
                                )}

                                ${row(
                                    "AI Estimated Value",
                                    p =>
                                        p.ai_valuation != null
                                            ? `
                                                <strong>
                                                    ${formatPrice(
                                                        p.ai_valuation
                                                    )}
                                                </strong>

                                                <small class="compare-subtext">
                                                    Range
                                                    ${formatPrice(
                                                        p.ai_valuation_lower
                                                    )}
                                                    –
                                                    ${formatPrice(
                                                        p.ai_valuation_upper
                                                    )}
                                                </small>
                                            `
                                            : "Unavailable"
                                )}

                                ${row(
                                    "AI Basis",
                                    p =>
                                        `<span>${escapeHtml(
                                            p.ai_basis ||
                                            "Unavailable"
                                        )}</span>`
                                )}

                                ${row(
                                    "AI Confidence",
                                    p =>
                                        escapeHtml(
                                            p.ai_confidence ||
                                            "Unavailable"
                                        )
                                )}

                                ${row(
                                    "Asking vs AI",
                                    p =>
                                        p.ai_diff != null
                                            ? `${
                                                p.ai_diff >= 0
                                                    ? "+"
                                                    : "-"
                                            }${formatPrice(
                                                Math.abs(
                                                    p.ai_diff
                                                )
                                            )}`
                                            : "Unavailable"
                                )}

                                ${row(
                                    "AI Status",
                                    p =>
                                        escapeHtml(
                                            p.ai_status ||
                                            "Unavailable"
                                        )
                                )}

                                ${row(
                                    "Location",
                                    p =>
                                        `${escapeHtml(
                                            p.locality
                                        )}, ${escapeHtml(
                                            p.city
                                        )}, ${escapeHtml(
                                            p.state
                                        )}`
                                )}

                                ${row(
                                    "Property Type",
                                    p =>
                                        escapeHtml(
                                            p.property_type
                                        )
                                )}

                                ${row(
                                    "Listing",
                                    p =>
                                        escapeHtml(
                                            p.listing_type ||
                                            "Sale"
                                        )
                                )}

                                ${row(
                                    "Area",
                                    p =>
                                        `${Number(
                                            p.area || 0
                                        ).toLocaleString(
                                            "en-IN"
                                        )} sq ft`
                                )}

                                ${row(
                                    "BHK",
                                    p =>
                                        p.bedrooms
                                            ? escapeHtml(
                                                p.bedrooms
                                            )
                                            : "N/A"
                                )}

                                ${row(
                                    "Bathrooms",
                                    p =>
                                        p.bathrooms
                                            ? escapeHtml(
                                                p.bathrooms
                                            )
                                            : "0"
                                )}

                                ${row(
                                    "Parking",
                                    p =>
                                        p.parking
                                            ? escapeHtml(
                                                p.parking
                                            )
                                            : "0"
                                )}

                                ${row(
                                    "Facing",
                                    p =>
                                        escapeHtml(
                                            p.facing ||
                                            "N/A"
                                        )
                                )}

                                ${row(
                                    "Furnishing",
                                    p =>
                                        escapeHtml(
                                            p.furnishing ||
                                            "N/A"
                                        )
                                )}

                                ${row(
                                    "Open",
                                    p =>
                                        `<a
                                            href="${getDetailsUrl(
                                                p
                                            )}"
                                            class="compare-open-link"
                                        >
                                            View Property →
                                        </a>`
                                )}

                            </tbody>
                        </table>
                    </div>
                `;

                content.scrollTop = 0;

                document
                    .querySelector(
                        ".compare-table-wrap"
                    )
                    ?.scrollTo({
                        top: 0,
                        behavior: "smooth"
                    });

            } catch (err) {
                if (content) {
                    content.innerHTML = `
                        <div class="comparison-error">
                            <h3>
                                Comparison unavailable
                            </h3>

                            <p>
                                ${escapeHtml(
                                    err.message
                                )}
                            </p>
                        </div>
                    `;
                }
            }
        }
    );
}
// ============================================================
// AI ASSISTANT
// ============================================================

function ensureAssistantUI() {
    let toggle = document.getElementById("assistantToggle");
    let panel = document.getElementById("assistantPanel");

    if (!toggle) {
        toggle = document.createElement("button");
        toggle.type = "button";
        toggle.id = "assistantToggle";
        toggle.className = "assistant-toggle";
        toggle.setAttribute("aria-label", "Open RealtyKey AI Assistant");
        toggle.innerHTML = `<img src="/assets/ai-assistant.png" alt="AI Assistant" class="assistant-logo">`;
                document.body.appendChild(toggle);
    }

    if (!panel) {
        panel = document.createElement("section");
        panel.id = "assistantPanel";
        panel.className = "assistant-panel";
        panel.innerHTML = `
            <div class="assistant-header">
                <div><span class="section-label">REALTYKEY AI</span><h3>Property assistant</h3><p>Ask about using the platform and understanding your property options.</p></div>
                <button type="button" class="assistant-close" id="closeAssistantBtn" aria-label="Close assistant">×</button>
            </div>
            <div class="assistant-messages" id="assistantMessages">
                <div class="assistant-bubble bot">Hello! I can help with search, listing, AI valuation, comparison, favourites, seller chat, offers and reports.</div>
            </div>
            <div class="assistant-quick-prompts">
                <button type="button" data-question="How do I list a property?">How do I list a property?</button>
                <button type="button" data-question="How does AI valuation work?">How does AI valuation work?</button>
                <button type="button" data-question="How do I compare properties?">How do I compare properties?</button>
                <button type="button" data-question="How do I search properties?">How do I search properties?</button>
            </div>
            <form id="assistantForm" class="assistant-form">
                <input id="assistantInput" type="text" placeholder="Ask about RealtyKey AI…" autocomplete="off">
                <button type="submit">Send</button>
            </form>`;
        document.body.appendChild(panel);
    }
    return { toggle, panel };
}

function setupAssistant() {
    const { toggle, panel } = ensureAssistantUI();
    const close = document.getElementById("closeAssistantBtn");
    const form = document.getElementById("assistantForm");
    const input = document.getElementById("assistantInput");
    const messages = document.getElementById("assistantMessages");
    if (!toggle || !panel || !form || !input || !messages) return;
    if (toggle.dataset.bound) return;
    toggle.dataset.bound = "1";

    toggle.addEventListener("click", () => {
        panel.classList.toggle("active");
        if (panel.classList.contains("active")) input.focus();
    });
    close?.addEventListener("click", () => panel.classList.remove("active"));

    panel.querySelectorAll(".assistant-quick-prompts button").forEach(btn => btn.addEventListener("click", () => {
        input.value = btn.dataset.question || "";
        form.requestSubmit();
    }));

    form.addEventListener("submit", async e => {
        e.preventDefault();
        const text = input.value.trim();
        if (!text) return;
        const user = document.createElement("div");
        user.className = "assistant-bubble user";
        user.textContent = text;
        messages.appendChild(user);
        input.value = "";
        const bot = document.createElement("div");
        bot.className = "assistant-bubble bot typing";
        bot.innerHTML = `<span></span><span></span><span></span>`;
        messages.appendChild(bot);
        messages.scrollTop = messages.scrollHeight;
        try {
            const data = await fetchJson("/api/ai-assistant", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });
            bot.classList.remove("typing");
            bot.textContent = data.reply || "I can help with RealtyKey AI features.";
        } catch (err) {
            bot.classList.remove("typing");
            bot.textContent = err.message || "The assistant service is unavailable right now.";
        }
        messages.scrollTop = messages.scrollHeight;
    });
}

// ============================================================
// PROPERTY DETAILS
// ============================================================

async function initializePropertyDetailsPage() {
    const root = document.getElementById("propertyDetailsPage");
    if (!root) return;
    const id = Number(new URLSearchParams(window.location.search).get("id"));
    if (!id) { root.innerHTML = `<div class="details-error"><h1>Property Not Found</h1><p>No valid property ID was specified.</p></div>`; return; }
    try { const data = await fetchJson(`/property/${id}`); renderPropertyDetails(data.property); }
    catch (err) { root.innerHTML = `<div class="details-error"><h1>Unable to load property</h1><p>${escapeHtml(err.message)}</p></div>`; }
}

function renderPropertyDetails(property) {
    const root = document.getElementById("propertyDetailsPage");
    if (!root) return;
    const isOwner = currentUser && property.owner_id && String(currentUser.id) === String(property.owner_id);
    const canContactOwner = Boolean(!isOwner && property.owner_id);
    const fullLoc = [property.locality, property.city, property.state].filter(Boolean).join(", ");
    const images = Array.isArray(property.images) && property.images.length ? property.images : [getPropertyImage(property)];

    root.innerHTML = `
        <div class="property-layout">
            <div>
                <div class="detail-gallery"><img id="detailMainImage" class="detail-main-image" src="${escapeHtml(images[0])}" alt="Property photo">
                    <div class="detail-thumbnails">${images.map((img, i) => `<button type="button" class="detail-thumb ${i === 0 ? "active" : ""}" data-src="${escapeHtml(img)}"><img src="${escapeHtml(img)}" alt="Photo ${i+1}"></button>`).join("")}</div>
                </div>
                <section class="detail-section"><span class="section-label">DESCRIPTION & HIGHLIGHTS</span><h2>About this ${escapeHtml(property.property_type)}</h2><p style="white-space:pre-line;line-height:1.8">${escapeHtml(property.description || "No description provided.")}</p>
                    <div class="detail-feature-grid" style="margin-top:24px">
                        ${property.built_up_area ? `<div><small>Built-up Area</small><strong>${Number(property.built_up_area).toLocaleString("en-IN")} sq ft</strong></div>` : ""}
                        ${property.carpet_area ? `<div><small>Carpet Area</small><strong>${Number(property.carpet_area).toLocaleString("en-IN")} sq ft</strong></div>` : ""}
                        ${property.plot_area ? `<div><small>Plot Area</small><strong>${Number(property.plot_area).toLocaleString("en-IN")} sq ft</strong></div>` : ""}
                        ${property.length && property.width ? `<div><small>Dimensions</small><strong>${property.length} × ${property.width} ft</strong></div>` : ""}
                        ${property.bedrooms ? `<div><small>Bedrooms</small><strong>${property.bedrooms}</strong></div>` : ""}
                        ${property.bathrooms ? `<div><small>Bathrooms</small><strong>${property.bathrooms}</strong></div>` : ""}
                        ${property.facing && property.facing !== "Not Specified" ? `<div><small>Facing</small><strong>${escapeHtml(property.facing)}</strong></div>` : ""}
                        <div><small>Furnishing</small><strong>${escapeHtml(property.furnishing || "Not Specified")}</strong></div>
                        ${property.property_age ? `<div><small>Property Age</small><strong>${property.property_age} Years</strong></div>` : ""}
                        ${property.parking ? `<div><small>Parking</small><strong>${property.parking} Spaces</strong></div>` : ""}
                        ${property.floors ? `<div><small>Number of Floors</small><strong>${property.floors}</strong></div>` : ""}
                        ${property.floor_position ? `<div><small>Floor Position</small><strong>${escapeHtml(property.floor_position)}</strong></div>` : ""}
                        ${property.road_width ? `<div><small>Road Width</small><strong>${property.road_width} ft</strong></div>` : ""}
                        <div><small>Listing</small><strong>Active • 30 days</strong></div>
                    </div>
                    ${property.amenities?.length ? `<div style="margin-top:18px"><strong style="display:block;margin-bottom:8px">Amenities</strong><div style="display:flex;flex-wrap:wrap;gap:7px">${property.amenities.map(a=>`<span style="padding:6px 9px;background:#f1f5f9;border-radius:8px;font-size:12px">${escapeHtml(a)}</span>`).join("")}</div></div>` : ""}
                </section>
                <section class="detail-section"><span class="section-label">EXACT LOCATION</span><h2>${escapeHtml(fullLoc)}</h2><p style="margin-top:6px">📍 ${escapeHtml(property.location_address || fullLoc)}</p>
                    ${property.latitude != null && property.longitude != null ? `<div style="margin-top:14px"><iframe title="Property location" src="https://www.openstreetmap.org/export/embed.html?bbox=${property.longitude-0.006}%2C${property.latitude-0.004}%2C${property.longitude+0.006}%2C${property.latitude+0.004}&layer=mapnik&marker=${property.latitude}%2C${property.longitude}" style="width:100%;height:300px;border:1px solid #e6eaf1;border-radius:14px"></iframe><div style="display:flex;justify-content:space-between;gap:10px;margin-top:8px;font-size:12px;color:#64748b"><span>Coordinates: ${Number(property.latitude).toFixed(5)}, ${Number(property.longitude).toFixed(5)}</span><a href="${escapeHtml(property.map_url || "#")}" target="_blank" rel="noopener" style="color:#3157d5;font-weight:700">Open in OpenStreetMap →</a></div></div>` : `<p style="margin-top:10px;color:#94a3b8">No GPS coordinates were provided for this listing.</p>`}
                </section>
            </div>
            <div>
                <div class="detail-card"><div class="detail-topline"><span class="detail-badge">${escapeHtml(property.property_type)}</span><span class="user-listed-badge">${escapeHtml(property.listing_type || "Sale")}</span></div>
                    <h1>${escapeHtml(property.locality || property.city)}</h1><p class="detail-location">📍 ${escapeHtml(fullLoc)}</p>
                    <div class="detail-price">${formatPrice(property.price)} <small style="font-size:14px;font-weight:normal;color:#64748b">${property.listing_type === "Rent" ? "/ month" : ""}</small></div>
                    <div class="detail-stats"><div><small>Total Area</small><strong>${Number(property.area || 0).toLocaleString("en-IN")} sq ft</strong></div><div><small>Configuration</small><strong>${property.bedrooms ? `${property.bedrooms} BHK` : "Plot"}</strong></div><div><small>Bathrooms</small><strong>${property.bathrooms || 0}</strong></div><div><small>Views</small><strong>👁 ${property.views || 0}</strong></div></div>
                    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:14px;margin-bottom:16px"><small style="color:#64748b;display:block">Listed by</small><strong>${escapeHtml(property.owner_name || "Property Lister")}</strong><small style="display:block;color:#94a3b8;margin-top:2px">Listed ${formatDate(property.created_at)}</small></div>
                    <div class="detail-ai" id="detailAiBox"><small>REALTYKEY AI VALUATION</small><strong id="detailAiPrice">Loading…</strong><p id="detailAiText">Calculating an estimate using the ML model and geographic benchmark coverage.</p></div>
                    <div class="detail-actions" id="detailActions">${isOwner ? `<div style="background:#ecfdf3;border:1px solid #a6f4c5;padding:12px;border-radius:10px;width:100%;text-align:center;color:#027a48;font-weight:700">✓ This is your published listing</div><a href="my-listings.html" class="primary-button" style="width:100%;text-align:center">Manage in My Listings</a><a href="messages.html" class="secondary-button" style="width:100%;text-align:center">View Buyer Messages</a>` : `${canContactOwner ? `<button type="button" class="primary-button" id="chatSellerBtn" style="width:100%">💬 Chat with Seller</button><button type="button" class="secondary-button" id="makeOfferBtn" style="width:100%;color:#3157d5">🏷 Make an Offer</button>` : `<div style="padding:12px;border-radius:10px;background:#f8fafc;border:1px solid #e2e8f0;color:#64748b;font-size:12px;text-align:center;width:100%">Marketplace data listing — direct owner chat and offers are unavailable.</div>`}<button type="button" class="secondary-button" id="favDetailBtn" style="width:100%">♡ Save to Favorites</button><button type="button" class="secondary-button" id="sharePropertyBtn" style="width:100%">🔗 Share Property</button>${canContactOwner ? `<button type="button" class="report-button" id="reportPropertyBtn" style="width:100%;margin-top:8px">⚑ Report this Property</button>` : ""}`}</div>
                </div>
            </div>
        </div><div id="detailModalsContainer"></div>`;

    document.querySelectorAll(".detail-thumb").forEach(btn => btn.addEventListener("click", () => { const img = document.getElementById("detailMainImage"); if(img) img.src = btn.dataset.src; document.querySelectorAll(".detail-thumb").forEach(t=>t.classList.remove("active")); btn.classList.add("active"); }));

    if (!isOwner) {
        document.getElementById("favDetailBtn")?.addEventListener("click", async () => { const btn = document.getElementById("favDetailBtn"); if (!currentUser) { showAuthModal("Login required", "Please login to save this property."); return; } await toggleFavorite(property.id, btn); btn.textContent = btn.classList.contains("active") ? "♥ Saved in Favorites" : "♡ Save to Favorites"; });
        document.getElementById("chatSellerBtn")?.addEventListener("click", () => { if (!currentUser) { showAuthModal("Login required", "Please login to chat with this seller."); return; } openChatModal(property); });
        document.getElementById("makeOfferBtn")?.addEventListener("click", () => { if (!currentUser) { showAuthModal("Login required", "Please login to submit an offer."); return; } openOfferModal(property); });
        document.getElementById("reportPropertyBtn")?.addEventListener("click", () => { if (!currentUser) { showAuthModal("Login required", "Please login to submit a report."); return; } openReportModal(property); });
        document.getElementById("sharePropertyBtn")?.addEventListener("click", () => shareProperty(property));
        if (currentUser) loadFavoriteState();
    }
    loadDetailValuation(property);
}

async function loadDetailValuation(property) {
    const priceEl = document.getElementById("detailAiPrice");
    const textEl = document.getElementById("detailAiText");
    if (!priceEl || !textEl) return;
    try {
        const data = await fetchJson("/predict-price", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({ state:property.state, city:property.city, locality:property.locality, property_type:property.property_type, area_sqft:property.area, bhk:property.bhk, bathrooms:property.bathrooms, asking_price:property.price }) });
        priceEl.textContent = formatPrice(data.estimated_price);
        textEl.innerHTML = `${escapeHtml(data.coverage_explanation || "")}<br><strong style="color:#93c5fd">Range:</strong> ${formatPrice(data.price_range.lower)}–${formatPrice(data.price_range.upper)} • <strong style="color:#93c5fd">${escapeHtml(data.confidence_level)}</strong>`;
    } catch { priceEl.textContent = "Unavailable"; textEl.textContent = "The valuation model is not available for this property right now."; }
}

async function shareProperty(property) {
    const details = [
        property.bedrooms ? `${property.bedrooms} BHK` : null,
        property.bathrooms ? `${property.bathrooms} bathrooms` : null,
        `${Number(property.area||0).toLocaleString("en-IN")} sq ft`,
        property.floors ? `${property.floors} floors` : null,
        property.facing && property.facing !== "Not Specified" ? `Facing ${property.facing}` : null,
        property.parking ? `${property.parking} parking space(s)` : null,
        property.owner_name ? `Listed by ${property.owner_name}` : null
    ].filter(Boolean).join(" • ");
    const text = `${property.property_type} in ${property.locality}, ${property.city}\nPrice: ${formatPrice(property.price)}${property.listing_type === "Rent" ? " / month" : ""}\n${details}\n\n${property.description || ""}`;
    const payload = { title: `${property.property_type} in ${property.locality}, ${property.city}`, text, url: window.location.href };
    if (navigator.share) { try { await navigator.share(payload); return; } catch { return; } }
    try { await navigator.clipboard.writeText(`${text}\n${window.location.href}`); alert("Property details and link copied to clipboard."); }
    catch { prompt("Copy this property link:", window.location.href); }
}

function openChatModal(property) {
    const container = document.getElementById("detailModalsContainer"); if (!container) return;
    container.innerHTML = `<div class="overlay-modal active" id="chatModal"><div class="overlay-modal-card"><button class="modal-x" id="closeChatModal">×</button><span class="section-label">DIRECT BUYER-SELLER MESSAGING</span><h2>Contact ${escapeHtml(property.owner_name || "Seller")}</h2><p style="font-size:13px;color:#64748b;margin-bottom:14px">Regarding: <strong>${escapeHtml(property.locality)}, ${escapeHtml(property.city)}</strong> (${formatPrice(property.price)})</p><div class="quick-messages" style="margin-bottom:16px">${["Is the price negotiable?","Is this property still available?","What is included in the rent?","Can you share the exact location?","Can I discuss the property details?","Send your contact details."].map((m,i)=>`<button type="button" class="quick-msg-chip" data-msg="${escapeHtml(m)}">${i+1}. ${escapeHtml(m)}</button>`).join("")}</div><form id="directChatForm" class="chat-compose"><input type="text" id="chatInputText" placeholder="Write a message..." required><button type="submit">Send</button></form><div id="chatSendStatus" class="chat-status"></div></div></div>`;
    document.getElementById("closeChatModal")?.addEventListener("click",()=>container.innerHTML="");
    container.querySelectorAll(".quick-msg-chip").forEach(btn=>btn.addEventListener("click",()=>{const i=document.getElementById("chatInputText");if(i)i.value=btn.dataset.msg;}));
    document.getElementById("directChatForm")?.addEventListener("submit",async e=>{e.preventDefault();const input=document.getElementById("chatInputText"),status=document.getElementById("chatSendStatus");if(status)status.textContent="Sending...";try{const data=await fetchJson("/api/conversations",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({property_id:property.id,message:input.value.trim()})});if(status)status.innerHTML=`✓ Message sent. <a href="messages.html?cid=${encodeURIComponent(data.conversation_id)}" style="color:#2563eb;font-weight:700;text-decoration:underline">Open Messages →</a>`;input.value="";}catch(err){if(status)status.textContent=`✕ ${err.message}`;}});
}

function openOfferModal(property) {
    const container = document.getElementById("detailModalsContainer"); if (!container) return;
    container.innerHTML = `<div class="overlay-modal active"><div class="overlay-modal-card" style="max-width:440px"><button class="modal-x" id="closeOfferModal">×</button><span class="section-label">PRICE NEGOTIATION</span><h2>Make an Offer</h2><p style="font-size:13px;color:#64748b;margin-bottom:16px">Asking Price: <strong>${formatPrice(property.price)}</strong></p><form id="submitOfferForm"><label>Your Offered Price (₹)<input type="number" id="offerPriceInput" min="1000" value="${Math.max(1000,Math.round(Number(property.price||0)*0.95))}" required></label><button type="submit" class="primary-button" style="width:100%;margin-top:14px">Submit Offer to Seller</button><div id="offerStatusFeedback" class="chat-status"></div></form></div></div>`;
    document.getElementById("closeOfferModal")?.addEventListener("click",()=>container.innerHTML="");
    document.getElementById("submitOfferForm")?.addEventListener("submit",async e=>{e.preventDefault();const price=Number(document.getElementById("offerPriceInput")?.value||0),status=document.getElementById("offerStatusFeedback");if(status)status.textContent="Submitting offer...";try{await fetchJson("/api/offers",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({property_id:property.id,offered_price:price})});if(status)status.textContent=`✓ Offer of ${formatPrice(price)} submitted to seller.`;setTimeout(()=>container.innerHTML="",1500);}catch(err){if(status)status.textContent=`✕ ${err.message}`;}});
}

function openReportModal(property) {
    const container = document.getElementById("detailModalsContainer"); if (!container) return;
    container.innerHTML = `<div class="overlay-modal active"><div class="overlay-modal-card" style="max-width:440px"><button class="modal-x" id="closeReportModal">×</button><span class="section-label" style="color:#b42318">SAFETY & TRUST</span><h2>Report Property</h2><p style="font-size:13px;color:#64748b;margin-bottom:14px">Submit the reason and supporting details for admin review.</p><form id="submitReportForm"><label>Category<select id="reportCategorySelect"><option>Suspicious / Scam</option><option>Fake Information</option><option>Duplicate Listing</option><option>Incorrect Details</option><option>Other</option></select></label><label>Additional Details<textarea id="reportDetailsText" rows="3" placeholder="Explain the issue..."></textarea></label><button type="submit" class="report-button" style="width:100%;margin-top:12px">Submit Report</button><div id="reportStatusFeedback" class="chat-status"></div></form></div></div>`;
    document.getElementById("closeReportModal")?.addEventListener("click",()=>container.innerHTML="");
    document.getElementById("submitReportForm")?.addEventListener("submit",async e=>{e.preventDefault();const status=document.getElementById("reportStatusFeedback");try{await fetchJson(`/api/properties/${property.id}/report`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({category:document.getElementById("reportCategorySelect")?.value||"Other",details:document.getElementById("reportDetailsText")?.value.trim()||""})});if(status)status.textContent="✓ Report submitted to admin review.";setTimeout(()=>container.innerHTML="",1400);}catch(err){if(status)status.textContent=`✕ ${err.message}`;}});
}

// ============================================================
// MESSAGES & OFFERS PAGE
// ============================================================

async function loadMessagesPage() {
    const list = document.getElementById("conversationList"); if (!list) return;
    if (!currentUser) { list.innerHTML = `<div class="message-empty"><h3>Login required</h3><p>Please login to view your messages.</p></div>`; return; }
    try {
        const data = await fetchJson("/api/conversations", { credentials:"include" });
        if (!data.conversations?.length) { list.innerHTML = `<div class="message-empty"><h3>No conversations yet</h3><p>Chats with buyers and sellers will appear here.</p></div>`; return; }
        list.innerHTML = data.conversations.map(c => `<button type="button" class="conversation-item" data-id="${escapeHtml(c.conversation_id)}"><img src="${escapeHtml(getPropertyImage(c.property || {}))}" alt="Property"><span><strong>${escapeHtml(c.property?.locality || c.property?.city || "Property")}</strong><small>${escapeHtml(c.last_message?.text || "No messages yet")}</small></span></button>`).join("");
        list.querySelectorAll(".conversation-item").forEach(btn=>btn.addEventListener("click",()=>openActiveChat(btn.dataset.id)));
        const cid = new URLSearchParams(window.location.search).get("cid");
        openActiveChat(cid || data.conversations[0].conversation_id);
    } catch (err) { list.innerHTML = `<div class="message-empty"><h3>Messages unavailable</h3><p>${escapeHtml(err.message)}</p></div>`; }
}

async function openActiveChat(conversationId) {
    if (activeChatPollInterval) clearInterval(activeChatPollInterval);
    const panel = document.getElementById("chatPanel"); if (!panel) return;
    document.querySelectorAll(".conversation-item").forEach(i=>i.classList.toggle("active",i.dataset.id===conversationId));
    const render = async () => {
        try {
            const data = await fetchJson(`/api/conversations/${encodeURIComponent(conversationId)}`,{credentials:"include"});
            const conv=data.conversation, prop=conv.property||{}, isSeller=String(currentUser?.id)===String(conv.owner_id);
            let offersHtml="";
            try { const od=await fetchJson(`/api/offers?property_id=${encodeURIComponent(prop.id||0)}`,{credentials:"include"}); const offers=od.offers||[]; if(offers.length) offersHtml=`<div style="padding:12px 20px;background:#f8fafc;border-bottom:1px solid #e5e7eb"><strong style="font-size:12px;color:#475569">OFFERS</strong>${offers.map(o=>`<div style="margin-top:8px;display:flex;justify-content:space-between;gap:12px;align-items:center;background:white;border:1px solid #e2e8f0;border-radius:10px;padding:10px"><div><small>${escapeHtml(o.buyer_name)} • ${formatDate(o.created_at)}</small><strong style="display:block">${formatPrice(o.offered_price)}</strong><span style="font-size:11px;font-weight:800">${escapeHtml(o.status)}</span></div>${isSeller&&o.status==="pending"?`<div style="display:flex;gap:6px"><button class="primary-button respond-offer-btn" data-id="${escapeHtml(o.offer_id)}" data-action="accept" style="padding:6px 10px;font-size:11px">Accept</button><button class="danger-button respond-offer-btn" data-id="${escapeHtml(o.offer_id)}" data-action="reject" style="padding:6px 10px;font-size:11px">Reject</button></div>`:""}</div>`).join("")}</div>`; } catch {}
            panel.innerHTML=`<div class="chat-panel-header" style="display:flex;justify-content:space-between;gap:10px;align-items:center"><div><small>PROPERTY CONVERSATION</small><h2>${escapeHtml(prop.locality||prop.city||"Property")} • ${formatPrice(prop.price)}</h2></div><div style="display:flex;gap:6px;flex-wrap:wrap"><a href="${getDetailsUrl(prop)}" class="secondary-button" style="padding:8px 12px;font-size:12px">View Property</a>${!isSeller?`<button id="chatOfferBtn" class="primary-button" style="padding:8px 12px;font-size:12px">Make Offer</button>`:""}</div></div>${offersHtml}<div class="quick-messages" style="padding:10px 20px;background:white;border-bottom:1px solid #e5e9f0"><button class="quick-msg-chip" data-msg="Is the price negotiable?">Negotiable?</button><button class="quick-msg-chip" data-msg="Is this property still available?">Available?</button><button class="quick-msg-chip" data-msg="Can you share the exact location?">Location?</button><button class="quick-msg-chip" data-msg="Send your contact details.">Contact info?</button></div><div class="chat-messages" id="activeChatMessages">${(conv.messages||[]).map(m=>`<div class="chat-bubble ${String(m.sender_id)===String(currentUser?.id)?"own":"other"}"><span>${escapeHtml(m.sender_name||"User")} • ${formatDate(m.created_at)}</span><p>${escapeHtml(m.text)}</p></div>`).join("")}</div><form class="chat-compose" id="activeChatComposeForm"><input id="chatComposeInput" type="text" placeholder="Write a message..." required><button type="submit">Send</button></form>`;
            document.getElementById("activeChatMessages")?.scrollTo({top:999999,behavior:"auto"});
            panel.querySelectorAll(".quick-msg-chip").forEach(b=>b.addEventListener("click",()=>{const i=document.getElementById("chatComposeInput");if(i)i.value=b.dataset.msg;}));
            document.getElementById("chatOfferBtn")?.addEventListener("click",()=>openOfferModal(prop));
            panel.querySelectorAll(".respond-offer-btn").forEach(b=>b.addEventListener("click",async()=>{try{await fetchJson(`/api/offers/${encodeURIComponent(b.dataset.id)}/respond`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:b.dataset.action})});render();}catch(err){alert(err.message);}}));
            document.getElementById("activeChatComposeForm")?.addEventListener("submit",async e=>{e.preventDefault();const input=document.getElementById("chatComposeInput"),text=input?.value.trim();if(!text)return;try{await fetchJson(`/api/conversations/${encodeURIComponent(conversationId)}/messages`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text})});input.value="";render();}catch(err){alert(err.message);}});
        } catch { /* polling can fail transiently */ }
    };
    await render();
    activeChatPollInterval=setInterval(render,3500);
}

// ============================================================
// MY LISTINGS
// ============================================================

async function loadMyListingsPage() {
    const grid=document.getElementById("myListingsGrid"); if(!grid)return;
    if(!currentUser){grid.innerHTML=`<div class="result-empty" style="grid-column:1/-1"><h3>Login required</h3><p>Please login to manage your properties.</p><a class="primary-button" href="login.html" style="margin-top:10px">Login</a></div>`;return;}
    try{
        const data=await fetchJson("/api/my-listings",{credentials:"include"});
        if(!data.properties?.length){grid.innerHTML=`<div class="result-empty" style="grid-column:1/-1"><h3>No listings yet</h3><p>Publish a home, apartment or plot from List Property.</p><a class="primary-button" href="list-property.html" style="margin-top:12px">+ List Property</a></div>`;return;}
        grid.innerHTML=data.properties.map(p=>`<article class="manage-card"><img src="${escapeHtml(getPropertyImage(p))}" alt="Property photo"><div class="manage-card-body"><span class="status-pill">Active listing</span><h3>${escapeHtml(p.locality||p.city)}</h3><p>📍 ${escapeHtml(p.locality?`${p.locality}, `:"")}${escapeHtml(p.city)}</p><strong>${formatPrice(p.price)}</strong><div style="font-size:12px;color:#64748b;margin:10px 0"><div>👁 Views: <strong>${p.views||0}</strong></div><div>📅 Listed: ${formatDate(p.created_at)}</div><div>⏳ Expires: ${formatDate(p.expires_at)}</div></div><div class="manage-actions"><a href="${getDetailsUrl(p)}" class="secondary-button">View</a><button class="danger-button delete-prop-btn" data-id="${p.id}">Delete</button></div></div></article>`).join("");
        grid.querySelectorAll(".delete-prop-btn").forEach(btn=>btn.addEventListener("click",async()=>{if(!confirm(`Delete property #${btn.dataset.id}? This cannot be undone.`))return;btn.disabled=true;try{await fetchJson(`/api/my-listings/${encodeURIComponent(btn.dataset.id)}`,{method:"DELETE",credentials:"include"});loadMyListingsPage();}catch(err){alert(err.message);btn.disabled=false;}}));
    }catch(err){grid.innerHTML=`<div class="result-empty" style="grid-column:1/-1"><h3>Error</h3><p>${escapeHtml(err.message)}</p></div>`;}
}

// ============================================================
// ADMIN
// ============================================================

async function loadAdminPage() {
    const page=document.getElementById("adminPage"); if(!page)return;
    if(!currentUser||currentUser.role!=="admin"){page.innerHTML=`<div class="admin-denied"><h1>Admin Access Required</h1><p>This section is restricted to the configured administrator.</p><a href="index.html" class="primary-button" style="margin-top:14px">Return to Home</a></div>`;return;}
    try{
        const [sum,propData,userData,reportData]=await Promise.all([fetchJson("/api/admin/summary",{credentials:"include"}),fetchJson("/api/admin/properties",{credentials:"include"}),fetchJson("/api/admin/users",{credentials:"include"}),fetchJson("/api/admin/reports",{credentials:"include"})]);
        setText("adminUsersCount",sum.users||0);setText("adminPropertiesCount",sum.properties||0);setText("adminReportsCount",sum.reports||0);setText("adminConversationsCount",sum.conversations||0);
        const ptable=document.getElementById("adminPropertiesTable"); if(ptable)ptable.innerHTML=(propData.properties||[]).map(p=>`<tr><td>#${p.id}</td><td>${escapeHtml(p.locality)}, ${escapeHtml(p.city)}</td><td>${escapeHtml(p.owner_name||"Lister")}</td><td>${formatPrice(p.price)}</td><td>${escapeHtml(p.status||"active")}</td><td><a href="${getDetailsUrl(p)}" target="_blank" rel="noopener">View</a> <button class="danger-button admin-del-btn" data-id="${p.id}">Remove</button></td></tr>`).join("") || `<tr><td colspan="6">No user properties.</td></tr>`;
        ptable?.querySelectorAll(".admin-del-btn").forEach(b=>b.addEventListener("click",async()=>{if(!confirm(`Remove property #${b.dataset.id}?`))return;try{await fetchJson(`/api/admin/properties/${encodeURIComponent(b.dataset.id)}`,{method:"DELETE",credentials:"include"});loadAdminPage();}catch(err){alert(err.message);}}));
        const rtable=document.getElementById("adminReportsTable"); if(rtable)rtable.innerHTML=(reportData.reports||[]).map(r=>`<tr><td>#${r.property_id} (${escapeHtml(r.property_title||"")})</td><td><strong>${escapeHtml(r.category||r.reason||"")}</strong></td><td>${escapeHtml(r.details||"No details")}</td><td>${escapeHtml(r.status||"")}</td><td>${r.status==="open"?`<button class="secondary-button resolve-rep-btn" data-id="${escapeHtml(r.report_id)}">Resolve</button>`:"<span style='color:#027a48'>Resolved</span>"}</td></tr>`).join("") || `<tr><td colspan="5">No reports.</td></tr>`;
        rtable?.querySelectorAll(".resolve-rep-btn").forEach(b=>b.addEventListener("click",async()=>{try{await fetchJson(`/api/admin/reports/${encodeURIComponent(b.dataset.id)}/resolve`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"reviewed_by_admin"})});loadAdminPage();}catch(err){alert(err.message);}}));
        const utable=document.getElementById("adminUsersTable"); if(utable){ const header=utable.closest("table")?.querySelector("thead tr"); if(header && header.children.length===5) header.insertAdjacentHTML("beforeend","<th>Actions</th>"); } if(utable)utable.innerHTML=(userData.users||[]).map(u=>`<tr><td>${escapeHtml(u.name||"User")}</td><td>${escapeHtml(u.email||"—")}</td><td>${escapeHtml(u.phone||"—")}</td><td>${escapeHtml(u.role||"user")}</td><td>${escapeHtml(u.status||"active")}</td><td>${u.role==="admin"?"Protected":`<button class="secondary-button user-status-btn" data-id="${escapeHtml(u.id)}" data-status="${u.status==="inactive"?"active":"inactive"}">${u.status==="inactive"?"Activate":"Deactivate"}</button>`}</td></tr>`).join("") || `<tr><td colspan="6">No users.</td></tr>`;
        utable?.querySelectorAll(".user-status-btn").forEach(b=>b.addEventListener("click",async()=>{try{await fetchJson(`/api/admin/users/${encodeURIComponent(b.dataset.id)}/status`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({status:b.dataset.status})});loadAdminPage();}catch(err){alert(err.message);}}));
    }catch(err){page.innerHTML=`<div class="admin-denied"><h1>Admin error</h1><p>${escapeHtml(err.message)}</p></div>`;}
}

// ============================================================
// LIST PROPERTY PAGE
// ============================================================

function setupPropertyListingPage() {
    const form=document.getElementById("dynamicPropertyForm"); if(!form)return;
    if(!currentUser){
        const feedback=document.getElementById("listingFeedback");if(feedback){feedback.className="status-feedback error";feedback.textContent="Please login before publishing a property.";}
        form.querySelectorAll("input,select,textarea,button").forEach(el=>el.disabled=true);
        return;
    }
    const typeSelector=document.getElementById("propTypeSelector");
    const sections={House:document.getElementById("houseFieldsSection"),Apartment:document.getElementById("apartmentFieldsSection"),Plot:document.getElementById("plotFieldsSection")};
    const setSection=section=>{
        Object.values(sections).forEach(s=>s&&(s.style.display="none"));
        Object.entries(sections).forEach(([name,s])=>{if(!s)return;const active=s===section;s.querySelectorAll("input,select,textarea").forEach(el=>{el.disabled=!active;if(!active)el.required=false;});});
        if(section)section.style.display="block";
    };
    const updateType=()=>{const t=typeSelector?.value||"Apartment";const sec=sections[t]||sections.Apartment;setSection(sec);if(t==="House")document.getElementById("houseBuiltUpArea")?.setAttribute("required","true");if(t==="Apartment")document.getElementById("aptBuiltUpArea")?.setAttribute("required","true");if(t==="Plot")document.getElementById("plotArea")?.setAttribute("required","true");};
    typeSelector?.addEventListener("change",updateType);updateType();

    const fileInput=document.getElementById("propertyImagesInput"), grid=document.getElementById("uploadThumbnailsGrid"), drop=document.getElementById("dropZone");
    let selectedFiles=[];
    const render=()=>{if(!grid)return;grid.innerHTML="";selectedFiles.forEach((file,i)=>{const box=document.createElement("div");box.className="preview-box";const img=document.createElement("img");img.alt=`Photo ${i+1}`;img.src=URL.createObjectURL(file);const btn=document.createElement("button");btn.type="button";btn.className="preview-remove-btn";btn.textContent="×";btn.addEventListener("click",()=>{selectedFiles.splice(i,1);render();});box.append(img,btn);grid.appendChild(box);});};
    const addFiles=files=>{for(const file of files){if(selectedFiles.length>=20)break;if(!["image/jpeg","image/png","image/webp"].includes(file.type)){alert(`${file.name}: JPG, JPEG, PNG or WEBP only.`);continue;}if(file.size>10*1024*1024){alert(`${file.name}: image exceeds 10 MB.`);continue;}if(!selectedFiles.some(f=>f.name===file.name&&f.size===file.size))selectedFiles.push(file);}render();};
    fileInput?.addEventListener("change",()=>addFiles(Array.from(fileInput.files||[])));
    drop?.addEventListener("click",()=>fileInput?.click());
    drop?.addEventListener("dragover",e=>{e.preventDefault();drop.style.borderColor="#2563eb";});
    drop?.addEventListener("dragleave",()=>drop.style.borderColor="");
    drop?.addEventListener("drop",e=>{e.preventDefault();drop.style.borderColor="";addFiles(Array.from(e.dataTransfer.files||[]));});
    document.getElementById("detectGpsBtn")?.addEventListener("click",()=>{
        const btn=document.getElementById("detectGpsBtn"),status=document.getElementById("gpsStatusText");if(!navigator.geolocation){if(status)status.textContent="Geolocation is not supported.";return;}btn.disabled=true;if(status)status.textContent="Requesting GPS coordinates...";
        navigator.geolocation.getCurrentPosition(async pos=>{const lat=pos.coords.latitude,lon=pos.coords.longitude;document.getElementById("propLatitude").value=lat;document.getElementById("propLongitude").value=lon;try{const d=await fetchJson(`/reverse-geocode?lat=${lat}&lon=${lon}`);if(d.state)document.getElementById("propState").value=d.state;if(d.city)document.getElementById("propCity").value=d.city;if(d.locality)document.getElementById("propLocality").value=d.locality;if(d.address)document.getElementById("propAddress").value=d.address;if(status)status.textContent=`✓ GPS coordinates detected (${lat.toFixed(4)}, ${lon.toFixed(4)}).`;}catch{if(status)status.textContent=`Coordinates detected (${lat.toFixed(4)}, ${lon.toFixed(4)}).`;}finally{btn.disabled=false;}},()=>{if(status)status.textContent="Unable to retrieve GPS location.";btn.disabled=false;});
    });
    form.addEventListener("submit",async e=>{
        e.preventDefault();const feedback=document.getElementById("listingFeedback"),submit=document.getElementById("submitListingBtn");if(!selectedFiles.length){feedback.className="status-feedback error";feedback.textContent="Please select at least one property photo.";return;}
        const fd=new FormData(form);fd.delete("images");selectedFiles.forEach(f=>fd.append("images",f));
        const t=typeSelector?.value||"Apartment";
        const area=t==="House"?document.getElementById("houseBuiltUpArea")?.value:t==="Plot"?document.getElementById("plotArea")?.value:document.getElementById("aptBuiltUpArea")?.value;
        fd.set("area",area||"");
        const copyName=(id,key)=>{const v=document.getElementById(id)?.value;if(v!==undefined)fd.set(key,v);};
        if(t==="House"){copyName("houseBhk","bhk");copyName("houseBathrooms","bathrooms");copyName("houseParking","parking");copyName("houseFacing","facing");copyName("houseFurnishing","furnishing");copyName("houseFloors","floors");copyName("housePlotArea","plot_area");copyName("houseLength","length");copyName("houseWidth","width");copyName("houseBuiltUpArea","built_up_area");copyName("houseCarpetArea","carpet_area");}
        if(t==="Apartment"){copyName("aptBhk","bhk");copyName("aptBathrooms","bathrooms");copyName("aptParking","parking");copyName("aptFacing","facing");copyName("aptFurnishing","furnishing");copyName("aptFloorNum","floor_number");copyName("aptTotalFloors","total_floors");copyName("aptBuiltUpArea","built_up_area");copyName("aptCarpetArea","carpet_area");copyName("aptAge","property_age");}
        if(t==="Plot"){copyName("plotArea","plot_area");copyName("plotLength","length");copyName("plotWidth","width");copyName("plotFacing","facing");copyName("plotRoadWidth","road_width");copyName("plotParking","parking");}
        submit.disabled=true;submit.textContent="Publishing Property...";feedback.className="status-feedback";feedback.textContent="";
        try{const data=await fetchJson("/list-property",{method:"POST",body:fd,credentials:"include"});feedback.className="status-feedback success";feedback.innerHTML=`<strong>✓ Listing Published Successfully!</strong><br>Property ID: #${data.property_id} • Status: Active • Photos: ${data.image_count}<br><a href="${getDetailsUrl({id:data.property_id})}" style="color:#027a48;font-weight:700;text-decoration:underline">View Your Published Property →</a>`;form.reset();selectedFiles=[];render();updateType();}catch(err){feedback.className="status-feedback error";feedback.textContent=err.message;}finally{submit.disabled=false;submit.textContent="Publish Listing Immediately →";}
    });
}

async function applyBrowserLocationForRecommendations() {
    const hasUserLocation = ["searchState", "searchCity", "searchLocality"].some(id => document.getElementById(id)?.value.trim());
    if (hasUserLocation || !navigator.geolocation) return;

    await new Promise(resolve => {
        navigator.geolocation.getCurrentPosition(async position => {
            try {
                const { latitude, longitude } = position.coords;
                const data = await fetchJson(`/reverse-geocode?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`);
                if (data.state) setInputValue("searchState", data.state);
                if (data.city) setInputValue("searchCity", data.city);
                if (data.locality) setInputValue("searchLocality", data.locality);
                const status = document.getElementById("recommendationLocationStatus");
                if (status) status.textContent = data.city ? `Using nearby location: ${data.locality ? data.locality + ", " : ""}${data.city}` : "Using your nearby location";
            } catch { /* location is an enhancement; manual search still works */ }
            resolve();
        }, () => resolve(), { enableHighAccuracy: false, timeout: 7000, maximumAge: 300000 });
    });
}

// ============================================================
// INITIALIZATION
// ============================================================
async function init() {
    // Bind independent interactive tools first.
    // This prevents slow startup requests from delaying
    // AI Valuation, Compare, or the AI Assistant.
    setupValuationTool();
    setupRateCalculator();
    setupComparison();
    setupAssistant();

    await getCurrentUser();

    ensureAuthLinks();
    setupAuthActions();
    setupAuthModal();
    setupNotificationsDropdown();

    setupLocationAutocomplete();

    await loadLocationHierarchy();

    const searchPromise =
        setupSearchSection();

    setupFavoritesSection();

    await searchPromise;

    await applyBrowserLocationForRecommendations();

    await loadRecommendations();

    setupPropertyListingPage();

    await initializePropertyDetailsPage();

    await loadMessagesPage();

    await loadMyListingsPage();

    await loadAdminPage();

    updateCompareFloatingBar();
}
document.addEventListener("DOMContentLoaded", init);
