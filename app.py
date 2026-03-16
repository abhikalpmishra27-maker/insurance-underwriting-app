"""
Flask application for AI-Powered Life Insurance Underwriting.
"""

import json
import os
import base64
import logging
import re

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv

from underwriting_engine import ProposalForm, underwrite
from models import init_db, get_user_by_id, get_user_by_username, create_user, verify_password, User

load_dotenv()

app = Flask(__name__)
CORS(app)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

# ---------------------------------------------------------------------------
# Flask-Login setup
# ---------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return get_user_by_id(int(user_id))


@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({"error": "Authentication required. Please log in."}), 401


# Initialise the database on first import
init_db()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
)
logger = logging.getLogger(__name__)

MAX_PDF_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@app.route("/api/auth/register", methods=["POST"])
def register():
    """Create a new user account."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    if not USERNAME_RE.match(username):
        return jsonify({
            "error": "Username must be 3-30 characters and contain only letters, numbers, and underscores."
        }), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    if get_user_by_username(username):
        return jsonify({"error": "Username is already taken."}), 409

    user = create_user(username, password)
    login_user(user)
    logger.info("New user registered: %s", username)
    return jsonify({"success": True, "user": {"id": user.id, "username": user.username}}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Authenticate an existing user."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    row = get_user_by_username(username)
    if not row or not verify_password(password, row["password"]):
        return jsonify({"error": "Invalid username or password."}), 401

    user = User(id=row["id"], username=row["username"])
    login_user(user)
    logger.info("User logged in: %s", username)
    return jsonify({"success": True, "user": {"id": user.id, "username": user.username}})


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def logout():
    """Log out the current user."""
    logger.info("User logged out: %s", current_user.username)
    logout_user()
    return jsonify({"success": True})


@app.route("/api/auth/status")
def auth_status():
    """Return current authentication state."""
    if current_user.is_authenticated:
        return jsonify({
            "authenticated": True,
            "user": {"id": current_user.id, "username": current_user.username},
        })
    return jsonify({"authenticated": False})


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "insurance-underwriting-app"})


@app.route("/api/extract", methods=["POST"])
@login_required
def extract():
    """
    Accept a PDF file upload, send it to the Claude API for extraction,
    and return the structured proposal data as JSON.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Please attach a PDF file."}), 400

    pdf_file = request.files["file"]
    if pdf_file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    if not pdf_file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are supported."}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY is not configured")
        return jsonify({"error": "Server configuration error: API key not set."}), 500

    pdf_bytes = pdf_file.read()
    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        return jsonify({"error": "PDF file exceeds the 5 MB size limit."}), 400

    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    try:
        import anthropic  # imported here so the module loads without the SDK installed

        client = anthropic.Anthropic(api_key=api_key)

        extraction_prompt = """You are an insurance underwriting data extraction assistant.
Extract all relevant information from this life insurance proposal form PDF and return it as a JSON object.

Extract the following fields (use null if not found):
{
  "name": "full name of applicant",
  "gender": "Male or Female",
  "dob": "date of birth in DD/MM/YYYY format",
  "place_of_residence": "city/state/country",
  "profession": "occupation/job title",
  "height_cm": numeric height in centimetres,
  "weight_kg": numeric weight in kilograms,
  "yearly_income": numeric annual income,
  "source_of_income": "salary/business/profession/self-employed",
  "base_cover": numeric life cover amount,
  "cir_cover": numeric critical illness cover amount,
  "accident_cover": numeric accident cover amount,
  "parent_health_status": "both_above_65 or one_above_65 or both_below_65",
  "health_conditions": {
    "thyroid": 0-4 severity (0=none),
    "asthma": 0-4 severity,
    "hypertension": 0-4 severity,
    "diabetes": 0-4 severity,
    "gut_disorder": 0-4 severity
  },
  "habits": {
    "smoking": "none/occasionally/moderate/high",
    "alcohol": "none/occasionally/moderate/high",
    "tobacco": "none/occasionally/moderate/high"
  },
  "risky_occupations": ["athlete","pilot","driver","merchant_navy","oil_gas"] (list only applicable ones)
}

Return ONLY the JSON object, no additional text or markdown fences."""

        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": extraction_prompt,
                        },
                    ],
                }
            ],
        )

        raw_text = message.content[0].text.strip()

        # Strip markdown code fences if the model included them
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        extracted = json.loads(raw_text)
        logger.info("Successfully extracted proposal data for: %s", extracted.get("name", "unknown"))
        return jsonify({"success": True, "data": extracted})

    except json.JSONDecodeError as exc:
        logger.error("Claude returned non-JSON response: %s", exc)
        return jsonify({"error": "AI returned an unexpected response format. Please try again."}), 500
    except ImportError:
        logger.error("anthropic package is not installed")
        return jsonify({"error": "Server configuration error: AI library not installed."}), 500
    except Exception as exc:  # noqa: BLE001 — catch-all for Anthropic SDK errors (APIError, etc.)
        logger.exception("Error calling Claude API: %s", exc)
        return jsonify({"error": f"AI extraction failed: {str(exc)}"}), 500


@app.route("/api/underwrite", methods=["POST"])
@login_required
def api_underwrite():
    """
    Accept proposal data as JSON and run it through the Python underwriting engine.
    Returns the full underwriting report as JSON.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON."}), 400

    required_fields = [
        "name", "gender", "dob", "place_of_residence", "profession",
        "height_cm", "weight_kg", "yearly_income", "source_of_income",
        "base_cover", "cir_cover", "accident_cover", "parent_health_status",
    ]
    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        proposal = ProposalForm(
            name=str(data["name"]),
            gender=str(data["gender"]),
            dob=str(data["dob"]),
            place_of_residence=str(data["place_of_residence"]),
            profession=str(data["profession"]),
            height_cm=float(data["height_cm"]),
            weight_kg=float(data["weight_kg"]),
            yearly_income=float(data["yearly_income"]),
            source_of_income=str(data["source_of_income"]),
            base_cover=float(data["base_cover"]),
            cir_cover=float(data["cir_cover"]),
            accident_cover=float(data["accident_cover"]),
            parent_health_status=str(data["parent_health_status"]),
            health_conditions=data.get("health_conditions", {}),
            habits=data.get("habits", {}),
            risky_occupations=data.get("risky_occupations", []),
        )

        report = underwrite(proposal)

        # Convert flags list of tuples to list of dicts for JSON serialisation
        report["flags"] = [
            {"level": f[0], "code": f[1], "message": f[2]}
            for f in report.get("flags", [])
        ]

        logger.info("Underwriting complete for: %s | decision: %s", proposal.name, report.get("uw_decision"))
        return jsonify({"success": True, "report": report})

    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 422
    except KeyError as exc:
        return jsonify({"error": f"Missing data field: {exc}"}), 400
    except Exception as exc:  # noqa: BLE001 — unexpected runtime errors
        logger.exception("Unexpected error during underwriting: %s", exc)
        return jsonify({"error": f"Underwriting error: {str(exc)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
