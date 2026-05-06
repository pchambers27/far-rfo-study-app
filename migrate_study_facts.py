import json
from sqlalchemy import text
from database import engine


def migrate():
    """Read study_facts.json and upsert into the database."""
    with open("study_facts.json") as f:
        facts = json.load(f)

    inserted = 0

    with engine.begin() as conn:
        # For now, simple wipe-and-reload since study facts don't have FK references
        conn.execute(text("DELETE FROM study_facts"))

        for fact in facts:
            if "key_takeaway" not in fact or not fact["key_takeaway"]:
                raise ValueError(f"Study fact about '{fact.get('topic')}' missing required 'key_takeaway'")
            if "tags" not in fact or not isinstance(fact["tags"], list):
                raise ValueError(f"Study fact about '{fact.get('topic')}' missing or invalid 'tags' field")

            tags_json = json.dumps(fact["tags"])

            conn.execute(
                text("""
                    INSERT INTO study_facts
                        (far_part, topic, content, key_takeaway, citation, display_order, tags)
                    VALUES
                        (:far_part, :topic, :content, :key_takeaway, :citation, :display_order, CAST(:tags AS JSONB))
                """),
                {
                    "far_part": fact["far_part"],
                    "topic": fact["topic"],
                    "content": fact["content"],
                    "key_takeaway": fact["key_takeaway"],
                    "citation": fact.get("citation"),
                    "display_order": fact.get("display_order", 0),
                    "tags": tags_json,
                },
            )
            inserted += 1

    print(f"Migrated {inserted} study facts.")


if __name__ == "__main__":
    migrate()