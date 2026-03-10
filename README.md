# AI-Powered Life Insurance Underwriting App

A full-stack web application that automates life insurance underwriting using
AI-based PDF extraction (Claude) and a rules-based Python underwriting engine.

---

## Architecture

```
Browser  ──►  Flask (app.py)  ──►  Claude API  (PDF extraction)
                  │
                  └──►  underwriting_engine.py  (risk calculation)
```

| Layer | Technology |
|-------|-----------|
| Backend | Python Flask |
| Frontend | HTML / CSS / Vanilla JS (dark-themed SPA) |
| AI Extraction | Anthropic Claude (`claude-opus-4-5`) |
| Underwriting | Python rules engine + JS mirror |
| PDF Reports | jsPDF + jspdf-autotable (CDN) |

---

## Project Structure

```
insurance-underwriting-app/
├── app.py                   # Flask application
├── underwriting_engine.py   # Core Python underwriting engine
├── templates/
│   └── index.html           # Single-page application (dark theme)
├── requirements.txt
├── .env.example             # Environment variable template
├── .gitignore
├── Procfile                 # Deployment (Heroku / Render)
└── README.md
```

---

## Quick Start

### 1. Clone & install dependencies

```bash
git clone https://github.com/abhikalpmishra27-maker/insurance-underwriting-app.git
cd insurance-underwriting-app
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

### 3. Run the development server

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/` | Serve the frontend SPA |
| `GET`  | `/api/health` | Health check |
| `POST` | `/api/extract` | Upload PDF → Claude extracts proposal data |
| `POST` | `/api/underwrite` | JSON proposal → underwriting report |

### `POST /api/extract`

- **Content-Type**: `multipart/form-data`
- **Field**: `file` (PDF, max 5 MB)
- **Response**: `{ "success": true, "data": { ...proposal fields... } }`

### `POST /api/underwrite`

- **Content-Type**: `application/json`
- **Body**: Proposal JSON (see `ProposalForm` fields in `underwriting_engine.py`)
- **Response**: `{ "success": true, "report": { ...underwriting report... } }`

---

## Application Workflow

1. **Upload** — Drag-and-drop or browse for a PDF proposal form
2. **Extract** — Claude AI reads the PDF and extracts structured data
3. **Review** — Edit any extracted field before running underwriting
4. **Results** — View the underwriting decision, EMR breakdown, flags, and
   premium calculation; download as a PDF report

---

## Underwriting Logic

The engine computes an **Extra Mortality Rating (EMR)** from:

- **BMI** — Calculated from height/weight; mapped to EMR table
- **Family history** — Parent health status adds/subtracts EMR
- **Health conditions** — Thyroid, asthma, hypertension, diabetes, gut disorder
  (severity 1–4); co-morbidity extra loading for 2+ conditions
- **Lifestyle habits** — Smoking, alcohol, tobacco; co-existence loading for 2+
- **Risky occupation** — Pilot, driver, athlete, merchant navy, oil & gas

The total EMR determines the **Life Rating Class** (I–X) and drives loading
percentages on the base premium. CIR (Critical Illness) cover follows a
separate rating table and is declined above EMR 100 or age 60.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | — | Your Anthropic API key |
| `FLASK_SECRET_KEY` | No | `dev-secret-key-…` | Flask session secret |
| `FLASK_DEBUG` | No | `false` | Enable debug mode |
| `PORT` | No | `5000` | Server port |

---

## Deployment (Render / Heroku)

The `Procfile` is configured to run with **gunicorn**:

```
web: gunicorn app:app
```

Set the environment variables (`ANTHROPIC_API_KEY`, `FLASK_SECRET_KEY`) in
your hosting platform's dashboard, then deploy from the GitHub repository.

---

## Security Notes

- The Anthropic API key is **never** sent to the browser. All Claude calls are
  proxied through the Flask `/api/extract` endpoint.
- PDF files are processed in-memory and are never written to disk.
- CORS is enabled for development; restrict allowed origins in production.
