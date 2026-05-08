"""
Admin diagnostic script -- shows user activity, attempts, and content engagement.
Run with: python admin_stats.py
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from database import engine

def section(title):
  """Print s avisual section divider."""
  print("\n" + "=" * 60)
  print(f" {title}")
  print("=" * 60)

def show_user_summary():
  section("USERS")
  with engine.connect() as conn:
    total_users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
    print(f"\nTotal users: {total_users}")
    recent_signups = conn.execute(text("""SELECT COUNT(*) FROM users WHERE created_at >= :cutoff"""), {"cutoff": datetime.now(timezone.utc) - timedelta(days=7)}).scalar()
    print(f"New signups (last 7 days): {recent_signups}")

    rows = conn.execute(text("""
    SELECT u.email, u.create_at, COUNT(a.id) as attempt_count, MAX(a.timestamp) as last_attempt FROM users u LEFT JOIN attempts a ON a.user_id = u.id GROUP BY u.id, u.email, u.created_at ORDER BY last_attempt DESC NULLS LAST, u.created_at DESC""")).mappings().all()
    print (f"\n{'Email':<35} {'Signed Up':<12} {'Attempts':<10} {'Last seen':<20}")
    print("-" * 80)
    for row in rows:
      email = row["email"][:33]
      signup = row["created_at"].strftime("%Y-%m-%d") if row["create_at"] else "-"
      attempts = row["attempt_count"]
      last = row["last_attempt"].strftime("%Y-%m-%d %H:%M") if row["last_attempt"] else "Never"
      print(f"{email:<35} {signup:<12} {attempts:<10} {last:<20}")

def show_attempt_summary():
  section("ATTEMPTS")
  with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM attempts")).scalar()
    last_7 = conn.execute(text("SELECT COUNT(*) FROM attempts WHERE timestamp >= :cutoff"), {"cutoff": datetime.now(timezone.utc) - timedelta(days=7)}).scalar()
    last_30 = conn.execute(text("SELECT COUNT(*) FROM attempts WHERE timestamp >= :cutoff"), {"cutoff": datetime.now(timezone.utc) - timedelta(days=30)}).scalar()

    correct = conn.execute(text("SELECT SUM(was_correct) FROM attempts")).scalar() or 0
    accuracy = round(100.0 * correct / total, 1) if total else 0
    print(f"\nTotal attempts: {total}")
    print(f"Last 7 days: {last_7}")
    print(f"Last 30 days: {last_30}")
    print(f"Overall accuracy: {accuracy}%")

def show_part_engagement():
  section("ENGAGEMENT BY FAR PART")
  with engine.connect() as conn:
    rows = conn.execute(text("""
      SELECT q.far_part, COUNT(a.id) as attempts, SUM(a.was_correct) as correct, ROUND(100.0 * SUM(a.was_correct) / COUNT(a.id), 1) as accuracy FROM attempts a JOIN questions q ON a.question_id = q.id GROUP BY q.far_part ORDER BY attempts DESC""")).mappings().all()
    print(f"\n{'FAR Part':<10} {'Attempts':<10} {'Accuracy':<10}")
    print("-" * 35)
    for row in rows:
      print(f"{row['far_part']:<10} {row['attempts']:<10} {row['accuracy']}%")

def show_most_missed_questions():
  section("MOST-MISSED QUESTIONS(top 10)")
  with engine.connect() as conn:
    rows = conn.execute(text("""
    SELECT q.id, q.far_part, q.question, COUNT(a.id) as total_attempts, COUNT(a.id) - SUM(a.was_correct) as wrong_attempts, ROUND(100.0 * (COUNT(a.id) - SUM(a.was_correct)) / COUNT(a.id), 1) as miss_rate FROM attempts a JOIN questions q ON a.question_id = q.id GROUP BY q.id, q.far_part, q.question HAVING COUNT(a.id) >= 3 ORDER BY wrong_attempts DESC LIMIT 10""")).mappings().all()
    if not rows:
      print("\n(No questions with 3+ attempts yet)")
      return 
    for row in rows:
      preview = row["question"][:50] + "..." if len(row["question"]) > 80 else row["question"]
      print(f"\n[{row['far_part']}]Q{row['id']} - Missed {row['miss_rate']}%({row['wrong_attempts']}/{row['total_attempts']})")
      print(f" {preview}")

if __name__ == "__main__":
  print(f"\nRFO Ready Admin Stats -- {datetime.now().strftime('%Y-%m-%d %H:%M')}")
  show_user_summary()
  show_attempt_summary()
  show_part_engagement()
  show_most_missed_questions()
  print("\n")