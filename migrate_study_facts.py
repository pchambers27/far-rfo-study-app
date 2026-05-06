import json
from sqlalchemy import text
from database import engine


def migrate():
    """Read study_facts.json and upsert into the database."""
    with open("study_facts.json") as f:
        facts = json.load(f)

    inserted = 0

    with engine.begin() as conn:
        # Wipe and reload — study_facts have no FK references
        conn.execute(text("DELETE FROM study_facts"))

        for fact in facts:
            # Required fields
            if "key_takeaway" not in fact or not fact["key_takeaway"]:
                raise ValueError(f"Study fact about '{fact.get('topic')}' missing required 'key_takeaway'")
            if "tags" not in fact or not isinstance(fact["tags"], list):
                raise ValueError(f"Study fact about '{fact.get('topic')}' missing or invalid 'tags' field")

            # Optional but expected: related_question_ids defaults to empty list
            related_ids = fact.get("related_question_ids", [])
            if not isinstance(related_ids, list):
                raise ValueError(f"Study fact about '{fact.get('topic')}' has invalid 'related_question_ids' (must be list)")

            tags_json = json.dumps(fact["tags"])
            related_json = json.dumps(related_ids)

            conn.execute(
                text("""
                    INSERT INTO study_facts
                        (far_part, topic, content, key_takeaway, citation, display_order, tags, related_question_ids)
                    VALUES
                        (:far_part, :topic, :content, :key_takeaway, :citation, :display_order, CAST(:tags AS JSONB), CAST(:related AS JSONB))
                """),
                {
                    "far_part": fact["far_part"],
                    "topic": fact["topic"],
                    "content": fact["content"],
                    "key_takeaway": fact["key_takeaway"],
                    "citation": fact.get("citation"),
                    "display_order": fact.get("display_order", 0),
                    "tags": tags_json,
                    "related": related_json,
                },
            )
            inserted += 1

    print(f"Migrated {inserted} study facts.")


if __name__ == "__main__":
    migrate()