from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from backend.db.database import engine, Base, get_db
from backend.db.seed import seed_database
from backend.matching.auth import router as auth_router
from backend.matching.api import router as core_router

# Initialize database schema
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initializes tables and automatically seeds database if empty
    db = next(get_db())
    try:
        seed_database(db, reset=False)
    finally:
        db.close()
    yield

app = FastAPI(
    title="FoodRoute API",
    description="Smart Food Surplus Matching & Routing Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router)
app.include_router(core_router)

# Register Module 2 Routing Optimization Router
try:
    from backend.routing.api import router as routing_router
    app.include_router(routing_router)
except ImportError:
    from routing.api import router as routing_router
    app.include_router(routing_router)

@app.get("/")
def read_root():
    return {
        "name": "FoodRoute API",
        "status": "online",
        "version": "1.0.0",
        "documentation": "/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }

@app.post("/seed", tags=["Admin & Testing"])
def trigger_seed(reset: bool = True, db: Session = Depends(get_db)):
    """Resets and seeds database with initial test data."""
    seed_database(db, reset=reset)
    return {"message": "Database seeded successfully", "reset": reset}
