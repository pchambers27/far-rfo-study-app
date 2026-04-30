from database import create_user, get_user_by_email

# Create a test user
user_id = create_user("test@example.com", "password123")
print(f"Created user with id: {user_id}")

# Try to create a user with the same email -- should fail
duplicate = create_user("test@example.com", "AnotherPassword")
print(f"Duplicate attempt: {duplicate}")

# Look the user up
user = get_user_by_email("test@example.com")
print(f"Found user: id={user['id']}, email={user['email']}")
print(f"Password hash starts with: {user['password_hash'][:30]}...")