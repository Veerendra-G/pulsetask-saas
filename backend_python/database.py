import os
from pathlib import Path
import psycopg2
from dotenv import load_dotenv

# Explicitly load .env from current directory or parent directory
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Connect to Neon Serverless PostgreSQL with SSL require"""
    url = os.getenv("DATABASE_URL") or DATABASE_URL
    if not url:
        raise RuntimeError("DATABASE_URL is not set in environment or .env")
    return psycopg2.connect(url, sslmode="require")

def init_db():
    """Auto-create tables if not existing in Neon PostgreSQL"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(64) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    status VARCHAR(32) NOT NULL DEFAULT 'todo',
                    priority VARCHAR(16) NOT NULL DEFAULT 'medium',
                    project VARCHAR(64) NOT NULL DEFAULT 'Engineering',
                    due_date VARCHAR(32),
                    tags JSONB DEFAULT '[]'::jsonb,
                    user_id VARCHAR(64),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS user_id VARCHAR(64);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);")
        conn.commit()
        conn.close()
        print(" Connected to Neon PostgreSQL & verified tables (users, tasks)!")
    except Exception as e:
        print(f" Warning: Could not initialize Neon database: {e}")
