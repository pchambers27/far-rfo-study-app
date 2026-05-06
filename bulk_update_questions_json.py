import json

with open("questions.json") as f:
    questions = json.load(f)

updated = 0
removed_fillins = 0

new_questions = []
for q in questions:
    # Drop fill-ins
    if q.get("qtype") == "fill_in":
        removed_fillins += 1
        continue

    # Add difficulty if missing
    if "difficulty" not in q:
        q["difficulty"] = "foundational"

    # Add tags if missing — start with the FAR Part as a tag
    if "tags" not in q:
        q["tags"] = [q["far_part"]]

    # Remove old 'topic' field if it exists (no longer used)
    q.pop("topic", None)

    # Citation field stays as-is or gets added if you want
    new_questions.append(q)
    updated += 1

with open("questions.json", "w") as f:
    json.dump(new_questions, f, indent=4)

print(f"Updated {updated} questions, removed {removed_fillins} fill-ins.")