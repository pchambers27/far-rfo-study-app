from jinja2.ext import debug
from database import init_db
import os
import random
from flask import Flask, render_template, request, session, redirect, url_for
from database import get_all_questions, create_user, get_user_by_email, get_connection, record_attempt, get_far_parts, get_user_stats, get_far_parts_with_study_facts, get_study_facts
from werkzeug.security import check_password_hash
from functools import wraps
from sqlalchemy import text

app = Flask(__name__)
app.secret_key =os.environ.get("SECRET_KEY", "dev-only-key-change-in-production")

init_db()

# ======== Decorators ========

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped

# ======== Routes ========

@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    # Pull only the qeustions in the user's study session
    study_ids = session.get("study_question_ids")
    if not study_ids:
        return redirect(url_for("study"))

    # Get all questions matching those IDs, in their session-locked order
    all_questions = {q["id"]: q for q in get_all_questions()}
    quiz_data = [all_questions[qid] for qid in study_ids if qid in all_questions]

    # Look up current user info to show on page
    from database import get_connection
    conn = get_connection()
    user = conn.execute(text("SELECT email FROM users WHERE id = :id"), {"id": session.get("user_id")}).mappings().fetchone()
    conn.close()

    # Defensive: if somehow the session has user_id that doesn't exist in DB, log them out
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if "score" not in session:
        session["score"] = 0
    if "question_index" not in session:
        session["question_index"] = 0
    
    if request.method == "POST":
        user_answer = request.form["answer"]
        current_q = quiz_data[session["question_index"]]

        is_correct = user_answer.lower().strip() == current_q["answer"].lower().strip()

        if is_correct:
            session["score"] += 1
            session["last_result"] = "correct"
        else:
            session["last_result"] = "incorrect"

        session["last_correct_answer"] = current_q["answer"]

        session["last_explanation"] = current_q["explanation"]

        # Record the attempt to the database
        record_attempt(
            user_id=session["user_id"],
            question_id=current_q["id"],
            user_answer=user_answer,
            was_correct=is_correct
            )
        session["question_index"] += 1
        
  
    if session["question_index"] >= len(quiz_data):
        final_score = session["score"]
        total = len(quiz_data)
        for key in ["score", "question_index", "last_result", "last_correct_answer", "last_explanation"]:
            session.pop(key, None)
        session.pop("study_question_ids", None) # Clear the study set
        return f"""
        <!DOCTYPE html>
<html><head>
<title>Quiz Complete</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
</head><body class="bg-gray-50 min-h-screen">
<nav class="bg-blue-900 text-white shadow-md">
<div class="max-w-4xl mx-auto px-4 py-3"><h1 class="text-xl font-bold text-white">FAR RFO Study App</h1></div>
</nav>
<main class="max-w-2xl mx-auto px-4 py-12">
<div class="bg-white rounded-lg shadow-md p-8 text-center">
<h2 class="text-3xl font-bold text-gray-900 mb-4">Quiz Complete!</h2>
<p class="text-xl text-gray-700 mb-6">You scored <strong>{final_score} out of {total}</strong></p>
<a href="/study" class="inline-block px-6 py-3 bg-blue-900 text-white rounded hover:bg-blue-800 font-medium">Study Again</a>
</div></main></body></html>"""
     
    current_question = quiz_data[session["question_index"]]
    return render_template(
        "index.html", 
        question=current_question,
        last_result=session.get("last_result"),
        last_correct_answer=session.get("last_correct_answer"),
        last_explanation=session.get("last_explanation"),
        user_email=user["email"]
    )


@app.route("/study", methods=["GET", "POST"]) #Commenting here for database testing
@login_required
def study():
    far_parts = get_far_parts() # list of (name, count) tuples

    if request.method == "POST":
        selected_parts = request.form.getlist("parts")
        session_length = int(request.form.get("session_length", 10))

        # Validate: must pick at least one Part
        if not selected_parts:
            return render_template(
                "study.html",
                far_parts=far_parts,
                error="Please select at least one FAR Part."
            )

        # Pull matching questions, shuffle,m take the first N
        questions = get_all_questions(far_parts=selected_parts)
        random.shuffle(questions)
        questions = questions[:session_length]

        # Lock the question IDs into the session
        session["study_question_ids"] = [q["id"] for q in questions]
        session["question_index"] = 0
        session["score"] = 0
        # Clear any stale feedback fomr previous quiz
        for key in ["last_result", "last_correct_answer", "last_explanation"]:
            session.pop(key, None)
            
        return redirect(url_for("home"))
        
    return render_template("study.html", far_parts=far_parts)

@app.route("/learn")
@login_required
def learn():
    far_parts = get_far_parts_with_study_facts()
    return render_template("learn.html", far_parts=far_parts)

@app.route("/learn/<part_name>")
@login_required
def learn_part(part_name):
    facts = get_study_facts(part_name)
    if not facts:
        return redirect(url_for("learn"))
    return render_template("learn_part.html", part_name=part_name, facts=facts)



@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if not email or not password:
            error = "Email and password are required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        else:
            user_id = create_user(email, password)
            if user_id is None:
                error = "An account with that email already exists."
            else:
                session.clear()
                session["user_id"] = user_id
                return redirect(url_for("study"))
    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "Invalid email or password."
        else:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("study"))

    return render_template("login.html", error=error)

@app.route("/stats")
@login_required
def stats():
    user_stats = get_user_stats(session["user_id"])
    return render_template("stats.html", user_stats = user_stats)




@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/reset")
@login_required
def reset():
    user_id = session.get("user_id")
    session.clear()
    session["user_id"] = user_id
    return redirect(url_for("home"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
