# Database Setup

Use Neon Postgres for persistent tracker data.

## Why Neon

- The backend already uses PostgreSQL, SQLAlchemy async, `asyncpg`, and Alembic.
- It works cleanly with Render for the FastAPI service.
- It also integrates cleanly with Vercel if server-side frontend database access is needed later.
- The free tier is suitable for the MVP tracker phase.

## Render Environment

Set these variables on the Render backend service:

```env
PROJECT_DEFENSE_ENVIRONMENT=production
PROJECT_DEFENSE_DEMO_MODE=false
PROJECT_DEFENSE_DEV_AUTH_BYPASS=false
PROJECT_DEFENSE_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST/DB?ssl=require
PROJECT_DEFENSE_DB_POOL_SIZE=5
PROJECT_DEFENSE_DB_MAX_OVERFLOW=5
PROJECT_DEFENSE_FRONTEND_URL=https://your-vercel-app.vercel.app
PROJECT_DEFENSE_CORS_ORIGINS=https://your-vercel-app.vercel.app
```

Render now runs:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

That applies migrations before the API starts.

## Vercel Environment

The frontend should call the API, not the database directly:

```env
NEXT_PUBLIC_API_URL=https://your-render-api.onrender.com
NEXT_PUBLIC_DEMO_MODE=false
```

## Local Development

Local development can keep using Docker Compose:

```bash
docker compose up
alembic upgrade head
```

The local default database URL remains:

```env
PROJECT_DEFENSE_DATABASE_URL=postgresql+asyncpg://project_defense:project_defense@localhost:5432/project_defense
```
