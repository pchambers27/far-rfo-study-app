"""
One-shot schema migration to the v2 architecture.

What this does:
1. Adds 'difficulty', 'tags', 'citation' to questions
2. Adds 'tags' to study_facts
3. Backfills defaults: existing questions become 'foundational', tagged with their FAR Part
4. Backfills study_fact tags with their FAR Part
5. Deletes fill-in questions and their attempts (cascading)
6. Drops the 'topic' column from questions
7. Drops the 'fact_type' column from study_facts
8. Sets NOT NULL constraints

All in a single transaction. If anything fails, rolls back.
"""
import json
from sqlalchemy import text
from database import engine


def migrate():
    with engine.begin() as conn:
        print("Adding new columns...")

        # Step 1: Add new columns (safe, additive)
        conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS difficulty TEXT"))
        conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS tags JSONB"))
        conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS citation TEXT"))
        conn.execute(text("ALTER TABLE study_facts ADD COLUMN IF NOT EXISTS tags JSONB"))

        print("Backfilling defaults...")

        # Step 2: Backfill difficulty
        conn.execute(text("""
            UPDATE questions
            SET difficulty = 'foundational'
            WHERE difficulty IS NULL
        """))

        # Step 3: Backfill tags from far_part for questions
        # Each question's tags becomes [<far_part>] as a starting point
        conn.execute(text("""
            UPDATE questions
            SET tags = jsonb_build_array(far_part)
            WHERE tags IS NULL
        """))

        # Step 4: Backfill tags from far_part for study_facts
        conn.execute(text("""
            UPDATE study_facts
            SET tags = jsonb_build_array(far_part)
            WHERE tags IS NULL
        """))

        print("Deleting fill-in questions...")

        # Step 5: Delete attempts referencing fill-in questions first (FK constraint)
        deleted_attempts = conn.execute(text("""
            DELETE FROM attempts
            WHERE question_id IN (SELECT id FROM questions WHERE qtype = 'fill_in')
        """)).rowcount

        # Then delete the fill-in questions themselves
        deleted_questions = conn.execute(text("""
            DELETE FROM questions WHERE qtype = 'fill_in'
        """)).rowcount

        print(f"  Deleted {deleted_questions} fill-in questions")
        print(f"  Deleted {deleted_attempts} attempt records on those questions")

        print("Dropping unused columns...")

        # Step 6: Drop columns we no longer need
        conn.execute(text("ALTER TABLE questions DROP COLUMN IF EXISTS topic"))
        conn.execute(text("ALTER TABLE study_facts DROP COLUMN IF EXISTS fact_type"))

        print("Setting NOT NULL constraints...")

        # Step 7: Add NOT NULL constraints
        conn.execute(text("ALTER TABLE questions ALTER COLUMN difficulty SET NOT NULL"))
        conn.execute(text("ALTER TABLE questions ALTER COLUMN tags SET NOT NULL"))
        conn.execute(text("ALTER TABLE study_facts ALTER COLUMN tags SET NOT NULL"))
        conn.execute(text("ALTER TABLE study_facts ALTER COLUMN key_takeaway SET NOT NULL"))

        print("Migration complete.")


if __name__ == "__main__":
    migrate()