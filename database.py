import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Connect to Neon Serverless PostgreSQL with SSL require"""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in environment or .env")
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    """Auto-create tasks table if not existing in Neon PostgreSQL"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
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
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
        conn.close()
        print(" Connected to Neon PostgreSQL & verified tasks table!")
    except Exception as e:
        print(f" Warning: Could not initialize Neon database: {e}")
