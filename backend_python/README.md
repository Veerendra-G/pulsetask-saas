# PulseTask Python FastAPI Backend

FastAPI backend with Neon Serverless PostgreSQL database integration and automatic Swagger documentation.

## Features
- **Framework**: FastAPI (Python 3.12)
- **Database**: Neon Serverless PostgreSQL with SSL (`psycopg2`)
- **Documentation**: Automatic OpenAPI Swagger docs at `/docs` and ReDoc at `/redoc`
- **Frontend Serving**: Automatically serves the React frontend at `http://localhost:8000`
- **CORS**: Configured to accept requests from all origins (localhost, Vercel, mobile)

## Quick Start

### 1. Start the Server
In PowerShell:
```powershell
cd C:\Users\gandl\.gemini\antigravity\scratch\todo_saas_react\backend_python
python -m uvicorn main:app --port 8000 --reload
```
*(Or double-click `run.bat`)*

### 2. Endpoints
- **React SaaS Web App**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Tasks REST API**: [http://localhost:8000/api/tasks](http://localhost:8000/api/tasks)
