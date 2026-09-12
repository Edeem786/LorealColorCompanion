"""Flask entry point. Run with python -m onboarding.server."""
import sqlite3
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from .catalog import CATALOG_DIR, load_catalog, list_catalogs
from .cvd_profile import get_cvd_profile, save_cvd_profile
from .actions import DATABASE, dispatch  # Retained for existing Python callers.
from .integrations import AccessibilityAssessment, MakeupRegion

ROOT = Path(__file__).resolve().parent


def create_app(database=DATABASE, *, catalog_directory=CATALOG_DIR, detect_region=None, assess_accessibility=None, detect_shades=None):
    """Optional adapters keep vision and accessibility independently testable."""
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024

    @app.before_request
    def check_request():
        if request.method == "POST":
            if request.headers.get("Origin") not in (None, request.host_url.rstrip("/")):
                abort(403, description="Cross-origin requests are not supported.")
            if request.path not in {"/api/detect-region", "/api/detect-shades"} and (request.content_length or 0) > 100_000:
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

    @app.post("/api/detect-shades")
    def extract_shades():
        category = request.form.get("category")
        if category not in {"lip", "blush"}:
            abort(400, description="Choose lip or blush for automatic detection.")
        uploaded = request.files.get("image")
        if uploaded is None or uploaded.mimetype != "image/png":
            abort(400, description="Provide a PNG in the image field.")
        image_bytes = uploaded.read(10 * 1024 * 1024 + 1)
        if len(image_bytes) > 10 * 1024 * 1024:
            abort(413, description="Image is too large.")
        if (len(image_bytes) < 24 or not image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
                or image_bytes[12:16] != b"IHDR"):
            abort(400, description="Expected PNG image data.")
        width = int.from_bytes(image_bytes[16:20], "big")
        height = int.from_bytes(image_bytes[20:24], "big")
        if not (0 < width <= 800 and 0 < height <= 800):
            abort(400, description="Use the browser-resized image (up to 800 pixels per side).")
        try:
            if detect_shades is not None:
                shades = detect_shades(image_bytes, category)
            else:
                # Keep optional CV imports out of normal startup and manual extraction.
                from .vision import detect_lip_shades, detect_blush_shades
                detector = detect_lip_shades if category == "lip" else detect_blush_shades
                shades = detector(image_bytes)
            if (not isinstance(shades, list) or len(shades) > 12 or any(
                not isinstance(shade, list) or len(shade) != 3 or any(
                    type(channel) is not int or not 0 <= channel <= 255 for channel in shade
                ) for shade in shades
            )):
                raise ValueError("Detector must return up to 12 sRGB integer triplets.")
            return {"shades": shades}
        except (ImportError, FileNotFoundError):
            app.logger.exception("Vision setup incomplete")
            return {"error": "Auto-detection needs the vision dependencies and face model installed. Use manual extraction for now."}, 503
        except Exception:
            app.logger.exception("Shade detection failed")
            return {"error": "Detection unavailable. Try another image or extract shades manually."}, 503

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
