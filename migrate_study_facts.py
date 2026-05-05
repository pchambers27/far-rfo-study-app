import json
from sqlalchemy import text
from database import engine


def migrate():
    """Read study_facts.json and load into the database, replacing existing data."""
    with open("study_facts.json") as f:
        facts = json.load(f)

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM study_facts"))

        for fact in facts:
            conn.execute(
                text("""
                    INSERT INTO study_facts
                        (far_part, topic, fact_type, content, key_takeaway, citation, display_order)
                    VALUES
                        (:far_part, :topic, :fact_type, :content, :key_takeaway, :citation, :display_order)
                """),
                {
                    "far_part": fact["far_part"],
                    "topic": fact["topic"],
                    "fact_type": fact.get("fact_type"),
                    "content": fact["content"],
                    "key_takeaway": fact.get("key_takeaway"),
                    "citation": fact.get("citation"),
                    "display_order": fact.get("display_order", 0),
                },
            )

    print(f"Migrated {len(facts)} study facts to the database.")


if __name__ == "__main__":
    migrate()