import json
from sqlalchemy import text
from database import engine


def migrate():
    """Read questions.json and insert each question into the database."""
    with open("questions.json") as f:
        questions = json.load(f)

    # engine.begin() opens a transaction — auto-commits on success, rolls back on error
    with engine.begin() as conn:
       
        conn.execute(text("DELETE FROM questions"))

        for q in questions:
            choices_json = json.dumps(q.get("choices")) if q.get("choices") else None

            conn.execute(
                text("""
                    INSERT INTO questions
                        (id, far_part, topic, qtype, question, choices, answer, explanation)
                    VALUES
                        (:id, :far_part, :topic, :qtype, :question, :choices, :answer, :explanation)
                """),
                {
                    "id": q["id"],
                    "far_part": q["far_part"],
                    "topic": q["topic"],
                    "qtype": q["qtype"],
                    "question": q["question"],
                    "choices": choices_json,
                    "answer": q["answer"],
                    "explanation": q["explanation"],
                },
            )

    print(f"Migrated {len(questions)} questions to the database.")


if __name__ == "__main__":
    migrate()