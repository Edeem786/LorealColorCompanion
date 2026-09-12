"""Flask entry point. Run with python -m onboarding.server."""
import sqlite3
import base64
from .vision import detect_lip_shades
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .catalog import CATALOG_DIR, load_catalog, list_catalogs
from .cvd_profile import get_cvd_profile, save_cvd_profile
from .actions import DATABASE, dispatch  # Retained for existing Python callers.
from .integrations import AccessibilityAssessment, MakeupRegion

ROOT = Path(__file__).resolve().parent


def create_app(database=DATABASE, *, catalog_directory=CATALOG_DIR, detect_region=None, assess_accessibility=None):
    """Two optional function arguments are the only integration wiring needed."""
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024

    @app.before_request
    def check_request():
        if request.method == "POST":
            if request.headers.get("Origin") not in (None, request.host_url.rstrip("/")):
                abort(403, description="Cross-origin requests are not supported.")
            if request.path != "/api/detect-region" and (request.content_length or 0) > 100_000:
                abort(413, description="JSON request is too large.")

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/")
    def index():
        return send_from_directory(ROOT, "index.html")

    @app.get("/<filename>")
    def assets(filename):
        if filename not in {"app.js", "colors.js", "cvd-form.js", "style.css"}:
            abort(404)
        return send_from_directory(ROOT, filename)

    @app.get("/api/capabilities")
    def capabilities():
        return {"region_detection": detect_region is not None,
                "cvd_assessment": assess_accessibility is not None}

    @app.post("/api/rating")
    def rating():
        return jsonify(dispatch("/api/rating", request.get_json(), database))

    @app.post("/api/detect-lip-shades")
    def detect_lip():
        data = request.get_json()
        if not data or "image" not in data:
            return jsonify({"error": "No image provided."}), 400

        try:
            # data["image"] is a data URL like "data:image/png;base64,iVBOR..."
            header, encoded = data["image"].split(",", 1)
            image_bytes = base64.b64decode(encoded)
        except Exception:
            return jsonify({"error": "Invalid image data."}), 400

        shades = detect_lip_shades(image_bytes)
        return jsonify({"shades": shades})

    @app.get("/api/catalogs")
    def catalogs():
        return {"catalogs": list_catalogs(catalog_directory)}

    @app.get("/api/cvd-profile")
    def cvd_profile():
        return {"profile": get_cvd_profile(request.args.get("user_id"), database)}

    @app.post("/api/cvd-profile")
    def update_cvd_profile():
        payload = request.get_json()
        if not isinstance(payload, dict):
            raise ValueError("Expected an object.")
        return {"profile": save_cvd_profile(payload.get("user_id"), payload.get("type"),
                                            payload.get("severity"), database)}

    @app.post("/api/recommend")
    @app.post("/api/rank")
    def rank():
        payload = request.get_json()
        if request.path == "/api/recommend":
            if not isinstance(payload, dict):
                raise ValueError("Expected an object.")
            payload = {**payload, "candidates": load_catalog(payload.get("category", "blush"), catalog_directory)}
            payload.setdefault("category", "blush")
        result = dispatch("/api/rank", payload, database)
        for candidate in result["results"]:
            candidate["accessibility"] = None
            if assess_accessibility is not None:
                try:
                    assessment = assess_accessibility(payload["user_id"], payload.get("category", "lip"), tuple(candidate["color"]))
                    if assessment is not None:
                        if not isinstance(assessment, AccessibilityAssessment):
                            raise ValueError("Expected AccessibilityAssessment or None.")
                        candidate["accessibility"] = assessment.to_dict()
                except Exception:
                    app.logger.exception("Accessibility integration failed")
                    candidate["accessibility_error"] = "Accessibility assessment unavailable."
        # CVD information is attached, never blended into personal taste or used to reorder.
        return jsonify(result)

    @app.post("/api/detect-region")
    def detect():
        if detect_region is None:
            return jsonify({"region": None, "message": "Select the lip region manually."})
        uploaded = request.files.get("image")
        if uploaded is None or uploaded.mimetype != "image/png":
            abort(400, description="Provide the browser-normalized PNG in the image field.")
        image_bytes = uploaded.read(10 * 1024 * 1024 + 1)
        if len(image_bytes) > 10 * 1024 * 1024:
            abort(413, description="Image is too large.")
        if not image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            abort(400, description="Expected PNG image data.")
        try:
            region = detect_region(image_bytes, "lip")
            if region is None:
                return {"region": None, "message": "No lip region found. Select it manually."}
            if not isinstance(region, MakeupRegion):
                raise ValueError("Expected MakeupRegion or None.")
            return {"region": region.to_dict(), "message": "Review and adjust the suggested lip region."}
        except Exception:
            app.logger.exception("Vision integration failed")
            return jsonify({"region": None, "message": "Detection unavailable. Select the lip region manually."}), 503

    @app.errorhandler(ValueError)
    @app.errorhandler(TypeError)
    @app.errorhandler(KeyError)
    def invalid_input(error):
        return jsonify({"error": str(error)}), 400

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.exception("Preference storage failed")
        return jsonify({"error": "Could not save or read feedback. Please retry."}), 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify({"error": error.description}), error.code

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8000, debug=False)
