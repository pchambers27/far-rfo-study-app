import sqlite3
import json

DATABASE_PATH = "quiz.db"

def get_connection():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Run schema.sql to create tables if they don't exist."""
    conn = get_connection()
    with open("schema.sql") as f:
        conn.executescript(f.read())
        conn.commit()
        conn.close()
        print("Database initialized.")

def get_all_questions():
    """Fetch all questions from the database as a list of dicts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()
    conn.close()

    questions = []
    for row in rows:
        questions.append({
            "id": row["id"],
            "far_part": row["far_part"],
            "topic": row["topic"],
            "qtype": row["qtype"],
            "question": row["question_text"],
            "choices": json.loads(row["choices"]) if row["choices"] else None,
            "answer": row["answer"],
            "explanation": row["explanation"],
        })
    return questions


if __name__ == "__main__":
    init_db()