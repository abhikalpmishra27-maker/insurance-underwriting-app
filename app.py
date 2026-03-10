"""
Flask application for AI-Powered Life Insurance Underwriting.
"""

import os
import base64
import logging

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv

from underwriting_engine import ProposalForm, underwrite

load_dotenv()

app = Flask(__name__)
CORS(app)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s : %(message)s",
)
logger = logging.getLogger(__name__)

MAX_PDF_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "service": "insurance-underwriting-app"})


@app.route("/api/extract", methods=["POST"])
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

        import json
        # Strip markdown code fences if the model included them
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            raw_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        extracted = json.loads(raw_text)
        logger.info("Successfully extracted proposal data for: %s", extracted.get("name", "unknown"))
        return jsonify({"success": True, "data": extracted})

    except Exception as exc:  # noqa: BLE001
        logger.exception("Error calling Claude API: %s", exc)
        return jsonify({"error": f"AI extraction failed: {str(exc)}"}), 500


@app.route("/api/underwrite", methods=["POST"])
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

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during underwriting: %s", exc)
        return jsonify({"error": f"Underwriting error: {str(exc)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
