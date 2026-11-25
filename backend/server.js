const express = require('express');
const cors = require('cors');
const path = require('path');
const { Pool } = require('pg');
require('dotenv').config({ path: path.join(__dirname, '.env') });
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// Enable CORS so the React frontend can communicate with the backend
app.use(cors());
app.use(express.json());

// Initialize PostgreSQL Connection Pool for Neon
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: {
    rejectUnauthorized: false, // Required for Neon cloud SSL connections
  },
});

// Auto-initialize PostgreSQL Database Table on Startup
async function initDatabase() {
  try {
    const client = await pool.connect();
    console.log(' Connected to Neon PostgreSQL database successfully!');

    await client.query(`
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
    `);
    console.log(' Tasks table verified & ready in Neon database.');
    client.release();
  } catch (err) {
    console.error(' Failed to connect to Neon PostgreSQL:', err.message);
    console.log(' Note: Make sure to replace [YOUR_PASSWORD] in .env with your real password.');
  }
}

initDatabase();

// ========================== SWAGGER / OPENAPI SPECIFICATION ==========================
const swaggerSpec = {
  openapi: "3.0.0",
  info: {
    title: "PulseTask REST API",
    version: "1.0.0",
    description: "Production REST API for PulseTask SaaS backed by Neon Serverless PostgreSQL",
  },
  servers: [
    { url: "http://localhost:5000", description: "Local Development Server" }
  ],
  tags: [
    { name: "System", description: "Server health & diagnostics" },
    { name: "Tasks", description: "Task management CRUD operations connected to Neon DB" }
  ],
  paths: {
    "/api/health": {
      get: {
        tags: ["System"],
        summary: "API Health Check",
        description: "Checks if the Express server is up and running.",
        responses: {
          "200": {
            description: "Server is healthy",
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    status: { type: "string", example: "ok" },
                    service: { type: "string", example: "PulseTask Neon API" },
                    timestamp: { type: "string", format: "date-time" }
                  }
                }
              }
            }
          }
        }
      }
    },
    "/api/tasks": {
      get: {
        tags: ["Tasks"],
        summary: "Get All Tasks",
        description: "Retrieves all tasks from Neon PostgreSQL ordered by created_at DESC.",
        responses: {
          "200": {
            description: "Array of task objects",
            content: {
              "application/json": {
                schema: {
                  type: "array",
                  items: { $ref: "#/components/schemas/Task" }
                }
              }
            }
          }
        }
      },
      post: {
        tags: ["Tasks"],
        summary: "Create New Task",
        description: "Saves a new task into the Neon database.",
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/CreateTaskRequest" }
            }
          }
        },
        responses: {
          "201": {
            description: "Task created successfully",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Task" }
              }
            }
          },
          "400": { description: "Bad request - title is required" }
        }
      }
    },
    "/api/tasks/{id}": {
      put: {
        tags: ["Tasks"],
        summary: "Update Task",
        description: "Updates an existing task in Neon by ID.",
        parameters: [
          {
            name: "id",
            in: "path",
            required: true,
            description: "Task ID (e.g. task-1711234567890)",
            schema: { type: "string" }
          }
        ],
        requestBody: {
          required: true,
          content: {
            "application/json": {
              schema: { $ref: "#/components/schemas/UpdateTaskRequest" }
            }
          }
        },
        responses: {
          "200": {
            description: "Updated task object",
            content: {
              "application/json": {
                schema: { $ref: "#/components/schemas/Task" }
              }
            }
          },
          "404": { description: "Task not found" }
        }
      },
      delete: {
        tags: ["Tasks"],
        summary: "Delete Task",
        description: "Deletes a task permanently from Neon PostgreSQL.",
        parameters: [
          {
            name: "id",
            in: "path",
            required: true,
            description: "Task ID to delete",
            schema: { type: "string" }
          }
        ],
        responses: {
          "200": {
            description: "Task deleted",
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    success: { type: "boolean", example: true },
                    message: { type: "string", example: "Task task-123 deleted" }
                  }
                }
              }
            }
          },
          "404": { description: "Task not found" }
        }
      }
    },
    "/api/tasks-clear/completed": {
      delete: {
        tags: ["Tasks"],
        summary: "Bulk Delete Completed Tasks",
        description: "Removes all tasks marked as 'completed' from Neon.",
        responses: {
          "200": {
            description: "Completed tasks deleted",
            content: {
              "application/json": {
                schema: {
                  type: "object",
                  properties: {
                    success: { type: "boolean", example: true },
                    deletedCount: { type: "integer", example: 2 }
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  components: {
    schemas: {
      Task: {
        type: "object",
        properties: {
          id: { type: "string", example: "task-1711234567890" },
          title: { type: "string", example: "My First Full-Stack Task in Neon" },
          description: { type: "string", example: "Detailed task specifications" },
          status: { type: "string", enum: ["todo", "in_progress", "completed"], example: "todo" },
          priority: { type: "string", enum: ["low", "medium", "high", "urgent"], example: "medium" },
          project: { type: "string", example: "Engineering" },
          dueDate: { type: "string", example: "2026-11-28" },
          tags: {
            type: "array",
            items: { type: "string" },
            example: ["Backend", "NeonDB"]
          },
          createdAt: { type: "string", format: "date-time" }
        }
      },
      CreateTaskRequest: {
        type: "object",
        required: ["title"],
        properties: {
          title: { type: "string", example: "Integrate Stripe billing webhooks" },
          description: { type: "string", example: "Handle invoice generation and customer upgrade events." },
          status: { type: "string", enum: ["todo", "in_progress", "completed"], default: "todo" },
          priority: { type: "string", enum: ["low", "medium", "high", "urgent"], default: "medium" },
          project: { type: "string", default: "Engineering" },
          dueDate: { type: "string", example: "2026-12-01" },
          tags: {
            type: "array",
            items: { type: "string" },
            example: ["Payments", "API"]
          }
        }
      },
      UpdateTaskRequest: {
        type: "object",
        properties: {
          title: { type: "string", example: "Updated Task Title" },
          description: { type: "string", example: "Updated description text" },
          status: { type: "string", enum: ["todo", "in_progress", "completed"], example: "completed" },
          priority: { type: "string", enum: ["low", "medium", "high", "urgent"], example: "urgent" },
          project: { type: "string", example: "Engineering" },
          dueDate: { type: "string", example: "2026-12-05" },
          tags: {
            type: "array",
            items: { type: "string" },
            example: ["Sprint1"]
          }
        }
      }
    }
  }
};

// ========================== SWAGGER UI ENDPOINT ==========================
// OpenAPI Spec as raw JSON
app.get('/api/openapi.json', (req, res) => {
  res.json(swaggerSpec);
});

// Interactive Swagger UI HTML page
app.get(['/docs', '/api-docs', '/swagger'], (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PulseTask REST API | Interactive Swagger Documentation</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5.18.2/favicon-32x32.png" />
  <style>
    body { margin: 0; padding: 0; background: #fafafa; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .custom-topbar {
      background: #0f172a;
      color: #ffffff;
      padding: 12px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 2px solid #6366f1;
    }
    .custom-topbar .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }
    .custom-topbar .badge {
      background: #4338ca;
      color: #c7d2fe;
      font-size: 11px;
      padding: 3px 8px;
      border-radius: 9999px;
      font-weight: 600;
    }
    .custom-topbar .links {
      display: flex;
      gap: 16px;
      font-size: 13px;
    }
    .custom-topbar a {
      color: #93c5fd;
      text-decoration: none;
      transition: color 0.15s;
    }
    .custom-topbar a:hover {
      color: #ffffff;
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <div class="custom-topbar">
    <div class="brand">
      <span>⚡ PulseTask</span>
      <span class="badge">OpenAPI 3.0</span>
      <span style="font-size:13px; color:#94a3b8; font-weight:400;">Neon PostgreSQL REST API</span>
    </div>
    <div class="links">
      <a href="/" target="_blank">💻 Open App UI ↗</a>
      <a href="/api/openapi.json" target="_blank">📄 Raw OpenAPI JSON ↗</a>
    </div>
  </div>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui-bundle.js"></script>
  <script src="https://unpkg.com/swagger-ui-dist@5.18.2/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = () => {
      window.ui = SwaggerUIBundle({
        url: '/api/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout",
        docExpansion: "list",
        filter: true,
        showRequestDuration: true
      });
    };
  </script>
</body>
</html>`);
});

// ========================== API ROUTES ==========================

// Health Check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'PulseTask Neon API', timestamp: new Date() });
});

// 1. GET ALL TASKS
app.get('/api/tasks', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM tasks ORDER BY created_at DESC');
    // Map snake_case to camelCase for React frontend
    const tasks = result.rows.map(row => ({
      id: row.id,
      title: row.title,
      description: row.description,
      status: row.status,
      priority: row.priority,
      project: row.project,
      dueDate: row.due_date,
      tags: row.tags || [],
      createdAt: row.created_at,
    }));
    res.json(tasks);
  } catch (err) {
    console.error('Error fetching tasks:', err);
    res.status(500).json({ error: 'Failed to fetch tasks from database' });
  }
});

// 2. CREATE NEW TASK
app.post('/api/tasks', async (req, res) => {
  const { id, title, description, status, priority, project, dueDate, tags } = req.body;
  const taskId = id || 'task-' + Date.now();

  try {
    const query = `
      INSERT INTO tasks (id, title, description, status, priority, project, due_date, tags)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
      RETURNING *;
    `;
    const values = [
      taskId,
      title,
      description || '',
      status || 'todo',
      priority || 'medium',
      project || 'Engineering',
      dueDate || null,
      JSON.stringify(tags || []),
    ];

    const result = await pool.query(query, values);
    const row = result.rows[0];

    res.status(201).json({
      id: row.id,
      title: row.title,
      description: row.description,
      status: row.status,
      priority: row.priority,
      project: row.project,
      dueDate: row.due_date,
      tags: row.tags || [],
      createdAt: row.created_at,
    });
  } catch (err) {
    console.error('Error creating task:', err);
    res.status(500).json({ error: 'Failed to create task' });
  }
});

// 3. UPDATE TASK
app.put('/api/tasks/:id', async (req, res) => {
  const { id } = req.params;
  const { title, description, status, priority, project, dueDate, tags } = req.body;

  try {
    const query = `
      UPDATE tasks
      SET title = COALESCE($1, title),
          description = COALESCE($2, description),
          status = COALESCE($3, status),
          priority = COALESCE($4, priority),
          project = COALESCE($5, project),
          due_date = COALESCE($6, due_date),
          tags = COALESCE($7, tags)
      WHERE id = $8
      RETURNING *;
    `;
    const values = [
      title,
      description,
      status,
      priority,
      project,
      dueDate,
      tags ? JSON.stringify(tags) : null,
      id,
    ];

    const result = await pool.query(query, values);

    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Task not found' });
    }

    const row = result.rows[0];
    res.json({
      id: row.id,
      title: row.title,
      description: row.description,
      status: row.status,
      priority: row.priority,
      project: row.project,
      dueDate: row.due_date,
      tags: row.tags || [],
      createdAt: row.created_at,
    });
  } catch (err) {
    console.error('Error updating task:', err);
    res.status(500).json({ error: 'Failed to update task' });
  }
});

// 4. DELETE TASK
app.delete('/api/tasks/:id', async (req, res) => {
  const { id } = req.params;
  try {
    const result = await pool.query('DELETE FROM tasks WHERE id = $1 RETURNING *', [id]);
    if (result.rows.length === 0) {
      return res.status(404).json({ error: 'Task not found' });
    }
    res.json({ success: true, message: `Task ${id} deleted` });
  } catch (err) {
    console.error('Error deleting task:', err);
    res.status(500).json({ error: 'Failed to delete task' });
  }
});

// 5. BULK DELETE COMPLETED TASKS
app.delete('/api/tasks-clear/completed', async (req, res) => {
  try {
    const result = await pool.query("DELETE FROM tasks WHERE status = 'completed' RETURNING *");
    res.json({ success: true, deletedCount: result.rowCount });
  } catch (err) {
    console.error('Error clearing completed tasks:', err);
    res.status(500).json({ error: 'Failed to clear completed tasks' });
  }
});

// ========================== FRONTEND WEB SERVICE ==========================
// Serve the React frontend directly as a web service
const frontendPath = path.join(__dirname, '..');
app.use(express.static(frontendPath));

// Fallback all non-API web traffic to index.html
app.get('*', (req, res) => {
  if (!req.path.startsWith('/api')) {
    res.sendFile(path.join(frontendPath, 'index.html'));
  }
});

// Start Server locally (on Vercel, the app is exported as a Serverless Function)
if (process.env.VERCEL !== '1') {
  app.listen(PORT, () => {
    console.log(` PulseTask Full-Stack Web Service running on http://localhost:${PORT}`);
    console.log(` 💻 Web Application UI: http://localhost:${PORT}`);
    console.log(` 📄 Swagger API Docs:   http://localhost:${PORT}/docs`);
    console.log(` ⚡ Backend REST API:   http://localhost:${PORT}/api/tasks`);
  });
}

module.exports = app;
