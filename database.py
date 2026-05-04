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

def get_all_questions(far_parts=None):
    """Fetch all questions from the database as a list of dicts."""
    conn = get_connection()

    if far_parts:
        # Build dynamic placeholder string: "?, ?, ?," for however many parts
        placeholders = ",".join(["?"] * len(far_parts))
        query = f"SELECT * FROM questions WHERE far_part IN ({placeholders}) ORDER BY id"
        rows = conn.execute(query, far_parts).fetchall()
    else:
        rows = conn.execute("SELECT * FROM questions ORDER BY id").fetchall()

    conn.close()

    questions = []
    for row in rows:
        questions.append({
             "id": row["id"],
             "far_part": row["far_part"],
             "topic": row["topic"],
             "qtype": row["qtype"],
             "question": row["question"],
             "choices": json.loads(row["choices"]) if row["choices"] else None,
             "answer": row["answer"],
             "explanation": row["explanation"]
        })
    return questions

def create_user(email, password):
    """Create a new user. Returns the new user's id, or None if email is taken."""
    from werkzeug.security import generate_password_hash

    email = email.lower().strip()
    password_hash = generate_password_hash(password)

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_email(email):
    """Look up the user by email. Returns the row, or None if not found."""
    email = email.lower().strip()
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row

def record_attempt(user_id, question_id, user_answer, was_correct):
    """Record one quiz attempt. Returns the new row's id."""
    conn = get_connection()
    cursor = conn.execute(
        """ INSERT INTO attempts (user_id, question_id, user_answer, was_correct) VALUES (?, ?, ?, ?)""",
        (user_id, question_id, user_answer, 1 if was_correct else 0))
    conn.commit()
    attempt_id = cursor.lastrowid
    conn.close()
    return attempt_id

def get_far_parts():
    """Return a list of (far_part, count) tuples for all Parts in the database, sorted."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT far_part, COUNT(*) as count
        FROM questions
        GROUP BY far_part
        ORDER BY far_part"""
    ).fetchall()
    conn.close()
    return[(row["far_part"], row["count"]) for row in rows]

def get_user_stats(user_id):
    """
    Return per-FAR-part stats for a user.
    Returns: list of dicts with far_part, lifetime stats, and recent stats."""
    conn = get_connection()

    # Lifetime stats per FAR Part
    lifetime_rows = conn.execute("""
        SELECT
            q.far_part,
            COUNT(*) as total,
            SUM(a.was_correct) as correct
        FROM attempts a
        JOIN questions q ON a.question_id = q.id
        WHERE a.user_id = ?
        GROUP BY q.far_part""", (user_id,)).fetchall()

    # Recent stats: only attempts within last 30 days
    recent_rows = conn.execute("""
        SELECT
            q.far_part,
            COUNT(*) as total,
            SUM(a.was_correct) as correct
        FROM attempts a
        JOIN questions q ON a.question_id = q.id
        WHERE a.user_id = ?
            AND a.timestamp >= datetime('now', '-30 days')
        GROUP BY q.far_part""", (user_id,)).fetchall()

    conn.close()

    # Combine into one structure keyed by far_part
    stats_by_part = {}

    for row in lifetime_rows:
        stats_by_part[row["far_part"]] = {
            "far_part": row["far_part"],
            "lifetime_total": row["total"],
            "lifetime_correct": row["correct"],
            "lifetime_accuracy": round(100.0 * row["correct"] / row["total"], 1) if row["total"] else 0,
            "recent_total": 0,
            "recent_correct": 0,
            "recent_accuracy": None,
        }
    for row in recent_rows:
        if row["far_part"] in stats_by_part:
            stats_by_part[row["far_part"]]["recent_total"] = row["total"]
            stats_by_part[row["far_part"]]["recent_correct"] = row["correct"]
            stats_by_part[row["far_part"]]["recent_accuracy"] = (
                round(100.0 * row["correct"] / row["total"], 1) if row["total"] else None
            )
    # Sort weakest-first by lifetime accuracy
    return sorted(stats_by_part.values(), key=lambda s: s["lifetime_accuracy"])

def get_study_facts(far_part):
    """Fetch all study facts for a given FAR Part, in display order."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, far_part, topic, fact_type, content, key_takeaway, citation, display_order
        FROM study_facts
        WHERE far_part = ?
        ORDER BY display_order ASC, id ASC""", (far_part,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_far_parts_with_study_facts():
    """Return list of (far_part, count) tuples for Parts that have study facts."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT far_part, COUNT(*) as count
        FROM study_facts
        GROUP BY far_part
        ORDER BY far_part""").fetchall()
    conn.close()
    return [(row["far_part"], row["count"]) for row in rows]

if __name__ == "__main__":
    init_db()