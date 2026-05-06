import json
from sqlalchemy import text
from database import engine


def migrate():
    """Read questions.json and upsert into the database."""
    with open("questions.json") as f:
        questions = json.load(f)

    skipped_fillins = 0
    inserted = 0
    updated = 0

    with engine.begin() as conn:
        for q in questions:
            # Reject fill-ins explicitly
            if q.get("qtype") == "fill_in":
                skipped_fillins += 1
                continue

            # Required fields
            if "difficulty" not in q:
                raise ValueError(f"Question {q.get('id')} missing required 'difficulty' field")
            if "tags" not in q or not isinstance(q["tags"], list):
                raise ValueError(f"Question {q.get('id')} missing or invalid 'tags' field (must be list)")
            if q["qtype"] in ("multiple_choice", "scenario") and not q.get("choices"):
                raise ValueError(f"Question {q.get('id')} of type '{q['qtype']}' missing required 'choices'")

            choices_json = json.dumps(q["choices"]) if q.get("choices") else None
            tags_json = json.dumps(q["tags"])

            result = conn.execute(
                text("""
                    INSERT INTO questions
                        (id, far_part, qtype, difficulty, tags, question, choices, answer, explanation, citation)
                    VALUES
                        (:id, :far_part, :qtype, :difficulty, CAST(:tags AS JSONB), :question, :choices, :answer, :explanation, :citation)
                    ON CONFLICT (id) DO UPDATE SET
                        far_part = EXCLUDED.far_part,
                        qtype = EXCLUDED.qtype,
                        difficulty = EXCLUDED.difficulty,
                        tags = EXCLUDED.tags,
                        question = EXCLUDED.question,
                        choices = EXCLUDED.choices,
                        answer = EXCLUDED.answer,
                        explanation = EXCLUDED.explanation,
                        citation = EXCLUDED.citation
                    RETURNING (xmax = 0) AS was_insert
                """),
                {
                    "id": q["id"],
                    "far_part": q["far_part"],
                    "qtype": q["qtype"],
                    "difficulty": q["difficulty"],
                    "tags": tags_json,
                    "question": q["question"],
                    "choices": choices_json,
                    "answer": q["answer"],
                    "explanation": q.get("explanation"),
                    "citation": q.get("citation"),
                },
            )
            was_insert = result.scalar()
            if was_insert:
                inserted += 1
            else:
                updated += 1

    print(f"Inserted: {inserted}, Updated: {updated}, Skipped (fill-ins): {skipped_fillins}")


if __name__ == "__main__":
    migrate()