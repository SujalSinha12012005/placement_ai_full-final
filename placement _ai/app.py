from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
import os, csv, json, re
from werkzeug.utils import secure_filename
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = "a_very_long_random_secret_123456789"

# === CONFIG ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ GEMINI_API_KEY not set! Please set it before running the app.")

genai.configure(api_key=GEMINI_API_KEY)

RESUMES_FOLDER = os.path.join(app.root_path, "resumes")
USERS_CSV = os.path.join(app.root_path, "users.csv")
SUBMISSIONS_CSV = os.path.join(app.root_path, "submissions.csv")
ALLOWED_EXT = {".pdf"}

SUBMISSIONS_FIELDS = [
    "Name", "Email", "Skills", "Filename",
    "Score", "BestRole", "MissingSkills", "Suggestions", "AIFeedback"
]

# === HELPERS ===
def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXT

def ensure_users_csv():
    os.makedirs(RESUMES_FOLDER, exist_ok=True)
    if not os.path.exists(USERS_CSV):
        with open(USERS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Email", "Password", "IsAdmin"])
            writer.writerow(["admin@admin.com", "admin123", "1"])

def ensure_submissions_csv():
    if not os.path.exists(SUBMISSIONS_CSV):
        with open(SUBMISSIONS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SUBMISSIONS_FIELDS)
            writer.writeheader()

def clean_to_json(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:].strip()
    m = re.search(r"\{.*?\}", t, re.DOTALL)
    return m.group(0) if m else t

def analyze_resume_with_ai(skills_text: str):
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = f"""
        You are a hiring assistant. Given this candidate's skills:
        {skills_text}

        1) Give a score from 0 to 100 for general software engineering employability.
        2) Suggest the single most suitable job role/title.
        3) List 3-8 missing or high-impact skills they should learn next.
        4) Give a short improvement plan (1-2 sentences).

        Respond ONLY as valid JSON in this exact schema:
        {{
          "score": 88,
          "best_role": "Full-Stack Software Engineer",
          "missing_skills": ["React", "REST APIs", "SQL", "Unit Testing"],
          "suggestions": "Focus on modern web frameworks, build 2 projects using REST and write unit tests."
        }}
        """
        resp = model.generate_content(prompt)
        raw = getattr(resp, "text", None) or resp.parts[0].text
        js = clean_to_json(raw)

        data = json.loads(js)
        score = int(data.get("score", 50))
        best_role = data.get("best_role", "Generalist")
        missing_skills = data.get("missing_skills", [])
        if isinstance(missing_skills, str):
            missing_skills = [s.strip() for s in missing_skills.split(",") if s.strip()]
        suggestions = data.get("suggestions", "Strengthen fundamentals and build portfolio projects.")
        missing_skills_str = ", ".join(missing_skills)
        return score, best_role, missing_skills_str, suggestions, raw

    except Exception as e:
        return 50, "AI Processing Failed", "", f"AI Error: {e}", f"AI Error: {e}"

def generate_quiz_from_skills(skills_text: str):
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = f"""
        You are a quiz generator. Based on these skills: {skills_text}
        Create 4-5 multiple choice questions with 4 options each.
        Mark the correct answer with "(correct)" after it.
        Respond ONLY in JSON in this format:

        [
          {{
            "question": "Question text?",
            "options": ["option1", "option2 (correct)", "option3", "option4"]
          }},
          ...
        ]
        """
        resp = model.generate_content(prompt)
        raw = getattr(resp, "text", None) or resp.parts[0].text
        js = clean_to_json(raw)
        quiz = json.loads(js)
        return quiz, raw

    except Exception as e:
        return [], f"AI Error: {e}"

# === ROUTES ===
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if not email or not password:
            flash("Provide email and password", "danger")
            return redirect(url_for("signup"))

        with open(USERS_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Email") == email:
                    flash("Account already exists. Please login.", "warning")
                    return redirect(url_for("login"))

        with open(USERS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([email, password, "0"])

        flash("Account created. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        found = False
        is_admin = False
        with open(USERS_CSV, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Email") == email and row.get("Password") == password:
                    found = True
                    is_admin = (row.get("IsAdmin") == "1")
                    break
        if found:
            session["user"] = email
            session["is_admin"] = bool(is_admin)
            flash("Logged in successfully", "success")
            if is_admin:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("upload"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user" not in session:
        flash("Please login to upload resume", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        skills = request.form.get("skills", "").strip()
        resume = request.files.get("resume")

        if not (name and email and skills and resume):
            flash("All fields required", "danger")
            return redirect(url_for("upload"))

        if not allowed_file(resume.filename):
            flash("Only PDF resumes are allowed", "danger")
            return redirect(url_for("upload"))

        filename = secure_filename(resume.filename)
        save_path = os.path.join(RESUMES_FOLDER, filename)
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(save_path):
            filename = f"{base}_{counter}{ext}"
            save_path = os.path.join(RESUMES_FOLDER, filename)
            counter += 1

        resume.save(save_path)

        # AI Analysis
        score, best_role, missing_skills, suggestions, raw_feedback = analyze_resume_with_ai(skills)

        # Write to CSV
        with open(SUBMISSIONS_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SUBMISSIONS_FIELDS)
            if f.tell() == 0:
                writer.writeheader()
            writer.writerow({
                "Name": name,
                "Email": email,
                "Skills": skills,
                "Filename": filename,
                "Score": score,
                "BestRole": best_role,
                "MissingSkills": missing_skills,
                "Suggestions": suggestions,
                "AIFeedback": raw_feedback
            })

        return render_template(
            "upload.html",
            score=score,
            best_role=best_role,
            missing_skills=missing_skills,
            suggestions=suggestions
        )

    return render_template("upload.html")

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if "user" not in session:
        flash("Please login to take the quiz", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        user_answers = request.form.to_dict()
        quiz_data = session.get("quiz_data")
        if not quiz_data:
            flash("Quiz session expired. Please try again.", "warning")
            return redirect(url_for("quiz"))

        correct_count = 0
        results = []

        for idx, q in enumerate(quiz_data):
            q_key = f"q{idx}"
            user_answer = user_answers.get(q_key, "")
            options = q.get("options", [])
            correct_option = next((opt.replace(" (correct)", "") for opt in options if "(correct)" in opt), None)

            is_correct = (user_answer == correct_option)
            if is_correct:
                correct_count += 1

            results.append({
                "question": q.get("question"),
                "user_answer": user_answer,
                "correct_answer": correct_option,
                "is_correct": is_correct
            })

        score = int((correct_count / len(quiz_data)) * 100)
        session.pop("quiz_data", None)  # Clear quiz after completion

        return render_template("quiz_result.html", results=results, score=score)

    # Hardcoded quiz questions for testing
    quiz = [
        {
            "question": "Which HTML element is used to define the title of a document?",
            "options": [
                "head (correct)",
                "title",
                "meta",
                "header"
            ]
        },
        {
            "question": "What does CSS stand for?",
            "options": [
                "Cascading Style Sheets (correct)",
                "Colorful Style Sheets",
                "Computer Style Sheets",
                "Creative Style Sheets"
            ]
        },
        {
            "question": "Which property is used to change the background color in CSS?",
            "options": [
                "background-color (correct)",
                "color",
                "bgcolor",
                "background"
            ]
        },
        {
            "question": "In JavaScript, which keyword declares a variable?",
            "options": [
                "var (correct)",
                "int",
                "let",
                "const"
            ]
        }
    ]

    session["quiz_data"] = quiz
    return render_template("quiz.html", quiz=quiz)

@app.route("/ask", methods=["POST"])
def ask_question():
    if "user" not in session:
        flash("Please login to continue.", "warning")
        return redirect(url_for("login"))

    user_question = request.form.get("user_question", "").strip()

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        prompt = f"""
        You are a helpful career advisor. Answer this question about resume building or career advice in a concise way:

        Question: {user_question}
        """
        resp = model.generate_content(prompt)
        answer = getattr(resp, "text", None) or resp.parts[0].text

    except Exception:
        answer = "Sorry, I couldn't get an AI answer right now. Please try again later."

    # Get last submission for user
    latest_submission = None
    if os.path.exists(SUBMISSIONS_CSV):
        with open(SUBMISSIONS_CSV, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            user_submissions = [r for r in reader if r.get("Email") == session["user"]]
            if user_submissions:
                latest_submission = user_submissions[-1]

    if not latest_submission:
        flash("No previous resume found. Please upload first.", "warning")
        return redirect(url_for("upload"))

    return render_template("upload.html",
        score=latest_submission.get("Score"),
        best_role=latest_submission.get("BestRole"),
        missing_skills=latest_submission.get("MissingSkills"),
        suggestions=latest_submission.get("Suggestions"),
        answer=answer
    )

@app.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        flash("Admin access required", "danger")
        return redirect(url_for("login"))

    skill = request.args.get("skill", "").strip().lower()
    rows = []
    if os.path.exists(SUBMISSIONS_CSV):
        with open(SUBMISSIONS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if skill and skill not in (row.get("Skills", "").lower()):
                    continue
                rows.append(row)

    def to_int(x):
        try:
            return int(float(x))
        except Exception:
            return 0
    rows.sort(key=lambda r: to_int(r.get("Score", 0)), reverse=True)

    return render_template("admin.html", data=rows, skill=skill)

@app.route("/resumes/<path:filename>")
def serve_resume(filename):
    return send_from_directory(RESUMES_FOLDER, filename, as_attachment=False)

# Boot checks
ensure_users_csv()
ensure_submissions_csv()

if __name__ == "__main__":
    app.run(debug=True)
