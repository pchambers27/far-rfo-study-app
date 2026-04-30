import os
from flask import Flask, render_template, request, session, redirect, url_for
from database import get_all_questions, create_user, get_user_by_email
from werkzeug.security import check_password_hash
from functools import wraps



app = Flask(__name__)
app.secret_key = "any-string-will-do-for-now"

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
    quiz_data = get_all_questions()

    # Look up current user info to show on page
    from database import get_connection
    conn = get_connection()
    user = conn.execute("SELECT email FROM users WHERE id = ?", (session.get("user_id"),)).fetchone()
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

        if user_answer.lower().strip() == current_q["answer"].lower().strip():
            session["score"] += 1
            session["last_result"] = "correct"

        else:
            session["last_result"] = "incorrect"
            session["last_correct_answer"] = current_q["answer"]
            session["last_explanation"] = current_q["explanation"]
  
        session["question_index"] += 1
        
  
    if session["question_index"] >= len(quiz_data):
        final_score = session["score"]
        total = len(quiz_data)
        for key in ["score", "question_index", "last_result", "last_correct_answer", "last_explanation"]:
            session.pop(key, None)
        return (f"Quiz Complete! Your final score is: {final_score} out of {total}")
     
    current_question = quiz_data[session["question_index"]]
    return render_template(
        "index.html", 
        question=current_question,
        last_result=session.get("last_result"),
        last_correct_answer=session.get("last_correct_answer"),
        last_explanation=session.get("last_explanation"),
        user_email=user["email"]
    )

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
            return redirect(url_for("home"))

    return render_template("login.html", error=error)

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
    app.run(host="0.0.0.0", port=port)
