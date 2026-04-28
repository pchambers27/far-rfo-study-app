import json
from database import get_connection

def migrate():
    """Read questions.json and insert each question into the database."""
    with open("questions.json") as f:
        questions = json.load(f)

    conn = get_connection()
    cursor = conn.cursor()

    for q in questions:
        choices_json = json.dumps(q.get("choices")) if q.get("choices") else  None

        cursor.execute(
          """INSERT INTO questions (far_part, topic, qtype, question, choices, answer, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)""",
          ( q["far_part"], 
            q["topic"], 
            q["qtype"], 
            q["question"], 
            choices_json, 
            q["answer"], 
            q["explanation"], ),
        )
    conn.commit()
    conn.close()
    print(f"Migrated {len(questions)} questions to the database.")

if __name__ == "__main__":
    migrate()