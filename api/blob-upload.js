const { issueSignedToken, presignUrl } = require("@vercel/blob");

module.exports = async function handler(req, res) {
    if (req.method !== "POST") {
        return res.status(405).json({
            success: false,
            error: "Method not allowed."
        });
    }

    try {
        // Verify the existing Flask login session.
        const host = req.headers.host;

        if (!host) {
            return res.status(400).json({
                success: false,
                error: "Unable to determine application host."
            });
        }

        const protocol =
            req.headers["x-forwarded-proto"] ||
            (process.env.VERCEL === "1" ? "https" : "http");

        const authResponse = await fetch(
            `${protocol}://${host}/auth/me`,
            {
                method: "GET",
                headers: {
                    cookie: req.headers.cookie || ""
                }
            }
        );

        if (!authResponse.ok) {
            return res.status(401).json({
                success: false,
                error: "Please log in before uploading property images."
            });
        }

        const authData = await authResponse.json();

        if (!authData.success || !authData.logged_in || !authData.user) {
            return res.status(401).json({
                success: false,
                error: "Please log in before uploading property images."
            });
        }

        const { pathname, contentType } = req.body || {};

        if (!pathname || !contentType) {
            return res.status(400).json({
                success: false,
                error: "pathname and contentType are required."
            });
        }

        const allowedTypes = [
            "image/jpeg",
            "image/png",
            "image/webp"
        ];

        if (!allowedTypes.includes(contentType)) {
            return res.status(400).json({
                success: false,
                error: "Only JPG, PNG and WEBP images are allowed."
            });
        }

        if (
            !/^properties\/[a-zA-Z0-9_-]{1,80}\/[a-zA-Z0-9_-]{1,120}\.(jpg|jpeg|png|webp)$/i.test(
                pathname
            )
        ) {
            return res.status(400).json({
                success: false,
                error: "Invalid property image path."
            });
        }

        const expiresAt = Date.now() + (10 * 60 * 1000);

        const token = await issueSignedToken({
            pathname,
            operations: ["put"],
            validUntil: expiresAt,
            maximumSizeInBytes: 10 * 1024 * 1024,
            allowedContentTypes: allowedTypes
        });

        const { presignedUrl } = await presignUrl(token, {
            pathname,
            operation: "put",
            validUntil: expiresAt
        });

        return res.status(200).json({
            success: true,
            uploadUrl: presignedUrl,
            pathname,
            user: {
                id: authData.user.id
            }
        });
    } catch (error) {
        console.error("Blob upload URL error:", error);

        return res.status(500).json({
            success: false,
            error: "Unable to prepare image upload."
        });
    }
};
