CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS questions (
  id SERIAL PRIMARY KEY,
  far_part TEXT NOT NULL,
  topic TEXT NOT NULL,
  qtype TEXT NOT NULL,
  question TEXT NOT NULL,
  choices TEXT,
  answer TEXT NOT NULL,
  explanation TEXT
);

CREATE TABLE IF NOT EXISTS attempts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  question_id INTEGER NOT NULL,
  user_answer TEXT,
  was_correct INTEGER NOT NULL,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (question_id) REFERENCES questions(id)
);

CREATE TABLE IF NOT EXISTS study_facts (
  id SERIAL PRIMARY KEY,
  far_part TEXT NOT NULL,
  topic TEXT NOT NULL,
  fact_type TEXT,
  content TEXT NOT NULL,
  key_takeaway TEXT,
  citation TEXT,
  display_order INTEGER DEFAULT 0
);