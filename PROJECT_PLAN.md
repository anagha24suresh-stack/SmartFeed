# FoodRoute: Smart Food Surplus Matching & Routing

A web platform that scores donations and requests by **urgency and expiry**, matches them intelligently, and plans **multi-depot, split-delivery routes** that respect **perishability time windows**.

---

## 1. Problem Summary

**Problem statement:** Surplus food goes to waste because donation decisions are made by proximity or posting order. Urgency and expiry are never evaluated at matching time, so matches happen too late and high-need requests get overlooked.

**Problem description:** Real food banks use multiple depots and a limited fleet. Vehicles often cannot complete a full pickup or delivery at every stop. Food has narrow usable windows, and donors and receivers are available only at certain times. Most routing tools ignore all of this.

**Our solution:**
1. **Score** every donation and request by urgency, expiry and need.
2. **Match** them in priority order, allowing partial (split) quantities.
3. **Route** vehicles from multiple depots, with split pickup/delivery and time windows.
4. **Show** everything in a clear dashboard that anyone can use.

---

## 2. Team and Module Split

| Module | Owner | Branch | Folder |
|---|---|---|---|
| **Module 1:** Data, Auth and Urgency Matching | Member 1 | `feature/module1-matching` | `/backend/matching`, `/backend/db` |
| **Module 2:** Routing Optimization Engine | Member 2 | `feature/module2-routing` | `/backend/routing` |
| **Module 3:** Frontend UI/UX and Visualization | Member 3 | `feature/module3-frontend` | `/frontend` |

Each member works **only inside their own folder**. This keeps merge conflicts close to zero.

---

## 3. Tech Stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite, Tailwind CSS, Leaflet (maps), Recharts (charts) |
| Backend | Python, FastAPI |
| Database | SQLite (dev), PostgreSQL optional |
| Routing math | Python (NumPy), Haversine distance |
| Auth | JWT |
| Testing | Pytest (backend), Vitest (frontend) |
| Version control | Git + GitHub |

---

## 4. Repository Structure

```
foodroute/
├── README.md
├── PROJECT_PLAN.md
├── backend/
│   ├── main.py                  # FastAPI app (created on main, shared)
│   ├── db/                      # Module 1
│   │   ├── models.py
│   │   └── seed.py
│   ├── matching/                # Module 1
│   │   ├── scoring.py
│   │   ├── matcher.py
│   │   └── api.py
│   ├── routing/                 # Module 2
│   │   ├── distance.py
│   │   ├── solver.py
│   │   ├── time_windows.py
│   │   └── api.py
│   └── tests/
├── frontend/                    # Module 3
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── api/
│   │   └── App.jsx
│   └── package.json
└── docs/
    └── api-contract.md
```

---

## 4.1 Shared Data Contract (agree on this on Day 1)

All three modules depend on the same shapes. Freeze these before coding.

**Donation**
```json
{
  "id": 1,
  "donor_name": "Green Leaf Restaurant",
  "food_type": "Cooked meals",
  "quantity_kg": 40,
  "location": { "lat": 12.97, "lng": 77.59 },
  "ready_time": "2026-11-05T14:00",
  "expiry_time": "2026-11-05T20:00",
  "pickup_window": { "start": "14:00", "end": "17:00" },
  "status": "open"
}
```

**Request**
```json
{
  "id": 7,
  "receiver_name": "Hope Shelter",
  "quantity_kg": 60,
  "location": { "lat": 12.93, "lng": 77.62 },
  "delivery_window": { "start": "15:00", "end": "19:00" },
  "need_level": 4,
  "status": "open"
}
```

**Depot**
```json
{ "id": 1, "name": "North Depot", "location": { "lat": 13.0, "lng": 77.58 } }
```

**Vehicle**
```json
{ "id": 1, "depot_id": 1, "capacity_kg": 100, "available_from": "09:00", "available_to": "21:00" }
```

**Match** (output of Module 1, input to Module 2)
```json
{
  "match_id": 12,
  "donation_id": 1,
  "request_id": 7,
  "allocated_kg": 40,
  "priority_score": 0.87
}
```

**Route** (output of Module 2, input to Module 3)
```json
{
  "vehicle_id": 1,
  "depot_id": 1,
  "stops": [
    { "type": "pickup", "donation_id": 1, "kg": 40, "arrive": "14:20", "depart": "14:35" },
    { "type": "delivery", "request_id": 7, "kg": 40, "arrive": "15:10", "depart": "15:25" }
  ],
  "total_distance_km": 18.4,
  "total_time_min": 95
}
```

---

## 5. Module 1: Data, Auth and Urgency Matching (Member 1)

**Goal:** Store all data, let users log in, and decide *which donation should go to which request* using urgency, not just distance.

### 5.1 Responsibilities
- Database design and seed data (donors, receivers, depots, vehicles).
- User roles: **Donor**, **Receiver**, **Admin**.
- CRUD endpoints for donations, requests, depots and vehicles.
- **Urgency scoring engine** (the core idea of the project).
- **Matching engine** that produces partial matches.
- Expose matches to Module 2.

### 5.2 Urgency Scoring

Each donation and request gets a score between 0 and 1.

```
Donation urgency  = 0.6 * expiry_pressure + 0.3 * quantity_weight + 0.1 * pickup_window_tightness
Request urgency   = 0.5 * need_level_norm + 0.3 * window_tightness + 0.2 * waiting_time_norm
```

- `expiry_pressure` = 1 − (time_left / max_shelf_life). Less time left means a higher score.
- `need_level_norm` = need level (1 to 5) divided by 5.
- `window_tightness` = 1 − (window_length / 24h).

Weights are stored in a config file so the team can tune them.

### 5.3 Matching Algorithm
1. Score all open donations and requests.
2. Sort donations by urgency (highest first). Sort requests by urgency (highest first).
3. For each donation, compute a **compatibility score** with each request: `priority = donation_urgency * request_urgency * feasibility`.
4. `feasibility` is 0 if the food would expire before it could realistically arrive, otherwise 1 (minus a small distance penalty).
5. Allocate `min(remaining_donation, remaining_request)`. **Splits are allowed**, so one donation can feed several requests and one request can be served by several donations.
6. Repeat until nothing feasible is left. Mark leftovers as *unmatched* with a reason (for example "expires before reachable").

### 5.4 API Endpoints
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/auth/register`, `/auth/login` | Account creation and login |
| GET/POST | `/donations` | List and create donations |
| GET/POST | `/requests` | List and create requests |
| GET/POST | `/depots`, `/vehicles` | Admin setup |
| GET | `/scores` | Current urgency scores |
| POST | `/matching/run` | Run matching, return matches |
| GET | `/matching/results` | Latest matches and unmatched items |

### 5.5 Deliverables
- [ ] Database schema and seed script (at least 10 donations, 10 requests, 3 depots, 5 vehicles)
- [ ] Auth with three roles
- [ ] All CRUD endpoints
- [ ] Scoring and matching code with unit tests
- [ ] `docs/api-contract.md` for the endpoints above

### 5.6 Definition of Done
- Matching run on seed data takes under 1 second.
- A donation expiring in 2 hours is always matched before an identical one expiring in 10 hours.
- Tests pass.

---

## 6. Module 2: Routing Optimization Engine (Member 2)

**Goal:** Turn matches into **real vehicle routes** that work in practice: multiple depots, limited capacity, split pickup/delivery, and time windows.

### 6.1 Responsibilities
- Distance and travel-time matrix (Haversine, with an average speed setting).
- Multi-depot vehicle assignment.
- Route construction with **split pickup and delivery**.
- Time-window checking, including food expiry.
- Efficient enough for everyday use (under 5 seconds for about 30 stops).

### 6.2 What Makes This Different from a Basic Router

| Real-world rule | How the solver handles it |
|---|---|
| Many depots | Every vehicle starts and ends at its own depot. Stops are assigned to the nearest feasible depot's fleet. |
| Limited capacity | Vehicle load never exceeds capacity at any point. |
| Partial pickup or delivery | A stop can be visited more than once or served partially, so capacity is never wasted. |
| Time windows | Arrival must fall inside the stop's window. Waiting is allowed if early. |
| Perishability | Delivery must happen before `expiry_time`. Late routes are rejected. |

### 6.3 Algorithm Plan
1. **Build tasks** from Module 1's matches (a pickup and a delivery for each).
2. **Initial solution:** greedy insertion. Insert each pickup and its delivery into the vehicle route with the smallest cost increase, checking capacity and time windows after every insertion.
3. **Split handling:** if a task does not fit in one vehicle, divide the quantity across vehicles or across visits.
4. **Improvement:** local search with 2-opt (reverse segments), relocate (move a stop) and swap (exchange two stops between routes). Accept only feasible improvements.
5. **Cost function:** `distance_km + penalty * lateness + big_penalty * expiry_violation`.
6. Output routes plus any tasks that could not be served, with a reason.

### 6.4 API Endpoints
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/routing/plan` | Build routes from the current matches |
| GET | `/routing/routes` | Latest routes |
| GET | `/routing/summary` | Totals: distance, food delivered, unserved |
| POST | `/routing/replan` | Re-run after a change (new donation, vehicle down) |

### 6.5 Metrics to Report
- Total distance and time
- Percentage of requested food delivered
- Percentage of donated food used before expiry
- Average vehicle capacity utilization
- Number of split deliveries

### 6.6 Deliverables
- [ ] Distance and time matrix module
- [ ] Greedy insertion solver with capacity and time-window checks
- [ ] Split pickup/delivery logic
- [ ] Local search improvement
- [ ] Baseline comparison (nearest-neighbor, single-depot, no splits) so the project can *show* the improvement
- [ ] Unit tests with hand-checked small cases

### 6.7 Definition of Done
- No route ever exceeds vehicle capacity.
- No delivery happens after food expiry.
- Multi-depot plan delivers more food than the single-depot baseline on the same seed data.
- 30 stops solve in under 5 seconds.

---

## 7. Module 3: Frontend UI/UX and Visualization (Member 3)

**Goal:** A clean, easy interface where a donor, receiver or food bank admin can finish their task in a few clicks without training.

### 7.1 Design Principles
- One clear action per screen.
- Plain-language labels ("Donate Food", not "Create Supply Entry").
- Color meaning is consistent: **red** = urgent, **amber** = soon, **green** = safe.
- Mobile-friendly, since donors often use phones.
- Every action gives visible feedback (toast message, loading state, error text).
- Accessible: good contrast, labels on all inputs, keyboard navigation.

### 7.2 Pages and Screens

| Page | Who uses it | What it shows |
|---|---|---|
| **Login / Register** | Everyone | Role selection, simple form |
| **Donor Dashboard** | Donor | My donations, status, "Donate Food" button |
| **Donate Food form** | Donor | Food type, quantity, pickup address on map, ready time, expiry time |
| **Receiver Dashboard** | Receiver | My requests, status, "Request Food" button |
| **Request Food form** | Receiver | Quantity needed, location, delivery window, need level |
| **Admin Control Center** | Admin | Map, urgency list, matches, routes, run buttons |
| **Route Details** | Admin, Driver | Step-by-step stops with times and quantities |
| **Analytics** | Admin | Food saved, waste avoided, route efficiency charts |

### 7.3 Button and Component Guide

| Component | Label | Behavior |
|---|---|---|
| Primary button | **Donate Food** / **Request Food** | Opens the form |
| Action button | **Run Matching** | Calls `/matching/run`, shows spinner, then results |
| Action button | **Plan Routes** | Calls `/routing/plan`, draws routes on map |
| Secondary button | **Re-plan** | Re-runs after a change |
| Urgency badge | Urgent / Soon / Safe | Colored by score |
| Countdown chip | "Expires in 2h 15m" | Live countdown |
| Map | Depots, donors, receivers, routes | Colored route lines, clickable markers |
| Timeline | Stop sequence | Pickup and delivery icons with arrival times |
| Stat cards | Meals saved, kg delivered, distance | Top of dashboard |
| Empty state | "No donations yet. Add one!" | Shown when lists are empty |
| Confirm dialog | "Delete this donation?" | Before destructive actions |

### 7.4 Key Screens in Detail

**Admin Control Center** (the main screen)
- Left panel: urgency-ranked list of donations and requests with badges.
- Center: map with colored markers (depots, donors, receivers) and route lines per vehicle.
- Right panel: matches and route summary.
- Top bar: **Run Matching** then **Plan Routes** (the second is disabled until the first is done).
- Time slider to preview the plan at different times of the day.

**Route Details**
- Vertical timeline per vehicle: depot, pickup, delivery, depot.
- Each step shows place, time, quantity, and a red warning if close to expiry.
- **Download PDF** or **Print** button for drivers.

### 7.5 Deliverables
- [ ] Design system (colors, fonts, spacing, button styles) in Tailwind config
- [ ] All pages in the table above
- [ ] API client layer (`/frontend/src/api`) with a **mock mode** so the UI can be built before the backend is ready
- [ ] Map integration with routes
- [ ] Analytics charts
- [ ] Responsive layout and basic accessibility checks
- [ ] Loading, error and empty states on every page

### 7.6 Definition of Done
- A first-time user can submit a donation in under 1 minute.
- Admin can go from "Run Matching" to a visible route map in 3 clicks.
- No page breaks on a phone-sized screen.

---

## 8. GitHub Workflow

### 8.1 Setup (one person, Day 1)
```bash
git init
git add .
git commit -m "chore: initial project structure"
git branch -M main
git remote add origin <repo-url>
git push -u origin main
```
Then create the three branches:
```bash
git checkout -b feature/module1-matching
git push -u origin feature/module1-matching
# repeat for module2-routing and module3-frontend
```
Each member clones the repo and switches to their own branch.

### 8.2 Rules
1. **Never commit directly to `main`.** Merge only through pull requests.
2. Work only in your own folder. If you need a shared file changed, tell the team first.
3. Commit small and often, using clear messages:
   - `feat: add urgency scoring`
   - `fix: capacity check in insertion`
   - `docs: update api contract`
4. Pull from `main` regularly to stay current:
   ```bash
   git fetch origin
   git merge origin/main
   ```
5. Every PR needs at least **one teammate review** before merging.
6. Do not change the shared data contract (Section 4.1) without agreement from all three.

### 8.3 Merge Order
1. **Module 1** merges first (the database and data models everyone depends on).
2. **Module 2** merges second (needs Module 1 matches).
3. **Module 3** merges last (connects to both).
4. After each merge, the next member pulls `main` into their branch and resolves any conflicts before opening their PR.

### 8.4 Integration Checklist (after all three are merged)
- [ ] Backend starts with one command
- [ ] Frontend connects to the real API (mock mode turned off)
- [ ] Full flow works: add donation, add request, run matching, plan routes, view map
- [ ] Seed data loads cleanly on a fresh clone
- [ ] README has setup steps that actually work

---

## 9. Timeline (suggested, 4 weeks)

| Week | Module 1 | Module 2 | Module 3 |
|---|---|---|---|
| **1** | Schema, auth, CRUD, seed data | Distance matrix, task model, basic single-vehicle route | Design system, login, forms (mock API) |
| **2** | Urgency scoring, matching with splits | Multi-depot insertion, capacity and time windows | Dashboards, urgency list, map markers |
| **3** | Tests, tune weights, API docs | Split logic, local search, baseline comparison | Route map, timeline, analytics |
| **4** | **Integration, bug fixes, demo data, report** | **Integration, bug fixes** | **Integration, polish, responsive fixes** |

---

## 10. Testing Plan

| Area | Test |
|---|---|
| Scoring | Shorter expiry always gives a higher score |
| Matching | Splits add up exactly to donated and requested quantities |
| Routing | Capacity never exceeded; no stop outside its window; no delivery after expiry |
| Routing | Multi-depot beats single-depot baseline on seed data |
| API | Each endpoint returns the agreed JSON shape |
| UI | Forms validate input; empty, loading and error states appear |
| End to end | One full scenario from donation to route display |

---

## 11. Demo Scenario (for the final presentation)

1. Show the **old way**: three donations matched by proximity or posting order. One high-need shelter is missed and food expires.
2. Add the same data to FoodRoute.
3. Click **Run Matching**. Urgent items jump to the top, and the shelter gets served.
4. Click **Plan Routes**. Show multiple depots, split deliveries and time windows on the map.
5. Show the analytics: more food delivered, less expired, better vehicle usage.

---

## 12. Expected Outcomes

- Food is matched by **urgency and expiry**, not just proximity.
- High-need, time-sensitive requests are no longer overlooked.
- Routes are **realistic**: multi-depot, split-capable and time-window safe.
- A clean interface that donors, receivers and admins can use without training.
- Measurable improvement over a simple nearest-first baseline.

---

## 13. Member Checklist

**Member 1:** schema, auth, CRUD, scoring, matching, API docs, tests
**Member 2:** distance matrix, solver, splits, time windows, local search, baseline, tests
**Member 3:** design system, all pages, map, timeline, analytics, mock API, responsive polish

**Everyone:** PR reviews, integration testing, final report and demo.
