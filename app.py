import os
from flask import Flask, render_template, request, session
import json

app = Flask(__name__)
app.secret_key = "any-string-will-do-for-now"

@app.route("/", methods=["GET", "POST"])
def home():
    with open("questions.json") as f:
        quiz_data = json.load(f)

    if "score" not in session:
        session["score"] = 0
    if "question_index" not in session:
        session["question_index"] = 0
    
    if request.method == "POST":
        user_answer = request.form["answer"]

        if user_answer.lower().strip() == quiz_data[session["question_index"]]["answer"].lower():
            session["score"] += 1
  
        session["question_index"] += 1
        
  
    if session["question_index"] >= len(quiz_data):
        final_score = session["score"]
        total = len(quiz_data)
        session.clear()
        return (f"Quiz Complete! Your final score is: {final_score} out of {total}")
     
    first_question = quiz_data[session["question_index"]]
    return render_template("index.html", question=first_question)

if __name__ == "__main__":
  app.run(host="0.0.0.0", port=3000)
