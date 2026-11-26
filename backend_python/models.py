from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Title of the task")
    description: Optional[str] = Field(default="", description="Detailed task description")
    status: Optional[str] = Field(default="todo", description="Task status (todo, in_progress, review, completed)")
    priority: Optional[str] = Field(default="medium", description="Task priority (low, medium, high, urgent)")
    project: Optional[str] = Field(default="Engineering", description="Project name")
    dueDate: Optional[str] = Field(default=None, description="Due date (YYYY-MM-DD)")
    tags: Optional[List[str]] = Field(default_factory=list, description="List of task tags")
    userId: Optional[str] = Field(default=None, description="Owner user ID")

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

# --- User Authentication Models ---
class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="User email address")
    password: str = Field(..., min_length=6, max_length=128, description="User password (min 6 chars)")
    name: Optional[str] = Field(default="", max_length=255, description="User display name")

class UserLogin(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="User email address")
    password: str = Field(..., min_length=1, max_length=128, description="User password")

class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Registered email address")

class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Registered email address")
    new_password: str = Field(..., min_length=6, max_length=128, description="New password")
    token: Optional[str] = Field(default=None, description="Optional reset token")

class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = Field(default=None, description="Google JWT ID token or mock token")
    email: Optional[str] = Field(default=None, description="Direct email from Google Auth popup")
    name: Optional[str] = Field(default=None, description="Display name from Google Auth popup")
    picture: Optional[str] = Field(default=None, description="Google user avatar URL")

class SocialAuthRequest(BaseModel):
    provider: str = Field(default="google", description="Social provider name: google")
    credential: Optional[str] = Field(default=None, description="Token or credential")
    email: Optional[str] = Field(default=None, description="User email")
    name: Optional[str] = Field(default=None, description="Display name")
    picture: Optional[str] = Field(default=None, description="Avatar URL")

class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = ""
    avatarUrl: Optional[str] = None
    provider: Optional[str] = "local"
    createdAt: Optional[datetime] = None

class AuthResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserResponse
