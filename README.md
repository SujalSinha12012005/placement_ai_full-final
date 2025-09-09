# Placement AI

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![Flask](https://img.shields.io/badge/flask-2.x-orange.svg)]()
[![Gemini-1.5-flash](https://img.shields.io/badge/Gemini-1.5--flash-AI-green.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen.svg)]()

> **Placement AI** — a lightweight Flask web app that helps students and early-career engineers:
>
> - upload a PDF resume,
> - receive an AI-generated score and recommended job role,
> - get a list of missing / high-impact skills and short suggestions,
> - ask follow-up career/resume questions to an AI advisor,
> - optionally take basic quizzes to check readiness,
> - admin dashboard to view and sort submissions.

---

## Table of Contents

- [What it does](#what-it-does)
- [Key features](#key-features)
- [Tech stack](#tech-stack)
- [System architecture (high-level)](#system-architecture-high-level)
- [SDG alignment](#sdg-alignment)
- [Risk factors & mitigation](#risk-factors--mitigation)
- [Quick start](#quick-start)
- [Environment variables](#environment-variables)
- [File & CSV formats](#file--csv-formats)
- [Routes / Endpoints summary](#routes--endpoints-summary)
- [Caching & rate-limit handling (avoid 429s)](#caching--rate-limit-handling-avoid-429s)
- [Testing & troubleshooting](#testing--troubleshooting)
- [Roadmap & recommended next steps](#roadmap--recommended-next-steps)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

This app connects a simple Flask frontend to Google’s Gemini model (via `google.generativeai`) to:

1. Analyze skills provided by the user (and optionally extracted text from uploaded PDF).
2. Ask the model to output a JSON with:
   - `score` (0–100)
   - `best_role` (string)
   - `missing_skills` (array)
   - `suggestions` (text)
3. Save the output to a local CSV (`submissions.csv`) and show results on the page.
4. Provide an **Ask a Question** interface where the user can query the AI advisor; the app responds using the latest submission context.
5. Provide a simple quiz endpoint for immediate assessment (hardcoded or AI-generated).

---

## Key features

- PDF resume upload (only `.pdf` allowed).
- AI resume analysis via **Gemini 1.5 Flash** (configured in `app.py`).
- Stores results in `submissions.csv`.
- Ask-a-question AI assistant tied to user’s last submission.
- Admin dashboard to view & sort submissions.
- Simple quiz flow with scoring and results page.
- Robust fallback messaging for API errors (e.g., 429).

---

## Tech stack

- **Backend:** Python + Flask  
- **Templates:** Jinja2 (Bootstrap for styling)  
- **AI:** Google Generative AI (Gemini — `gemini-1.5-flash`)  
- **Storage:** CSV files (`users.csv`, `submissions.csv`) — easy to replace with a DB later  
- **PDF parsing:** `PyPDF2` (optional, for text extraction)  
- **Dependencies:** listed in `requirements.txt` (example below)

**Example `requirements.txt`**


Flask>=2.2
google-generativeai>=0.5.0
PyPDF2>=3.0
werkzeug
python-dotenv




---

## System architecture (high-level)

**Client (browser)** ↔ **Flask app (app.py)** ↔ **Gemini AI**  
- The Flask app handles auth (CSV), file uploads, AI requests, and CSV storage.  
- Gemini performs NLP tasks (scoring, recommendations, answers).  
- Admin UI reads `submissions.csv` and serves the resume files from `/resumes`.

**ASCII diagram**

[ Browser ] <--HTTP--> [ Flask app (app.py) ] <--API--> [ Google Gemini AI ]
| | |
| |-- stores -> submissions.csv
| |-- serves -> /templates/*.html
| |-- stores files -> /resumes/


---

## SDG alignment

**Primary:** SDG 16 — Peace, Justice & Strong Institutions  
- Improves accountability/ transparency for placement support within institutions.

**Secondary:** SDG 4 — Quality Education  
- Improves learners’ employability by recommending targeted upskilling.

**Tertiary:** SDG 5 — Gender Equality  
- Supports confidential, AI-assisted career guidance helping remove access barriers.

---

## Risk factors & mitigation (brief)

- **API Rate limits (429):** Add caching, backoff and clear user messaging. Consider paid tier for production.
- **Data privacy:** Keep PII secure. For production, use an encrypted database and HTTPS.
- **AI bias:** Add human oversight (admin review) and display AI confidence/notes.
- **System availability:** Use cloud deployment with autoscaling and backups.

---

## Quick start

1. Clone repo:
```bash
git clone https://github.com/<your-username>/placement-ai.git
cd placement-ai

2.Create a virtual environment & install:
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows PowerShell
pip install -r requirements.txt

Add .env (or set env var):

3.GEMINI_API_KEY=your_gemini_api_key_here
FLASK_ENV=development

4.Run: python app.py
5.Visit: http://127.0.0.1:5000/
```

placement-ai/
├─ app.py                  # Main Flask app
├─ requirements.txt        # Python dependencies
├─ .env                    # Environment variables (GEMINI_API_KEY, FLASK_ENV)
├─ resumes/                # Uploaded resumes (PDF files)
├─ submissions.csv         # Stores AI analysis results
├─ users.csv               # (Optional) Stores user details
└─ templates/              # HTML templates
   ├─ base.html
   ├─ upload.html
   ├─ admin.html
   ├─ quiz.html
   └─ quiz_result.html
