# Fun Activity — City Buzz Tracker

Discover the best fun zones and upcoming events in any city, with real-time buzz scoring powered by multiple live data sources.

---

## What It Does

- **Fun Zones** — Finds and ranks entertainment venues (amusement parks, escape rooms, bowling alleys, go-karting, etc.) using a Bayesian scoring algorithm
- **Upcoming Events** — Aggregates events from PredictHQ and Google Events (via SerpAPI) with deduplication
- **Buzz Score** — Scores any event from 0–100 using Google Trends, News Coverage, Reddit discussions, and Time Proximity

---

## Architecture

```
Fun-Activity/
├── mcp-server/               ← Phase 1: MCP Tools (Claude Desktop)
│   ├── server.py             ← 3 MCP tools: fun_zones, events, buzz_score
│   ├── config.py             ← API keys, weights, constants
│   ├── ranking.py            ← Bayesian ranking engine
│   ├── buzz.py               ← Buzz scoring engine
│   ├── cache.py              ← In-memory TTL cache (6h)
│   └── data_sources/
│       ├── serpapi_client.py ← Google Maps, Events, News, YouTube
│       ├── predicthq_client.py ← PredictHQ event intelligence
│       ├── reddit_client.py  ← Reddit public JSON API
│       └── google_trends.py  ← pytrends (no API key needed)
│
├── backend/                  ← Phase 2: FastAPI + PostgreSQL
│   ├── main.py               ← App init, routes, dashboard
│   ├── database.py           ← Async SQLAlchemy engine + session
│   ├── models.py             ← 5 DB tables
│   ├── schemas.py            ← Pydantic request/response models
│   ├── routes/
│   │   ├── city_routes.py    ← CRUD for cities
│   │   ├── funzone_routes.py ← DB-first fetch, API fallback + sync
│   │   ├── event_routes.py   ← DB-first fetch, API fallback + sync
│   │   └── buzz_routes.py    ← DB-first fetch, compute fallback
│   └── services/
│       └── mcp_sync.py       ← Syncs MCP results into PostgreSQL
│
├── frontend/                 ← Phase 3: React + Tailwind (coming soon)
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Tech Stack

| Layer | Tech |
|-------|------|
| MCP Server | Python 3.11, FastMCP, httpx, pytrends |
| Backend API | FastAPI, SQLAlchemy (async), asyncpg |
| Database | PostgreSQL 15 |
| Containerization | Docker, Docker Compose |
| Data Sources | SerpAPI, PredictHQ, Reddit API, Google Trends |

---

## Database Schema

| Table | Description |
|-------|-------------|
| `cities` | City master list with coordinates |
| `fun_zones` | Ranked venues with scores, ratings, category |
| `events` | Upcoming events from PredictHQ + Google Events |
| `buzz_scores` | Historical buzz scores per event |
| `users` | Auth — reserved for Phase 3 |

---

## API Endpoints

### Cities
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/cities/` | Add a city |
| `GET` | `/cities/` | List all cities |

### Fun Zones
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/fun-zones/?city=Jaipur` | Get ranked fun zones (DB-first, syncs from API if empty) |

### Events
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/events/?city=Jaipur` | Get upcoming events (DB-first, syncs from API if empty) |

### Buzz Score
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/buzz/` | Compute or retrieve buzz score for an event |

### System
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info |
| `GET` | `/health` | Health check |
| `GET` | `/dashboard` | Total counts (cities, zones, events, buzz scores) |
| `GET` | `/docs` | Swagger UI |

---

## Buzz Score Formula

```
Buzz Score (0–100) =
  Google Trends search interest    × 30%
  News coverage (article count)    × 30%
  Reddit posts, upvotes, comments  × 25%
  Time proximity to event date     × 15%
```

When a source returns no data, its weight is redistributed proportionally to sources that did return data.

---

## Fun Zone Ranking Formula

```
Rank Score =
  Bayesian Rating (IMDb-style)     × 50%
  Activity Variety                 × 25%
  Category Diversity Penalty       × 15%
  Photo Count (log scale)          × 10%
```

---

## Setup

### Prerequisites
- Docker + Docker Compose
- A `.env` file in the project root (see below)

### Environment Variables

Create a `.env` file in the project root:

```env
SERPAPI_API_KEY=your_serpapi_key_here
PREDICTHQ_API_KEY=your_predicthq_key_here
DATABASE_URL=postgresql+asyncpg://fun_user:fun_secret_123@localhost:5432/fun_activity
```

Get your API keys:
- **SerpAPI** — https://serpapi.com (free tier: 100 searches/month)
- **PredictHQ** — https://www.predicthq.com (free tier: ~1000 events/month)
- **Google Trends** — No API key needed (uses pytrends)
- **Reddit** — No API key needed (uses public JSON API)

---

## Running with Docker

```bash
# Start PostgreSQL + Backend
docker compose up --build

# Run in background
docker compose up --build -d

# Stop
docker compose down
```

- Backend API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- PostgreSQL: `localhost:5432` (user: `fun_user`, db: `fun_activity`)

---

## Running Locally (without Docker)

```bash
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL separately (or use Docker just for DB)
docker compose up postgres -d

# 4. Run the backend
cd backend
uvicorn main:app --reload

# 5. (Optional) Run the MCP server for Claude Desktop
cd mcp-server
python server.py
```

---

## MCP Server (Claude Desktop Integration)

The MCP server exposes 3 tools that Claude can call directly:

| Tool | Description |
|------|-------------|
| `get_fun_zones(city, limit)` | Ranked list of fun activity zones |
| `get_upcoming_events(city)` | Upcoming events from multiple sources |
| `get_buzz_score(event_name, city, event_date)` | Buzz score with evidence breakdown |

To connect to Claude Desktop, add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "city-buzz-tracker": {
      "command": "python",
      "args": ["D:/Fun-Activity/mcp-server/server.py"]
    }
  }
}
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | Done | MCP Server — 3 tools, live data sources, buzz scoring |
| Phase 2 | Done | FastAPI backend + PostgreSQL + Docker |
| Phase 3 | Planned | React + Tailwind frontend dashboard |
| Phase 4 | Planned | User auth, saved cities, personalized recommendations |

---

## License

MIT
