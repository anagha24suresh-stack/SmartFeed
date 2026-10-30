# FoodRoute Shared API Contract & Data Models

This contract defines the shared data schemas, request/response formats, authentication conventions, and endpoints implemented in **Module 1 (Data, Auth, and Urgency Matching)** and consumed by **Module 2 (Routing Optimization Engine)** and **Module 3 (Frontend UI/UX)**.

---

## 1. Authentication & Security

FoodRoute uses JWT (JSON Web Token) bearer authentication.
- Header format: `Authorization: Bearer <access_token>`
- Roles: `donor`, `receiver`, `admin`

### 1.1 Register
`POST /auth/register`
- **Request Body:**
```json
{
  "username": "greenleaf",
  "email": "donations@greenleaf.com",
  "password": "donor123",
  "role": "donor"
}
```
- **Response (201 Created):**
```json
{
  "id": 2,
  "username": "greenleaf",
  "email": "donations@greenleaf.com",
  "role": "donor",
  "created_at": "2026-11-05T10:00:00"
}
```

### 1.2 Login
`POST /auth/login`
- **Request Body:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```
- **Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "role": "admin",
  "username": "admin"
}
```

### 1.3 Current User Profile
`GET /auth/me`
- Requires `Authorization: Bearer <token>` header.
- **Response (200 OK):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@foodroute.org",
  "role": "admin",
  "created_at": "2026-11-05T09:00:00"
}
```

---

## 2. Core Entities & CRUD

### 2.1 Donations
Represents surplus food offered by food donors (restaurants, banquets, grocery stores, corporate cafeterias).

- `GET /donations`: List all donations (Optional query filters: `?status=open&food_type=Cooked Meals`)
- `POST /donations`: Create a new donation
- `GET /donations/{id}`: Retrieve a single donation
- `PUT /donations/{id}`: Update a donation
- `DELETE /donations/{id}`: Remove a donation

**Create Donation Request:**
```json
{
  "donor_name": "Green Leaf Restaurant",
  "food_type": "Cooked Meals (Rice, Curry & Dal)",
  "quantity_kg": 40.0,
  "location": {
    "lat": 12.9750,
    "lng": 77.6050
  },
  "ready_time": "2026-11-05T12:00:00",
  "expiry_time": "2026-11-05T15:30:00",
  "pickup_window": {
    "start": "12:00",
    "end": "14:30"
  }
}
```

**Donation Response Object:**
```json
{
  "id": 1,
  "donor_name": "Green Leaf Restaurant",
  "food_type": "Cooked Meals (Rice, Curry & Dal)",
  "quantity_kg": 40.0,
  "remaining_kg": 40.0,
  "location": {
    "lat": 12.9750,
    "lng": 77.6050
  },
  "ready_time": "2026-11-05T12:00:00",
  "expiry_time": "2026-11-05T15:30:00",
  "pickup_window": {
    "start": "12:00",
    "end": "14:30"
  },
  "status": "open"
}
```

---

### 2.2 Requests
Represents food assistance requests submitted by receivers (shelters, orphanages, elder care facilities, community food banks).

- `GET /requests`: List requests (Optional query filters: `?status=open&min_need=3`)
- `POST /requests`: Create a new food request
- `GET /requests/{id}`: Retrieve a single request
- `PUT /requests/{id}`: Update a request
- `DELETE /requests/{id}`: Remove a request

**Create Request Payload:**
```json
{
  "receiver_name": "Hope Night Shelter",
  "quantity_kg": 60.0,
  "location": {
    "lat": 12.9344,
    "lng": 77.6101
  },
  "delivery_window": {
    "start": "14:00",
    "end": "17:00"
  },
  "need_level": 5
}
```

**Request Response Object:**
```json
{
  "id": 1,
  "receiver_name": "Hope Night Shelter",
  "quantity_kg": 60.0,
  "remaining_kg": 60.0,
  "location": {
    "lat": 12.9344,
    "lng": 77.6101
  },
  "delivery_window": {
    "start": "14:00",
    "end": "17:00"
  },
  "need_level": 5,
  "status": "open"
}
```

---

### 2.3 Depots & Fleet Vehicles (Admin Setup)

- `GET /depots` & `POST /depots`: List and register distribution hubs.
- `GET /vehicles` & `POST /vehicles`: List and register vehicles.

**Depot Schema:**
```json
{
  "id": 1,
  "name": "North Bangalore Depot (Hebbal)",
  "location": {
    "lat": 13.0358,
    "lng": 77.5970
  }
}
```

**Vehicle Schema:**
```json
{
  "id": 1,
  "depot_id": 1,
  "capacity_kg": 120.0,
  "available_from": "08:00",
  "available_to": "20:00",
  "is_active": true
}
```

---

## 3. Urgency Scoring & Priority Matching (Module 1 Core)

### 3.1 Urgency Scores Calculation
`GET /scores`
Computes real-time urgency metrics across all open donations and requests with full parameter breakdowns.

**Response Structure (200 OK):**
```json
{
  "timestamp": "2026-11-05T12:00:00Z",
  "donations": [
    {
      "id": 11,
      "donor_name": "Saffron Dine Catering",
      "food_type": "Cooked Meals (South Indian Thali)",
      "quantity_kg": 45.0,
      "time_left_hours": 2.0,
      "expiry_pressure": 0.9167,
      "quantity_weight": 0.45,
      "pickup_window_tightness": 0.9375,
      "urgency_score": 0.7788
    }
  ],
  "requests": [
    {
      "id": 1,
      "receiver_name": "Hope Night Shelter",
      "quantity_kg": 60.0,
      "need_level": 5,
      "need_level_norm": 1.0,
      "window_tightness": 0.875,
      "waiting_time_norm": 0.3333,
      "urgency_score": 0.8292
    }
  ]
}
```

### 3.2 Execute Matching
`POST /matching/run`
Runs the urgency-based priority matching algorithm, executes greedy split allocation, writes matches and unmatched items to the database, and returns execution metrics.

**Response Structure (200 OK):**
```json
{
  "batch_id": "a9f3b12c",
  "executed_at": "2026-11-05T12:00:01Z",
  "execution_time_ms": 18.5,
  "total_donations_evaluated": 12,
  "total_requests_evaluated": 12,
  "total_allocated_kg": 485.0,
  "matches_count": 15,
  "unmatched_count": 2,
  "matches": [
    {
      "match_id": 1,
      "donation_id": 11,
      "request_id": 1,
      "donor_name": "Saffron Dine Catering",
      "receiver_name": "Hope Night Shelter",
      "food_type": "Cooked Meals (South Indian Thali)",
      "allocated_kg": 45.0,
      "priority_score": 0.642
    }
  ],
  "unmatched": [
    {
      "item_type": "donation",
      "item_id": 10,
      "item_name": "BigBasket Fulfillment Hub",
      "unallocated_kg": 25.0,
      "reason": "No matching demand available for surplus quantity"
    }
  ]
}
```

### 3.3 Latest Matches for Routing (Module 2 Input)
`GET /matching/results`
Returns the latest match batch with enriched geographic coordinates, ready/expiry timestamps, and pickup/delivery windows required by Module 2's routing solver.

**Response Structure (200 OK):**
```json
{
  "batch_id": "a9f3b12c",
  "matches_count": 15,
  "unmatched_count": 2,
  "matches": [
    {
      "match_id": 1,
      "donation_id": 11,
      "request_id": 1,
      "donor_name": "Saffron Dine Catering",
      "receiver_name": "Hope Night Shelter",
      "food_type": "Cooked Meals (South Indian Thali)",
      "allocated_kg": 45.0,
      "priority_score": 0.642,
      "donation_location": { "lat": 12.9116, "lng": 77.6012 },
      "request_location": { "lat": 12.9344, "lng": 77.6101 },
      "ready_time": "2026-11-05T12:00:00",
      "expiry_time": "2026-11-05T14:00:00",
      "pickup_window": { "start": "13:00", "end": "14:30" },
      "delivery_window": { "start": "14:00", "end": "17:00" }
    }
  ],
  "unmatched": [
    {
      "item_type": "donation",
      "item_id": 10,
      "item_name": "BigBasket Fulfillment Hub",
      "unallocated_kg": 25.0,
      "reason": "No matching demand available for surplus quantity"
    }
  ]
}
```

---

## 4. Reset & Seeding Utility
`POST /seed?reset=true`
Re-initializes the database and seeds 3 users, 3 depots, 5 vehicles, 12 donations, and 12 requests.
