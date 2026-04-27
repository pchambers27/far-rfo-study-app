
import json
# Initialize the running total

score = 0 

#Store questions and data in a list of dictionaires for easy looping
with open("questions.json") as f:
    quiz_data = json.load(f)


# Loop through the questions using a for loop

for item in quiz_data:
    # Ask question, take input
    user_response = input(f"\n{item['question']}\n> ")

    # Check if answer is correct
    if user_response.lower().strip() == item["answer"].lower():
        print("Correct!")
        score += 1

    else:
        print(f"Incorrect! (Correct answer is: {item['answer']})")

# 4. Print the final score at the end
print("-" * 30)
print(f"Quiz Complete! Your final score is: {score} out of {len(quiz_data)}")