import json

with open("study_facts.json") as f:
    facts = json.load(f)

for f_dict in facts:
    if "tags" not in f_dict:
        f_dict["tags"] = [f_dict["far_part"]]
    # Drop old fact_type if present
    f_dict.pop("fact_type", None)

with open("study_facts.json", "w") as out:
    json.dump(facts, out, indent=4)

print(f"Updated {len(facts)} study facts.")