import json
import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

# Read DATABASE_URL from environment, fall back to local SQLite for dev
DATABASE_URL = os.environ.get("RENDER_DATABASE_URL") or os.environ.get("DATABASE_URL", "sqlite:///quiz.db")

# Render's Postgres URLs start with "postgres://" but SQLAlchemy 1.4+ requires "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create the engine. pool_pre_ping checks connections before using them
# (prevents "connection lost" errors after idle periods)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def get_connection():
    """Open a connection to the database."""
    return engine.connect()


def init_db():
    """Run schema.sql to create tables if they don't exist."""
    with open("schema.sql") as f:
        schema_sql = f.read()

    # Split by semicolons and execute each statement separately
    # (SQLAlchemy doesn't have an executescript equivalent)
    with engine.begin() as conn:
        for statement in schema_sql.split(";"):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
    print("Database initialized.")


def get_all_questions(far_parts=None, difficulty=None, tags=None):
    """
    Fetch questions, optionally filtered by FAR parts, difficulty, and/or tags.
    Returns list of dicts.
    """
    with get_connection() as conn:
        # Build the WHERE clause dynamically based on filters
        where_clauses = []
        params = {}

        if far_parts:
            placeholders = ",".join([f":fp{i}" for i in range(len(far_parts))])
            where_clauses.append(f"far_part IN ({placeholders})")
            for i, part in enumerate(far_parts):
                params[f"fp{i}"] = part

        if difficulty:
            where_clauses.append("difficulty = :difficulty")
            params["difficulty"] = difficulty

        if tags:
            # ANY tag in the list must be present in the question's tags
            tag_clauses = []
            for i, tag in enumerate(tags):
                tag_clauses.append(f"tags ? :tag{i}")
                params[f"tag{i}"] = tag
            where_clauses.append(f"({' OR '.join(tag_clauses)})")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = text(f"SELECT * FROM questions {where_sql} ORDER BY id")

        rows = conn.execute(query, params).mappings().all()

    questions = []
    for row in rows:
        questions.append({
            "id": row["id"],
            "far_part": row["far_part"],
            "qtype": row["qtype"],
            "difficulty": row["difficulty"],
            "tags": row["tags"] or [],
            "question": row["question"],
            "choices": json.loads(row["choices"]) if row["choices"] else None,
            "answer": row["answer"],
            "explanation": row["explanation"],
            "citation": row["citation"],
        })
    return questions


def create_user(email, password):
    """Create a new user. Returns the new user's id, or None if email is taken."""
    from werkzeug.security import generate_password_hash

    email = email.lower().strip()
    password_hash = generate_password_hash(password)

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("INSERT INTO users (email, password_hash) VALUES (:email, :password_hash) RETURNING id"),
                {"email": email, "password_hash": password_hash}
            )
            return result.scalar()
    except IntegrityError:
        return None


def get_user_by_email(email):
    """Look up the user by email. Returns the row as a dict, or None if not found."""
    email = email.lower().strip()
    with get_connection() as conn:
        row = conn.execute(
            text("SELECT * FROM users WHERE email = :email"),
            {"email": email}
        ).mappings().first()
    return dict(row) if row else None


def record_attempt(user_id, question_id, user_answer, was_correct):
    """Record one quiz attempt. Returns the new row's id."""
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO attempts (user_id, question_id, user_answer, was_correct)
                VALUES (:user_id, :question_id, :user_answer, :was_correct)
                RETURNING id
            """),
            {
                "user_id": user_id,
                "question_id": question_id,
                "user_answer": user_answer,
                "was_correct": 1 if was_correct else 0
            }
        )
        return result.scalar()


def get_far_parts():
    """Return a list of (far_part, count) tuples for all Parts in the database, sorted numerically."""
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT far_part, COUNT(*) as count
            FROM questions
            GROUP BY far_part
            ORDER BY CAST(REGEXP_REPLACE(far_part, '[^0-9]', '', 'g') AS INTEGER)
        """)).mappings().all()
    return [(row["far_part"], row["count"]) for row in rows]


def get_user_stats(user_id):
    """
    Return per-FAR-part stats for a user.
    Returns: list of dicts with far_part, lifetime stats, and recent stats.
    """
    cutoff = datetime.utcnow() - timedelta(days=30)

    with get_connection() as conn:
        # Lifetime stats per FAR Part
        lifetime_rows = conn.execute(text("""
            SELECT
                q.far_part,
                COUNT(*) as total,
                SUM(a.was_correct) as correct
            FROM attempts a
            JOIN questions q ON a.question_id = q.id
            WHERE a.user_id = :user_id
            GROUP BY q.far_part
        """), {"user_id": user_id}).mappings().all()

        # Recent stats: only attempts within the last 30 days
        recent_rows = conn.execute(text("""
            SELECT
                q.far_part,
                COUNT(*) as total,
                SUM(a.was_correct) as correct
            FROM attempts a
            JOIN questions q ON a.question_id = q.id
            WHERE a.user_id = :user_id
              AND a.timestamp >= :cutoff
            GROUP BY q.far_part
        """), {"user_id": user_id, "cutoff": cutoff}).mappings().all()

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


def get_study_facts(far_part=None, tags=None):
    """Fetch study facts, optionally filtered by FAR Part or tags."""
    with get_connection() as conn:
        where_clauses = []
        params = {}

        if far_part:
            where_clauses.append("far_part = :far_part")
            params["far_part"] = far_part

        if tags:
            tag_clauses = []
            for i, tag in enumerate(tags):
                tag_clauses.append(f"tags ? :tag{i}")
                params[f"tag{i}"] = tag
            where_clauses.append(f"({' OR '.join(tag_clauses)})")

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        query = text(f"""
            SELECT id, far_part, topic, content, key_takeaway, citation, display_order, tags, related_question_ids
            FROM study_facts
            {where_sql}
            ORDER BY display_order ASC, id ASC
        """)

        rows = conn.execute(query, params).mappings().all()
    return [dict(row) for row in rows]


def get_far_parts_with_study_facts():
    """Return list of (far_part, count) tuples for Parts that have study facts."""
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT far_part, COUNT(*) as count
            FROM study_facts
            GROUP BY far_part
            ORDER BY CAST(REGEXP_REPLACE(far_part, '[^0-9]', '', 'g') AS INTEGER)
        """)).mappings().all()
    return [(row["far_part"], row["count"]) for row in rows]

def load_tracks():
    """Load track definitions from tracks.json."""
    with open("tracks.json") as f:
        return json.load(f)


def get_active_tracks():
    """Return only tracks with status='active'."""
    return [t for t in load_tracks() if t.get("status") == "active"]


def get_track(track_id):
    """Return a single track by id, or None if not found or not active."""
    for track in load_tracks():
        if track["id"] == track_id and track.get("status") == "active":
            return track
    return None


def get_stage_stats(user_id, tags, difficulty=None):
    """
    Return aggregated stats for a user across questions matching the given tags
    (and optionally difficulty). Used per stage.
    Returns: dict with total_attempts, total_correct, accuracy.
    """
    if not tags:
        return {"total_attempts": 0, "total_correct": 0, "accuracy": None}

    # Build the SQL filter
    tag_clauses = []
    params = {"user_id": user_id}
    for i, tag in enumerate(tags):
        tag_clauses.append(f"q.tags ? :tag{i}")
        params[f"tag{i}"] = tag

    where_extra = ""
    if difficulty:
        where_extra = " AND q.difficulty = :difficulty"
        params["difficulty"] = difficulty

    query = text(f"""
        SELECT
            COUNT(*) as total,
            SUM(a.was_correct) as correct
        FROM attempts a
        JOIN questions q ON a.question_id = q.id
        WHERE a.user_id = :user_id
          AND ({' OR '.join(tag_clauses)})
          {where_extra}
    """)

    with get_connection() as conn:
        row = conn.execute(query, params).mappings().first()

    total = row["total"] or 0
    correct = row["correct"] or 0

    return {
        "total_attempts": total,
        "total_correct": correct,
        "accuracy": round(100.0 * correct / total, 1) if total else None,
    }

if __name__ == "__main__":
    init_db()