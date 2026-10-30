# FoodRoute: Smart Food Surplus Matching & Routing Platform

FoodRoute is a surplus food rescue and logistics optimization platform that scores donations and requests by **urgency and expiry**, matches them intelligently with split quantities, and plans **multi-depot, time-window-aware routes** for delivery fleets.

---

## Architecture & Module Split

| Module | Focus | Ownership | Key Directory |
|---|---|---|---|
| **Module 1** | Data models, Authentication, Urgency Scoring & Priority Matching | Member 1 (`Anagha`) | `/backend/db`, `/backend/matching` |
| **Module 2** | Multi-depot routing engine, split-delivery solver, time windows | Member 2 (`feature/module2-routing`) | `/backend/routing` |
| **Module 3** | React UI/UX, dashboards, Leaflet map routes, analytics | Member 3 (`feature/module3-frontend`) | `/frontend` |

---

## Tech Stack
- **Backend:** Python 3.9+, FastAPI, SQLAlchemy, SQLite, Pydantic, JWT Auth
- **Frontend:** React (Vite), Tailwind CSS, Leaflet, Recharts
- **Algorithms:** Urgency scoring heuristics, greedy split-delivery insertion, Haversine routing

---

## Quickstart

### Backend Setup
1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Run the development server:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```
4. Access the API documentation at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Shared Contracts
Refer to [`docs/api-contract.md`](docs/api-contract.md) and [`PROJECT_PLAN.md`](PROJECT_PLAN.md) for data schemas and endpoints.
