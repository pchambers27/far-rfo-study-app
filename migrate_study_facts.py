import json
from database import get_connection

def migrate():
  """Read study_facts.json and load into the database, replacing existing data."""
  with open("study_facts.json") as f:
    facts = json.load(f)
  conn = get_connection()
  cursor = conn.cursor()

  cursor.execute("DELETE FROM study_facts")
  for fact in facts:
    cursor.execute("""
      INSERT INTO study_facts (far_part, topic, fact_type, content, key_takeaway, citation, display_order)
      VALUES (?, ?, ?, ?, ?, ?, ?)""", (
      fact["far_part"],
      fact["topic"],
      fact.get("fact_type"),
      fact["content"],
      fact.get("key_takeaway"),
      fact.get("citation"),
      fact.get("display_order", 0),
      ),
                  )
  conn.commit()
  conn.close()
  print(f"Migrated {len(facts)} study facts to the database.")

if __name__ == "__main__":
  migrate()