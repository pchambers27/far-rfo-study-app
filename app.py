import os
from flask import Flask, render_template, request, session, redirect, url_for
from database import get_all_questions

app = Flask(__name__)
app.secret_key = "any-string-will-do-for-now"

@app.route("/", methods=["GET", "POST"])
def home():
    quiz_data = get_all_questions()

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
        session.clear()
        return (f"Quiz Complete! Your final score is: {final_score} out of {total}")
     
    current_question = quiz_data[session["question_index"]]
    return render_template(
        "index.html", 
        question=current_question,
        last_result=session.get("last_result"),
        last_correct_answer=session.get("last_correct_answer"),
        last_explanation=session.get("last_explanation"),
    )

@app.route("/reset")
def reset():
    session.clear()
    return "Session cleared. <a href='/'>Start over</a>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
