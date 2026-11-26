import os
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
    UserRegister, UserLogin, ForgotPasswordRequest, ResetPasswordRequest, GoogleAuthRequest, SocialAuthRequest, UserResponse, AuthResponse
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user_optional, get_current_user_required
)

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
    email = user_data.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
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
    email = creds.email.strip().lower()
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
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required.")
    
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
    email = payload.email.strip().lower()
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

    # Normalize email (handle test@gmail -> test@gmail.com)
    if email.endswith("@gmail"):
        email = email + ".com"

    # Require valid email for social authentication (never hardcoded to any user)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email address is required for social authentication.")

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

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid Google authentication: valid email is required.")

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
