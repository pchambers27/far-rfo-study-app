from jinja2.ext import debug
from database import init_db
import os
import random
from flask import Flask, render_template, request, session, redirect, url_for
from database import get_all_questions, create_user, get_user_by_email, get_connection, record_attempt, get_far_parts, get_user_stats, get_far_parts_with_study_facts, get_study_facts, get_active_tracks, get_track, get_stage_stats
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
@app.route("/")
def home():
    # Logged out users see the public landing page
    if "user_id" not in session:
        return render_template("landing.html")

    # Logged in users see the dashboard
    user_id = session["user_id"]
    user_email = session.get("user_email", "")

    user_stats = get_user_stats(user_id)
    total_attempts = sum(s["lifetime_total"] for s in user_stats)
    if total_attempts > 0:
        total_corect = sum(s["lifetime_correct"] for s in user_stats)
        overall_accuracy = round(100.0 * total_corect / total_attempts, 1)
    else:
        overall_accuracy = None
    return render_template("dashboard.html", user_email=user_email, total_attempts=total_attempts, overall_accuracy=overall_accuracy)




@app.route("/quiz", methods=["GET", "POST"])
@login_required
def quiz():
    
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
        last_result = session.get("last_result")
        last_correct_answer = session.get("last_correct_answer")
        last_explanation = session.get("last_explanation")
        for key in ["score", "question_index", "last_result", "last_correct_answer", "last_explanation"]:
            session.pop(key, None)
        session.pop("study_question_ids", None) # Clear the study set
        return render_template("quiz_complete.html", final_score=final_score, total=total, last_result=last_result, last_correct_answer=last_correct_answer, last_explanation=last_explanation)
     
    current_question = quiz_data[session["question_index"]]
    return render_template(
        "index.html", 
        question=current_question,
        last_result=session.get("last_result"),
        last_correct_answer=session.get("last_correct_answer"),
        last_explanation=session.get("last_explanation"),
        user_email=user["email"]
    )


@app.route("/study", methods=["GET", "POST"]) #Last commenting for the night to test database
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
            
        return redirect(url_for("quiz"))
        
    return render_template("study.html", far_parts=far_parts)

@app.route("/tracks/<track_id>")
@login_required
def track(track_id):
    track_data = get_track(track_id)
    if not track_data:
        return redirect(url_for("home"))

    user_id = session["user_id"]
    difficulty = track_data.get("question_filter", {}).get("difficulty")

    # Compute stats for each stage
    stages_with_stats = []
    for stage in track_data["stages"]:
        stats = get_stage_stats(user_id, stage["tags"], difficulty)
        stages_with_stats.append({**stage, "stats": stats})

    return render_template(
        "track.html",
        track=track_data,
        stages=stages_with_stats,
    )

@app.route("/tracks/<track_id>/stage/<int:stage_id>")
@login_required
def stage(track_id, stage_id):
    track_data = get_track(track_id)
    if not track_data:
        return redirect(url_for("home"))

    stage_data = next((s for s in track_data["stages"] if s["id"] == stage_id), None)
    if not stage_data:
        return redirect(url_for("track", track_id=track_id))

    difficulty = track_data.get("question_filter", {}).get("difficulty")
    stats = get_stage_stats(session["user_id"], stage_data["tags"], difficulty)

    return render_template(
        "stage.html",
        track=track_data,
        stage=stage_data,
        stats=stats,
    )


@app.route("/tracks/<track_id>/stage/<int:stage_id>/quiz")
@login_required
def start_stage_quiz(track_id, stage_id):
    track_data = get_track(track_id)
    if not track_data:
        return redirect(url_for("home"))

    stage_data = next((s for s in track_data["stages"] if s["id"] == stage_id), None)
    if not stage_data:
        return redirect(url_for("track", track_id=track_id))

    difficulty = track_data.get("question_filter", {}).get("difficulty")

    # Pull questions matching this stage's tags + track's difficulty
    questions = get_all_questions(tags=stage_data["tags"], difficulty=difficulty)

    if not questions:
        return redirect(url_for("stage", track_id=track_id, stage_id=stage_id))

    random.shuffle(questions)
    questions = questions[:10]

    session["study_question_ids"] = [q["id"] for q in questions]
    session["question_index"] = 0
    session["score"] = 0
    for key in ["last_result", "last_correct_answer", "last_explanation"]:
        session.pop(key, None)

    return redirect(url_for("quiz"))

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
                session["user_email"] = email
                return redirect(url_for("home"))
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
            session["user_email"] = email
            return redirect(url_for("home"))

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
