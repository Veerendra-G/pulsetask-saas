from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Title of the task")
    description: Optional[str] = Field(default="", description="Detailed task description")
    status: Optional[str] = Field(default="todo", description="Task status (todo, in_progress, completed)")
    priority: Optional[str] = Field(default="medium", description="Task priority (low, medium, high, urgent)")
    project: Optional[str] = Field(default="Engineering", description="Project name")
    dueDate: Optional[str] = Field(default=None, description="Due date (YYYY-MM-DD)")
    tags: Optional[List[str]] = Field(default_factory=list, description="List of task tags")

class TaskCreate(TaskBase):
    id: Optional[str] = Field(default=None, description="Optional custom ID")

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    project: Optional[str] = None
    dueDate: Optional[str] = None
    tags: Optional[List[str]] = None

class TaskResponse(TaskBase):
    id: str
    createdAt: Optional[datetime] = None

    class Config:
        from_attributes = True
