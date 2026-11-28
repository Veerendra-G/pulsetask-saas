import os
import re
import json
import time
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, APIRouter, HTTPException, status, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from psycopg2.extras import RealDictCursor

from database import get_db_connection, init_db
from models import (
    TaskCreate, TaskUpdate, TaskResponse,
    UserRegister, UserLogin, ForgotPasswordRequest, ResetPasswordRequest, GoogleAuthRequest, SocialAuthRequest, UserResponse, AuthResponse,
    AIParseTaskRequest, AIParseTaskResponse
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user_optional, get_current_user_required
)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

def validate_email_format(email: str) -> str:
    if not email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format. Please provide a complete email address (e.g. name@gmail.com)."
        )
    domain_part = cleaned.split("@")[1]
    if "." not in domain_part or len(domain_part.split(".")[-1]) < 2:
        raise HTTPException(
            status_code=400,
            detail="Invalid email domain. Please enter a valid email address with a domain extension (e.g. name@gmail.com)."
        )
    return cleaned

app = FastAPI(
    title="PulseTask FastAPI Backend",
    description="Enterprise Python FastAPI SaaS backend connected to Neon Serverless PostgreSQL with JWT Authentication",
    version="2.0.0",
    docs_url=None,   # We define explicit handlers below for /docs and /api/docs
    redoc_url=None,
    openapi_url=None
)

# Enable CORS for React frontend (Vercel, localhost, mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# --- Interactive Swagger Docs & OpenAPI Endpoints (support both /docs and /api/docs) ---
@app.get("/openapi.json", include_in_schema=False)
@app.get("/api/openapi.json", include_in_schema=False)
def get_open_api_endpoint():
    return JSONResponse(app.openapi())

@app.get("/docs", include_in_schema=False)
@app.get("/api/docs", include_in_schema=False)
def swagger_ui():
    return get_swagger_ui_html(openapi_url="/api/openapi.json", title="PulseTask API Docs")

@app.get("/redoc", include_in_schema=False)
@app.get("/api/redoc", include_in_schema=False)
def redoc_ui():
    return get_redoc_html(openapi_url="/api/openapi.json", title="PulseTask API ReDoc")

# Create API Router to support both /api/... and direct /... calls
router = APIRouter()

@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "PulseTask FastAPI Backend",
        "version": "2.0.0",
        "runtime": "Python 3.12",
        "database": "Neon PostgreSQL",
        "auth": "JWT + bcrypt enabled"
    }

# ==========================================
# --- Authentication Endpoints ---
# ==========================================

@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register(user_data: UserRegister):
    email = validate_email_format(user_data.email)
    if len(user_data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user_id = f"user-{int(time.time() * 1000)}"
    hashed = hash_password(user_data.password)
    name = (user_data.name or email.split("@")[0]).strip()

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if email already exists
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            if cur.fetchone():
                conn.close()
                raise HTTPException(status_code=400, detail="This email is already registered. Please sign in.")

            cur.execute("""
                INSERT INTO users (id, email, password_hash, name)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, name, created_at;
            """, (user_id, email, hashed, name))
            user_row = cur.fetchone()
            conn.commit()
            conn.close()

            token = create_access_token(user_id=user_row["id"], email=user_row["email"], name=user_row["name"])
            return {
                "token": token,
                "token_type": "bearer",
                "user": {
                    "id": user_row["id"],
                    "email": user_row["email"],
                    "name": user_row["name"] or "",
                    "createdAt": user_row["created_at"]
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@router.post("/auth/login", response_model=AuthResponse, tags=["Authentication"])
def login(creds: UserLogin):
    email = validate_email_format(creds.email)
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            user_row = cur.fetchone()
            conn.close()

            if not user_row or not verify_password(creds.password, user_row["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid email or password.")

            token = create_access_token(user_id=user_row["id"], email=user_row["email"], name=user_row["name"])
            return {
                "token": token,
                "token_type": "bearer",
                "user": {
                    "id": user_row["id"],
                    "email": user_row["email"],
                    "name": user_row["name"] or "",
                    "createdAt": user_row["created_at"]
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

@router.post("/auth/forgot-password", tags=["Authentication"])
def forgot_password(payload: ForgotPasswordRequest):
    email = validate_email_format(payload.email)
    
    # Check if user exists in database
    user_row = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, email, name FROM users WHERE email = %s;", (email,))
            user_row = cur.fetchone()
        conn.close()
    except Exception as e:
        print(f"Warning during forgot password verification: {e}")

    if not user_row:
        raise HTTPException(status_code=404, detail="No registered account found with this email.")

    return {
        "success": True,
        "email": email,
        "message": f"Account verified for {email}. Please set your new password below."
    }

@router.post("/auth/reset-password", tags=["Authentication"])
def reset_password(payload: ResetPasswordRequest):
    email = validate_email_format(payload.email)
    new_pwd = payload.new_password
    if not new_pwd or len(new_pwd) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    
    new_hash = hash_password(new_pwd)
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
            user = cur.fetchone()
            if not user:
                conn.close()
                raise HTTPException(status_code=404, detail="No account found with this email address.")
            
            cur.execute("UPDATE users SET password_hash = %s WHERE email = %s;", (new_hash, email))
            conn.commit()
        conn.close()
        return {"success": True, "message": "Password updated successfully! You can now sign in with your new password."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset password: {str(e)}")

@router.post("/auth/social", response_model=AuthResponse, tags=["Authentication"])
def social_auth(payload: SocialAuthRequest):
    provider = (payload.provider or "google").strip().lower()
    email = (payload.email or "").strip().lower()
    name = (payload.name or "").strip()
    picture = payload.picture

    # If Google credential JWT is provided from GIS client, decode payload safely
    if payload.credential and provider == "google":
        try:
            import base64
            parts = payload.credential.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                decoded_bytes = base64.urlsafe_b64decode(payload_b64)
                token_info = json.loads(decoded_bytes.decode("utf-8"))
                email = token_info.get("email", email).strip().lower()
                name = token_info.get("name", token_info.get("given_name", name)).strip()
                picture = token_info.get("picture", picture)
        except Exception as e:
            print(f"Warning decoding Google credential: {e}")

    # Strictly validate email format (never auto-append or allow invalid email like test@gmail)
    email = validate_email_format(email)

    if not name:
        name = email.split("@")[0].replace(".", " ").replace("_", " ").title()

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if user already exists
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            user_row = cur.fetchone()

            if not user_row:
                user_id = f"user-{provider}-{int(time.time() * 1000)}"
                dummy_hash = f"{provider}_oauth_{int(time.time())}"
                cur.execute("""
                    INSERT INTO users (id, email, password_hash, name, avatar_url, provider)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, email, name, avatar_url, provider, created_at;
                """, (user_id, email, dummy_hash, name, picture, provider))
                user_row = cur.fetchone()
                conn.commit()
            else:
                if picture and not user_row.get("avatar_url"):
                    try:
                        cur.execute("UPDATE users SET avatar_url = %s, provider = %s WHERE id = %s;", (picture, provider, user_row["id"]))
                        conn.commit()
                    except Exception:
                        pass

            conn.close()

            token = create_access_token(user_id=user_row["id"], email=user_row["email"], name=user_row["name"])
            return {
                "token": token,
                "token_type": "bearer",
                "user": {
                    "id": user_row["id"],
                    "email": user_row["email"],
                    "name": user_row["name"] or "",
                    "avatarUrl": picture or user_row.get("avatar_url"),
                    "provider": user_row.get("provider") or provider,
                    "createdAt": user_row.get("created_at")
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{provider.capitalize()} sign in failed: {str(e)}")

@router.post("/auth/google", response_model=AuthResponse, tags=["Authentication"])
def google_auth(payload: GoogleAuthRequest):
    email = (payload.email or "").strip().lower()
    name = (payload.name or "").strip()
    picture = payload.picture

    # If Google credential JWT is provided from GIS client, decode payload safely
    if payload.credential:
        try:
            import base64
            parts = payload.credential.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                payload_b64 += "=" * (-len(payload_b64) % 4)
                decoded_bytes = base64.urlsafe_b64decode(payload_b64)
                token_info = json.loads(decoded_bytes.decode("utf-8"))
                email = token_info.get("email", email).strip().lower()
                name = token_info.get("name", token_info.get("given_name", name)).strip()
                picture = token_info.get("picture", picture)
        except Exception as e:
            print(f"Warning decoding Google credential: {e}")

    email = validate_email_format(email)

    if not name:
        name = email.split("@")[0].capitalize()

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if user already exists
            cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
            user_row = cur.fetchone()

            if not user_row:
                # Auto-register new Google user
                user_id = f"user-google-{int(time.time() * 1000)}"
                dummy_hash = f"google_oauth_{int(time.time())}"
                cur.execute("""
                    INSERT INTO users (id, email, password_hash, name, avatar_url, provider)
                    VALUES (%s, %s, %s, %s, %s, 'google')
                    RETURNING id, email, name, avatar_url, provider, created_at;
                """, (user_id, email, dummy_hash, name, picture))
                user_row = cur.fetchone()
                conn.commit()
            else:
                if picture and not user_row.get("avatar_url"):
                    try:
                        cur.execute("UPDATE users SET avatar_url = %s WHERE id = %s;", (picture, user_row["id"]))
                        conn.commit()
                    except Exception:
                        pass

            conn.close()

            token = create_access_token(user_id=user_row["id"], email=user_row["email"], name=user_row["name"])
            return {
                "token": token,
                "token_type": "bearer",
                "user": {
                    "id": user_row["id"],
                    "email": user_row["email"],
                    "name": user_row["name"] or "",
                    "avatarUrl": picture or user_row.get("avatar_url"),
                    "provider": user_row.get("provider") or "google",
                    "createdAt": user_row.get("created_at")
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Google sign in failed: {str(e)}")

@router.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
def get_current_user_profile(current_user: dict = Depends(get_current_user_required)):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, email, name, avatar_url, provider, created_at FROM users WHERE id = %s;", (current_user["id"],))
            user_row = cur.fetchone()
            conn.close()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")
            return {
                "id": user_row["id"],
                "email": user_row["email"],
                "name": user_row["name"] or "",
                "avatarUrl": user_row.get("avatar_url"),
                "provider": user_row.get("provider") or "local",
                "createdAt": user_row["created_at"]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")

# ==========================================
# --- Task CRUD Endpoints ---
# ==========================================

@router.get("/tasks", response_model=List[TaskResponse], tags=["Tasks"])
def get_tasks(current_user: Optional[dict] = Depends(get_current_user_optional)):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if current_user:
                # Logged in: Return ONLY this user's private tasks (strictly isolated)
                cur.execute("""
                    SELECT * FROM tasks 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC;
                """, (current_user["id"],))
            else:
                # Guest mode: return demo/shared tasks
                cur.execute("SELECT * FROM tasks WHERE user_id IS NULL ORDER BY created_at DESC;")

            rows = cur.fetchall()
            tasks = []
            for row in rows:
                tasks.append({
                    "id": row["id"],
                    "title": row["title"],
                    "description": row.get("description") or "",
                    "status": row.get("status") or "todo",
                    "priority": row.get("priority") or "medium",
                    "project": row.get("project") or "Engineering",
                    "dueDate": row.get("due_date"),
                    "tags": row.get("tags") or [],
                    "userId": row.get("user_id"),
                    "createdAt": row.get("created_at")
                })
            conn.close()
            return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tasks: {str(e)}")

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
def create_task(task: TaskCreate, current_user: Optional[dict] = Depends(get_current_user_optional)):
    task_id = task.id or f"task-{int(time.time() * 1000)}"
    user_id = current_user["id"] if current_user else None

    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO tasks (id, title, description, status, priority, project, due_date, tags, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """, (
                task_id,
                task.title,
                task.description or "",
                task.status or "todo",
                task.priority or "medium",
                task.project or "Engineering",
                task.dueDate,
                json.dumps(task.tags or []),
                user_id
            ))
            row = cur.fetchone()
            conn.commit()
            conn.close()
            return {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"] or "",
                "status": row["status"] or "todo",
                "priority": row["priority"] or "medium",
                "project": row["project"] or "Engineering",
                "dueDate": row["due_date"],
                "tags": row["tags"] or [],
                "userId": row.get("user_id"),
                "createdAt": row["created_at"]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.put("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
def update_task(task_id: str, task: TaskUpdate, current_user: Optional[dict] = Depends(get_current_user_optional)):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s;", (task_id,))
            existing = cur.fetchone()
            if not existing:
                conn.close()
                raise HTTPException(status_code=404, detail="Task not found")

            title = task.title if task.title is not None else existing["title"]
            description = task.description if task.description is not None else existing["description"]
            status_val = task.status if task.status is not None else existing["status"]
            priority = task.priority if task.priority is not None else existing["priority"]
            project = task.project if task.project is not None else existing["project"]
            due_date = task.dueDate if task.dueDate is not None else existing["due_date"]
            tags = json.dumps(task.tags) if task.tags is not None else json.dumps(existing["tags"] or [])

            cur.execute("""
                UPDATE tasks
                SET title = %s, description = %s, status = %s, priority = %s, project = %s, due_date = %s, tags = %s
                WHERE id = %s
                RETURNING *;
            """, (title, description, status_val, priority, project, due_date, tags, task_id))
            row = cur.fetchone()
            conn.commit()
            conn.close()
            return {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"] or "",
                "status": row["status"] or "todo",
                "priority": row["priority"] or "medium",
                "project": row["project"] or "Engineering",
                "dueDate": row["due_date"],
                "tags": row["tags"] or [],
                "userId": row.get("user_id"),
                "createdAt": row["created_at"]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")

@router.delete("/tasks/{task_id}", tags=["Tasks"])
def delete_task(task_id: str, current_user: Optional[dict] = Depends(get_current_user_optional)):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s RETURNING id;", (task_id,))
            deleted = cur.fetchone()
            if not deleted:
                conn.close()
                raise HTTPException(status_code=404, detail="Task not found")
            conn.commit()
            conn.close()
            return {"success": True, "message": f"Task {task_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")

@router.delete("/tasks-clear/completed", tags=["Tasks"])
def clear_completed_tasks(current_user: Optional[dict] = Depends(get_current_user_optional)):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if current_user:
                cur.execute("DELETE FROM tasks WHERE status = 'completed' AND user_id = %s;", (current_user["id"],))
            else:
                cur.execute("DELETE FROM tasks WHERE status = 'completed' AND user_id IS NULL;")
            count = cur.rowcount
            conn.commit()
            conn.close()
            return {"success": True, "deletedCount": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear completed tasks: {str(e)}")

# --- AI Task Parser & Categorization (Gemini & Smart Heuristic) ---
def heuristic_parse_task(text: str, current_date_str: Optional[str] = None, existing_projects: Optional[List[str]] = None) -> dict:
    from datetime import datetime, timedelta

    today = datetime.now()
    if current_date_str:
        try:
            today = datetime.strptime(current_date_str, "%Y-%m-%d")
        except Exception:
            pass

    clean_text = text.strip()
    lower_text = clean_text.lower()

    # 1. Detect Priority
    priority = "medium"
    if any(w in lower_text for w in ["urgent", "asap", "emergency", "critical", "highest priority", "p0"]):
        priority = "urgent"
    elif any(w in lower_text for w in ["high priority", "important", "high", "crucial", "p1"]):
        priority = "high"
    elif any(w in lower_text for w in ["low priority", "low", "someday", "minor", "trivial", "when you can", "p3"]):
        priority = "low"

    # 2. Detect Due Date
    due_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if "today" in lower_text or "tonight" in lower_text:
        due_date = today.strftime("%Y-%m-%d")
    elif "tomorrow" in lower_text:
        due_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "day after tomorrow" in lower_text:
        due_date = (today + timedelta(days=2)).strftime("%Y-%m-%d")
    elif "next week" in lower_text:
        due_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        matched_day = False
        for idx, day in enumerate(weekdays):
            if f"next {day}" in lower_text or f"by {day}" in lower_text or f"on {day}" in lower_text or f"this {day}" in lower_text:
                days_ahead = idx - today.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                if f"next {day}" in lower_text:
                    days_ahead += 7
                due_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                matched_day = True
                break
        if not matched_day:
            in_days_match = re.search(r"in\s+(\d+)\s+days?", lower_text)
            if in_days_match:
                days = int(in_days_match.group(1))
                due_date = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    # 3. Detect Project / Category
    project = "Engineering"
    projects_list = [p for p in (existing_projects or []) if p and p != "All Projects"]
    if not projects_list:
        projects_list = ["Engineering", "Design", "Marketing", "Security", "Executive", "Personal"]

    matched_explicit = False
    for p in projects_list:
        pattern = rf"\b(?:project|category|under|for|in)\s+{re.escape(p.lower())}\b"
        if re.search(pattern, lower_text):
            project = p
            matched_explicit = True
            break

    if not matched_explicit:
        category_keywords = {
            "Design": ["ui", "ux", "figma", "design", "prototype", "wireframe", "logo", "sketch", "mockup", "colors", "styling", "layout", "banner", "graphics"],
            "Marketing": ["marketing", "campaign", "seo", "blog", "twitter", "ads", "social", "email", "newsletter", "launch", "content", "promot", "sales", "outreach"],
            "Security": ["security", "audit", "vuln", "cve", "auth", "token", "ssl", "cert", "firewall", "encrypt", "compliance", "permission", "patch"],
            "Executive": ["meeting", "investor", "board", "budget", "finance", "strategy", "roadmap", "hire", "quarterly", "q4", "contract", "legal", "revenue"],
            "Personal": ["buy", "grocery", "doctor", "health", "workout", "gym", "medicine", "home", "dinner", "family", "car", "cleaning", "shopping", "gift"],
            "Engineering": ["code", "deploy", "bug", "fix", "api", "backend", "frontend", "server", "database", "redis", "postgres", "aws", "docker", "test", "ci", "git", "endpoint", "infrastructure", "release"]
        }
        scores = {}
        for cat, keywords in category_keywords.items():
            scores[cat] = sum(1 for kw in keywords if re.search(rf"\b{kw}", lower_text))

        best_cat = max(scores, key=scores.get)
        if scores[best_cat] > 0:
            for p in projects_list:
                if p.lower() == best_cat.lower():
                    project = p
                    break
            else:
                project = best_cat

    # 4. Clean Title
    title = clean_text
    leading_patterns = [
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:add\s+(?:a\s+)?task\s+(?:to\s+)?|create\s+(?:a\s+)?task\s+(?:to\s+)?|schedule\s+(?:a\s+)?task\s+(?:to\s+)?|i\s+need\s+to\s+|remind\s+me\s+to\s+|make\s+a\s+task\s+to\s+|put\s+down\s+)",
        r"^(?:new\s+task\s*:?\s*|task\s*:?\s*|voice\s+task\s*:?\s*)"
    ]
    for lp in leading_patterns:
        title = re.sub(lp, "", title, flags=re.IGNORECASE).strip()

    trailing_patterns = [
        r"(?:\s+(?:by|due|on)?\s*(?:tomorrow|today|tonight|next\s+[a-z]+|this\s+[a-z]+|in\s+\d+\s+days?))",
        r"(?:\s+(?:for|in|under)?\s*(?:project|category)?\s*(?:engineering|design|marketing|security|executive|personal))",
        r"(?:\s+(?:with\s+)?(?:urgent|high|medium|low)\s+priority)",
        r"(?:\s+(?:priority\s+(?:urgent|high|medium|low)|asap|urgent|p0|p1|p2))",
        r"(?:\s+(?:project|category)\b)"
    ]
    for tp in trailing_patterns:
        title = re.sub(tp, "", title, flags=re.IGNORECASE).strip()

    title = title.strip(" .,-!?;:")
    if not title:
        title = clean_text[:60]
    title = title[0].upper() + title[1:] if len(title) > 1 else title.upper()

    tags = []
    if project and project != "Engineering":
        tags.append(project.lower())
    words = [w.strip(" .,;!?") for w in lower_text.split() if len(w) > 3]
    stop_words = {"this", "that", "with", "from", "have", "make", "task", "need", "please", "tomorrow", "today", "project", "priority"}
    potential_tags = [w for w in words if w not in stop_words and w.isalpha()]
    for pt in potential_tags[:2]:
        if pt not in tags:
            tags.append(pt)

    return {
        "title": title,
        "description": f"Captured via voice mode on {today.strftime('%b %d, %Y')}.",
        "project": project,
        "priority": priority,
        "dueDate": due_date,
        "tags": tags[:3],
        "source": "heuristic"
    }

def call_gemini_parse_task(text: str, api_key: str, current_date_str: Optional[str] = None, existing_projects: Optional[List[str]] = None) -> Optional[dict]:
    import urllib.request
    from datetime import datetime

    current_date = current_date_str or datetime.now().strftime("%Y-%m-%d")
    projects_str = ", ".join([p for p in (existing_projects or []) if p and p != "All Projects"] or ["Engineering", "Design", "Marketing", "Security", "Executive", "Personal"])

    prompt = f"""You are an expert AI task manager assistant for PulseTask SaaS.
The current date is {current_date}.
The existing projects/categories in the workspace are: [{projects_str}].
Available priorities are: "urgent", "high", "medium", "low".

Analyze the following voice command or task transcription and output a clean JSON object:
Input: "{text}"

JSON schema required:
{{
  "title": "Concise, imperative task title (remove filler words like 'remind me to', 'please add a task to', 'with priority high', etc.)",
  "description": "Additional context or notes if mentioned (or empty string)",
  "project": "Best matching category from existing projects or standard categories (e.g. Engineering, Design, Marketing, Security, Executive, Personal)",
  "priority": "urgent" | "high" | "medium" | "low",
  "dueDate": "YYYY-MM-DD (calculated relative to {current_date}, e.g. tomorrow, next Monday, etc.)",
  "tags": ["1-3 relevant lowercase tags"]
}}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates", [])
            if candidates:
                raw_json = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                result = json.loads(raw_json)
                result["source"] = "gemini"
                return result
    except Exception as e:
        print(f"Gemini API call notice: {e}")
        return None

@router.post("/ai/parse-task", response_model=AIParseTaskResponse, tags=["AI"])
def ai_parse_task(payload: AIParseTaskRequest):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Voice transcript or task text is required.")

    api_key = payload.apiKey or os.environ.get("GEMINI_API_KEY")
    result = None
    if api_key:
        result = call_gemini_parse_task(
            text=text,
            api_key=api_key,
            current_date_str=payload.currentDate,
            existing_projects=payload.existingProjects
        )

    if not result:
        result = heuristic_parse_task(
            text=text,
            current_date_str=payload.currentDate,
            existing_projects=payload.existingProjects
        )

    return AIParseTaskResponse(**result)

# Mount the router on both /api and root so /api/tasks and /tasks both work
app.include_router(router, prefix="/api")
app.include_router(router, prefix="")

# Locate the React frontend HTML file
def get_frontend_html():
    candidates = [
        Path(__file__).resolve().parent / "index.html",
        Path(__file__).resolve().parent.parent / "index.html",
        Path("/var/task/index.html"),
        Path("/var/task/backend_python/index.html")
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

@app.get("/", include_in_schema=False)
def serve_index():
    html_path = get_frontend_html()
    if html_path:
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>PulseTask React SaaS - Loading...</h1>")

@app.get("/{full_path:path}", include_in_schema=False)
def serve_spa(full_path: str):
    if full_path in ("docs", "redoc", "openapi.json") or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    html_path = get_frontend_html()
    if html_path:
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>PulseTask React SaaS - Loading...</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
