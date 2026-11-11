# Shorty — Design Notes

How Shorty works and why it is built this way. For setup, see the [README](../README.md).

## Overview

**Shorty** is a full-stack URL shortening service with real-time click analytics. It demonstrates high-performance caching patterns, read-heavy database optimization, and modern full-stack development practices.

**Problem Statement:** URL shorteners have extreme read-to-write ratios (100:1 or higher). How do you serve millions of redirects with minimal latency while capturing detailed analytics?

**Solution:** Cache-Aside pattern with Redis + MySQL persistence, Flask blueprints for modular architecture, and a Vue 3 dashboard for visualization.

## 🏗️ Architecture Deep Dive

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REQUEST FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│    ┌──────────┐                                                              │
│    │  User    │                                                              │
│    │ Browser  │                                                              │
│    └────┬─────┘                                                              │
│         │                                                                    │
│         ▼                                                                    │
│    ┌──────────────────────────────────────────────────────────────────┐     │
│    │                    NGINX / Load Balancer                         │     │
│    └─────────────────────────┬────────────────────────────────────────┘     │
│                              │                                               │
│         ┌────────────────────┴────────────────────┐                         │
│         │                                         │                          │
│         ▼                                         ▼                          │
│    ┌─────────────┐                         ┌─────────────┐                  │
│    │ Vue 3 SPA   │                         │  Flask API  │                  │
│    │ Dashboard   │◀── JSON/REST ─────────▶│  (Gunicorn) │                  │
│    │ Port: 5173  │                         │  Port: 5000 │                  │
│    └─────────────┘                         └──────┬──────┘                  │
│                                                   │                          │
│                              ┌────────────────────┴────────────────┐        │
│                              │                                      │        │
│                              ▼                                      ▼        │
│                       ┌───────────┐                          ┌───────────┐  │
│                       │   Redis   │                          │  MySQL    │  │
│                       │  (Cache)  │                          │  (Data)   │  │
│                       │ Port:6379 │                          │ Port:3306 │  │
│                       └───────────┘                          └───────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Request Flow: URL Redirect

```
User clicks: https://shorty.io/abc123

1. Request hits Flask API at /{short_code}
2. Check Redis cache: GET link:abc123   (JSON: id, url, expires_at)
   ├── HIT: use the cached entry, no MySQL read
   ├── MISS: SELECT from MySQL → SETEX link:abc123 (TTL 1h) → use it
   └── Redis down: logged, treated as a miss (service keeps working)
3. Unknown/inactive → 404, expired → 410
4. INSERT the click row + UPDATE links SET click_count = click_count + 1 (one commit)
5. HTTP 302 Redirect (Cache-Control: no-store so repeat visits are counted)
```

## 📊 Database Schema

### Entity Relationship Diagram

```
┌─────────────────────────────────────┐
│              LINKS                   │
├─────────────────────────────────────┤
│ id              INTEGER (PK)         │
│ short_code      VARCHAR(32) UNIQUE   │  ◀── B-Tree Index
│ original_url    TEXT                 │
│ title           VARCHAR(255)         │
│ created_at      TIMESTAMP            │
│ expires_at      TIMESTAMP            │
│ is_active       BOOLEAN              │
│ click_count     INTEGER              │  ◀── Denormalized counter
└─────────────────────────────────────┘
              │
              │ 1:N
              ▼
┌─────────────────────────────────────┐
│             CLICKS                   │
├─────────────────────────────────────┤
│ id              INTEGER (PK)         │
│ link_id         INTEGER (FK)         │  ◀── Composite index (link_id, clicked_at)
│ clicked_at      TIMESTAMP            │  ◀── Index
│ ip_address      VARCHAR(45)          │
│ user_agent      TEXT                 │
│ referrer        TEXT                 │
│ device_type     VARCHAR(20)          │
│ browser         VARCHAR(50)          │
│ os              VARCHAR(50)          │
│ country         VARCHAR(100)         │
│ city            VARCHAR(100)         │
└─────────────────────────────────────┘
```

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate `clicks` table** | Detailed analytics per click, flexible querying, audit trail |
| **Denormalized `click_count`** | Avoid `COUNT(*)` on dashboards, O(1) reads |
| **Index on `short_code`** | Primary lookup field, O(log N) instead of O(N) |
| **Index on `(link_id, clicked_at)`** | Per-link time-window analytics queries |
| **`shortuuid` for codes** | Base57 (no ambiguous chars), 8 chars = 57^8 combinations; collisions retried on the unique index |
| **Atomic counter update** | `click_count = click_count + 1` in SQL, so concurrent clicks are never lost |
| **Soft delete** | Deleted links stop redirecting but keep their analytics |

## 🔑 Key Technical Decisions

### 1. Cache-Aside Pattern (vs Write-Through)

**Why Cache-Aside?**
```python
def get_original_url(short_code):
    # 1. Check cache first
    cached = redis.get(f"link:{short_code}")
    if cached:
        return cached.decode()  # Cache HIT: <5ms
    
    # 2. Cache MISS: Query database
    link = Link.query.filter_by(short_code=short_code).first()
    if not link:
        return None
    
    # 3. Populate cache for next time
    redis.setex(f"link:{short_code}", 3600, link.original_url)
    return link.original_url
```

**Why not Write-Through?**
- URL shorteners are 100:1 read-heavy
- Cache-Aside only caches actively-used URLs
- Lower write latency (no cache update on creation)

### 2. Flask Blueprints Architecture

```python
# Modular route organization
app.register_blueprint(links_bp, url_prefix='/api/links')
app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
app.register_blueprint(redirect_bp)  # No prefix - handles /{short_code}
```

**Benefits:**
- Feature-based code organization
- Independent testing per module
- Clean separation of concerns

### 3. Application Factory Pattern

```python
def create_app(config_name=None):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    from app.routes.links import links_bp
    app.register_blueprint(links_bp, url_prefix='/api/links')
    
    return app
```

**Benefits:**
- Different configs for dev/test/prod
- Clean extension initialization
- Testable with isolated instances

## 🚀 Performance Optimizations

### 1. Redis Caching

The cache removes the MySQL **read** from the redirect path. Every redirect still **writes** a click row and bumps the counter, so database write load grows with traffic. The next step for high volume is to push click events to a queue and batch-insert them (see Q3).

These numbers have not been benchmarked; measure before quoting them.

### 2. Database Indexing

```sql
-- B-Tree index on lookup column
CREATE INDEX idx_links_short_code ON links(short_code);

-- Without the index, lookups scan the table (O(N));
-- with it, lookups are an index seek (O(log N)).
```

### 3. Denormalized Click Counter

```python
# Instead of COUNT(*) every time:
SELECT COUNT(*) FROM clicks WHERE link_id = 1;  -- Slow: O(clicks)

# Store counter directly:
UPDATE links SET click_count = click_count + 1 WHERE id = 1;
SELECT click_count FROM links WHERE id = 1;  -- Fast: O(1)
```

## 🎨 Frontend Architecture

### Vue 3 Composition API

`App.vue` uses `<script setup>` with `ref`/`reactive` state. HTTP calls live in `src/api.js` (one axios instance with a base URL and timeout). Errors are shown inline instead of with `alert()`, and the Chart.js instance is destroyed when the analytics panel closes so charts don't leak.

### Technology Choices

| Technology | Purpose | Why? |
|------------|---------|------|
| Vue 3 | Framework | Composition API, reactivity, familiar from work |
| Chart.js | Visualization | Simple, lightweight, good defaults |
| Vite | Build tool | Fast HMR, simple config |
| Axios | HTTP client | Promise-based, interceptors |

## 🐳 Docker & DevOps

### Docker Compose Services

```yaml
services:
  mysql:      # Data persistence
  redis:      # Caching layer
  api:        # Flask backend (runs `flask db upgrade` first; depends on mysql, redis)
  frontend:   # Vue development server
```

### Health Checks

```yaml
mysql:
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-proot_secret"]
    interval: 5s
    retries: 10

redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
```

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/links` | Create short link (`url`, optional `title`, `custom_code`, `expires_in_days`) |
| `GET` | `/api/links` | List active links (paginated) |
| `GET` | `/api/links/{id}` | Get link details |
| `PATCH` | `/api/links/{id}` | Update `title` / `is_active` |
| `DELETE` | `/api/links/{id}` | Soft-delete link (204) |
| `GET` | `/api/analytics/summary` | Totals and top links |
| `GET` | `/api/analytics/links/{id}?days=7` | Link analytics (1–365 days) |
| `GET` | `/api/analytics/links/{id}/clicks` | Raw click history (paginated) |
| `GET` | `/{short_code}` | Redirect to original URL |
| `GET` | `/health` | Health check |
