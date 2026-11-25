import os
import json
import time
from pathlib import Path
from typing import List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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

# Enable CORS for React frontend (Vercel, localhost:5173, mobile, localhost:8000)
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

@app.get("/api/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "PulseTask FastAPI Backend",
        "runtime": "Python 3",
        "database": "Neon PostgreSQL"
    }

@app.get("/api/tasks", response_model=List[TaskResponse], tags=["Tasks"])
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

@app.post("/api/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED, tags=["Tasks"])
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

@app.put("/api/tasks/{task_id}", response_model=TaskResponse, tags=["Tasks"])
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

@app.delete("/api/tasks/{task_id}", tags=["Tasks"])
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

@app.delete("/api/tasks-clear/completed", tags=["Tasks"])
def clear_completed_tasks():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE status = 'completed';")
            count = cur.rowcount
            conn.commit()
            conn.close()
            return {"success": True, "deletedCount": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear completed tasks: {str(e)}")

# Serve React Frontend UI directly at root http://localhost:8000
frontend_html = Path(__file__).resolve().parent.parent / "index.html"

@app.get("/", include_in_schema=False)
def serve_index():
    if frontend_html.exists():
        return FileResponse(frontend_html)
    return {"message": "PulseTask React UI file not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
