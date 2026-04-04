# Task Management API

A **production-style FastAPI backend** demonstrating real-world architecture patterns compared against Django REST Framework.

---

## 🏗️ Project Structure

```
app/
├── main.py                    ← App entry point (= Django's urls.py + manage.py)
├── api/
│   └── v1/
│       ├── user.py            ← User routes (= DRF UserViewSet)
│       └── task.py            ← Task routes (= DRF TaskViewSet)
├── schemas/
│   ├── user.py                ← Request/Response schemas (= DRF Serializers)
│   └── task.py
├── models/
│   ├── user.py                ← SQLAlchemy ORM model (= Django Model)
│   └── task.py
├── services/
│   ├── user_service.py        ← Business logic (= Missing in DRF, usually in views)
│   └── task_service.py
├── repositories/
│   ├── user_repo.py           ← DB queries only (= Django Manager / ORM calls)
│   └── task_repo.py
├── db/
│   ├── session.py             ← Engine + SessionLocal (= Django DB backend config)
│   └── base.py                ← DeclarativeBase + model imports for Alembic
├── core/
│   ├── config.py              ← Pydantic Settings (= Django settings.py)
│   ├── security.py            ← JWT + bcrypt utilities
│   └── dependencies.py        ← Depends() functions (= DRF authentication classes)
└── middleware/
    └── logging.py             ← Request/response logger (= Django middleware)
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL running locally

### 2. Setup

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment

```bash
# Copy and edit the .env file
copy .env.example .env
# Edit .env: set DATABASE_URL with your PostgreSQL credentials
# Generate a strong secret key:
# python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Create the database

```sql
-- In psql or pgAdmin:
CREATE DATABASE taskmanager_db;
```

### 5. Run migrations

```bash
# Apply the initial migration (creates users + tasks tables)
alembic upgrade head

# To generate a new migration after model changes:
alembic revision --autogenerate -m "add column xyz"
alembic upgrade head
```

### 6. Start the server

```bash
uvicorn app.main:app --reload
```

Visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

---

## 🔑 Authentication Flow

```
1. Register:  POST /api/v1/users/register      { email, full_name, password }
2. Login:     POST /api/v1/users/login         { email, password }
              ← returns access_token + refresh_token
3. Use:       GET  /api/v1/tasks/
              Header: Authorization: Bearer <access_token>
4. Refresh:   POST /api/v1/users/refresh       { refresh_token }
              ← returns new token pair
```

---

## 📡 API Endpoints

### Users (`/api/v1/users`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/register` | No | Register new user |
| POST | `/login` | No | Login → get JWT tokens |
| POST | `/refresh` | No | Refresh access token |
| GET | `/me` | ✅ | Get my profile |
| PATCH | `/me` | ✅ | Update my profile |
| POST | `/me/change-password` | ✅ | Change password |
| DELETE | `/me` | ✅ | Deactivate account |

### Tasks (`/api/v1/tasks`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/` | ✅ | Create task |
| GET | `/` | ✅ | List tasks (paginated + filtered) |
| GET | `/{id}` | ✅ | Get task by ID |
| PATCH | `/{id}` | ✅ | Update task (partial) |
| DELETE | `/{id}` | ✅ | Delete task |

### Query Parameters for `GET /tasks/`

| Param | Type | Example |
|-------|------|---------|
| `status` | string | `todo`, `in_progress`, `done` |
| `priority` | string | `low`, `medium`, `high` |
| `is_completed` | bool | `true`, `false` |
| `search` | string | full-text search in title + desc |
| `page` | int | `1` (default) |
| `page_size` | int | `10` (default, max 100) |

---

## ⭐ DRF → FastAPI Concept Map

| DRF Concept | FastAPI Equivalent | File |
|------------|-------------------|------|
| `settings.py` | `Pydantic Settings` | `core/config.py` |
| `models.Model` | `SQLAlchemy Base` | `models/*.py` |
| `Serializer` | `Pydantic BaseModel` | `schemas/*.py` |
| `ViewSet / APIView` | `APIRouter` functions | `api/v1/*.py` |
| `get_queryset()` | `Repository methods` | `repositories/*.py` |
| `perform_create()` | `Service layer` | `services/*.py` |
| `request.user` | `Depends(get_current_user)` | `core/dependencies.py` |
| `permission_classes` | `Depends(get_current_active_user)` | Route functions |
| `Django middleware` | `BaseHTTPMiddleware` | `middleware/logging.py` |
| `urls.py + include()` | `app.include_router()` | `main.py` |
| `makemigrations` | `alembic revision --autogenerate` | `alembic/` |
| `migrate` | `alembic upgrade head` | `alembic/` |

---

## 🔁 Request Flow

```
HTTP Request
    │
    ▼
LoggingMiddleware  (middleware/logging.py)
    │  ← logs method, path, client IP
    ▼
CORSMiddleware     (main.py — Starlette built-in)
    │
    ▼
APIRouter          (api/v1/task.py)
    │  ← Pydantic validates request body → 422 if invalid
    │  ← Depends(get_db) creates DB session
    │  ← Depends(get_current_active_user) validates JWT → resolves User
    ▼
TaskService        (services/task_service.py)
    │  ← Business rules (ownership, auto-status, etc.)
    ▼
TaskRepository     (repositories/task_repo.py)
    │  ← SQLAlchemy query (filtered by owner_id)
    ▼
PostgreSQL Database
    │
    ▼
SQLAlchemy ORM model (Task instance)
    │
    ▼
TaskService        (returns Task to router)
    │
    ▼
APIRouter          (serializes with TaskResponse Pydantic schema)
    │
    ▼
LoggingMiddleware  (logs status code + response time)
    │
    ▼
HTTP Response (JSON)
```

---

## 🔐 Security Features

- **bcrypt password hashing** (salted, cost factor 12)
- **JWT dual-token** (short-lived access + long-lived refresh)
- **Token type claim** (prevents refresh tokens being used as access tokens)
- **IDOR protection** (all task queries filter by owner_id at DB level)
- **User enumeration prevention** (same 401 for "not found" and "wrong password")
- **Soft-delete** (deactivated accounts block login without losing data)

---

## 🧪 Alembic Migration Commands

```bash
# See current migration state
alembic current

# View migration history
alembic history --verbose

# Generate migration from model changes
alembic revision --autogenerate -m "add task_tags table"

# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to a specific revision
alembic downgrade 001_initial

# Preview SQL without applying
alembic upgrade head --sql
```

---

## 🚀 Production Deployment

```bash
# With Gunicorn + Uvicorn workers (recommended for production)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Environment variables for production:
DEBUG=False
SECRET_KEY=<32-byte random hex>
DATABASE_URL=postgresql://user:pass@prod-db-host:5432/taskmanager_db
```
