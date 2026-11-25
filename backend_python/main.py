import os
import json
import time
from pathlib import Path
from typing import List
from fastapi import FastAPI, APIRouter, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg2.extras import RealDictCursor

from database import get_db_connection, init_db
from models import TaskCreate, TaskUpdate, TaskResponse

app = FastAPI(
    title="PulseTask FastAPI Backend",
    description="High-performance Python FastAPI REST API connected to Neon Serverless PostgreSQL",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for React frontend (Vercel, localhost, mobile)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Vercel Serverless Routing Middleware
@app.middleware("http")
async def vercel_routing_middleware(request: Request, call_next):
    matched_path = request.headers.get("x-matched-path")
    if matched_path:
        request.scope["path"] = matched_path
    return await call_next(request)

@app.on_event("startup")
def on_startup():
    init_db()

# Create API Router to support both /api/... and direct /... calls
router = APIRouter()

@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "PulseTask FastAPI Backend",
        "runtime": "Python 3.12",
        "database": "Neon PostgreSQL"
    }

@router.get("/tasks", response_model=List[TaskResponse], tags=["Tasks"])
def get_tasks():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM tasks ORDER BY created_at DESC;")
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
                    "createdAt": row.get("created_at")
                })
            conn.close()
            return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch tasks: {str(e)}")

@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
def create_task(task: TaskCreate):
    task_id = task.id or f"task-{int(time.time() * 1000)}"
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO tasks (id, title, description, status, priority, project, due_date, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
            """, (
                task_id,
                task.title,
                task.description or "",
                task.status or "todo",
                task.priority or "medium",
                task.project or "Engineering",
                task.dueDate,
                json.dumps(task.tags or [])
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
                "createdAt": row["created_at"]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")

@router.put("/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
def update_task(task_id: str, task: TaskUpdate):
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
                "createdAt": row["created_at"]
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")

@router.delete("/tasks/{task_id}", tags=["Tasks"])
def delete_task(task_id: str):
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
def clear_completed_tasks():
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("DELETE FROM tasks WHERE status = 'completed';")
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
