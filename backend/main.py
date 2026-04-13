import asyncio
import hashlib
import json
import random
import secrets
import threading
import uuid
import os
from datetime import datetime, timedelta, date
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Float, Text, UniqueConstraint, Index, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/takeoffcity")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class EventDB(Base):
    __tablename__ = "events"
    id                = Column(String, primary_key=True, index=True)
    name              = Column(String)
    earliest_date     = Column(String)
    latest_date       = Column(String)
    min_days          = Column(Integer, nullable=True)
    max_days          = Column(Integer, nullable=True)
    organiser_attends = Column(Boolean, default=False)
    calculated        = Column(Boolean, default=False)
    creator_username  = Column(String, default="")
    created_at        = Column(DateTime, default=datetime.utcnow)


class FeedbackDB(Base):
    __tablename__ = "feedbacks"
    id                   = Column(Integer, primary_key=True, index=True)
    event_id             = Column(String)
    city                 = Column(String)
    start_date           = Column(String, nullable=True)
    end_date             = Column(String, nullable=True)
    attendee_email       = Column(String, nullable=True)
    attendee_username    = Column(String, nullable=True)
    adults               = Column(Integer, default=1)
    children             = Column(Integer, default=0)
    availability_periods = Column(Text, nullable=True)
    edit_token           = Column(String, nullable=True, index=True)
    created_at           = Column(DateTime, default=datetime.utcnow)


class UserActivityDB(Base):
    __tablename__ = "user_activity"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, default="")
    action = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserDB(Base):
    __tablename__ = "users"
    id                = Column(Integer, primary_key=True, index=True)
    username          = Column(String, unique=True, index=True, nullable=False)
    email             = Column(String, unique=True, index=True, nullable=False)
    password_hash     = Column(String, nullable=False)
    created_at        = Column(DateTime, default=datetime.utcnow)
    terms_accepted_at = Column(DateTime, nullable=False)
    is_admin          = Column(Boolean, default=False)


class AirportCacheDB(Base):
    __tablename__ = "airport_cache"
    id           = Column(Integer, primary_key=True, index=True)
    city_query   = Column(String, nullable=False)    # normalised lowercase city name
    iata_code    = Column(String(3), nullable=False)
    airport_name = Column(String, nullable=False)
    city_name    = Column(String, nullable=False)    # as returned by API
    latitude     = Column(Float, nullable=False)
    longitude    = Column(Float, nullable=False)
    distance_km  = Column(Float, nullable=False)     # haversine from city centre
    radius_km    = Column(Integer, nullable=False)   # radius used in the search
    fetched_at   = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("city_query", "iata_code", "radius_km", name="uq_airport_cache"),
        Index("ix_airport_cache_city_radius", "city_query", "radius_km"),
    )


class FlightResultCacheDB(Base):
    __tablename__ = "flight_results_cache"
    id           = Column(Integer, primary_key=True, index=True)
    cache_key    = Column(String, nullable=False, unique=True)  # sha256 of query params
    fly_from     = Column(String, nullable=False)
    fly_to       = Column(String(3), nullable=False)
    date_from    = Column(String(10), nullable=False)
    date_to      = Column(String(10), nullable=False)
    result_json  = Column(Text, nullable=False)                 # full JSON blob from API
    fetched_at   = Column(DateTime, nullable=False)
    result_count = Column(Integer, nullable=False)


class CalculationResultDB(Base):
    __tablename__ = "calculation_results"
    id            = Column(Integer, primary_key=True, index=True)
    event_id      = Column(String, nullable=False, unique=True, index=True)
    result_json   = Column(Text, nullable=False)
    calculated_at = Column(DateTime, nullable=False)


Base.metadata.create_all(bind=engine)


# ── Password helpers ───────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260_000)
    return f"{salt}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, dk_hex = stored.split(':', 1)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260_000)
        return secrets.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


def seed_admin():
    db = SessionLocal()
    try:
        username = os.environ['WEB_ADMIN_USERNAME']
        password = os.environ['WEB_PASSWORD']
        email    = os.environ.get('WEB_ADMIN_EMAIL', f"{username}@admin.local")
        if not db.query(UserDB).filter(UserDB.username == username).first():
            db.add(UserDB(
                username=username,
                email=email,
                password_hash=hash_password(password),
                terms_accepted_at=datetime.utcnow(),
                is_admin=True,
            ))
            db.commit()
    finally:
        db.close()

import airports as airports_module
import calculate as calculate_module
import flights as flights_module
import tequila_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_admin()
    yield


app = FastAPI(title="TakeoffCity Backend", lifespan=lifespan)

ADMIN_USERS = {os.environ['WEB_ADMIN_USERNAME']}


# ── Pydantic models ────────────────────────────────────────────────────────────

def _validate_iso_date(v: str) -> str:
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError(f'"{v}" is not a valid YYYY-MM-DD date')
    return v


class EventCreate(BaseModel):
    name:              str
    earliest_date:     str
    latest_date:       str
    min_days:          Optional[int] = None
    max_days:          Optional[int] = None
    organiser_attends: bool = False

    @field_validator('earliest_date', 'latest_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        return _validate_iso_date(v)

    @model_validator(mode='after')
    def validate_date_order(self):
        if date.fromisoformat(self.earliest_date) > date.fromisoformat(self.latest_date):
            raise ValueError('earliest_date must not be after latest_date')
        return self


class FeedbackCreate(BaseModel):
    city:                 str
    start_date:           Optional[str] = None
    end_date:             Optional[str] = None
    attendee_email:       Optional[str] = None
    adults:               int = 1
    children:             int = 0
    availability_periods: Optional[str] = None

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _validate_iso_date(v)

    @model_validator(mode='after')
    def validate_date_order(self):
        if self.start_date and self.end_date:
            if date.fromisoformat(self.start_date) > date.fromisoformat(self.end_date):
                raise ValueError('start_date must not be after end_date')
        return self


class ActivityCreate(BaseModel):
    username: str
    action: str


class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class AuthVerify(BaseModel):
    username: str
    password: str


class PasswordUpdate(BaseModel):
    username: str
    current_password: str
    new_password: str


class EmailUpdate(BaseModel):
    username: str
    password: str
    new_email: str


class AccountDelete(BaseModel):
    username: str
    password: str


FUNNY_PHRASES = [
    "Retargeting the flux capacitor...",
    "Realigning the synergy matrices...",
    "Optimizing the coffee-to-code ratio...",
    "Downloading more RAM...",
    "Counting to infinity... twice.",
    "Bending the space-time continuum for your event...",
    "Consulting with the magic 8-ball...",
    "Applying some digital WD-40...",
    "Untangling the Ethernet cables...",
    "Calculating the meaning of life, the universe, and everything..."
]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Events ─────────────────────────────────────────────────────────────────────

@app.get("/events")
async def list_events(x_username: str = Header(default=""), db=Depends(get_db)):
    results = (
        db.query(EventDB, func.count(FeedbackDB.id).label('feedback_count'))
        .outerjoin(FeedbackDB, EventDB.id == FeedbackDB.event_id)
        .filter(EventDB.creator_username == x_username)
        .group_by(EventDB.id)
        .all()
    )
    return [{
        "id": e.id,
        "name": e.name,
        "earliest_date": e.earliest_date,
        "latest_date": e.latest_date,
        "feedback_count": count,
        "calculated": e.calculated
    } for e, count in results]


@app.post("/events")
async def create_event(event: EventCreate, x_username: str = Header(default=""), db=Depends(get_db)):
    event_id = str(uuid.uuid4())
    db.add(EventDB(
        id=event_id,
        name=event.name,
        earliest_date=event.earliest_date,
        latest_date=event.latest_date,
        min_days=event.min_days,
        max_days=event.max_days,
        organiser_attends=event.organiser_attends,
        creator_username=x_username,
    ))
    db.commit()
    return {"message": f"Event {event.name} created!", "event_id": event_id}


@app.get("/events/{event_id}")
async def get_event(event_id: str, x_username: str = Header(default=""), db=Depends(get_db)):
    result = (
        db.query(EventDB, func.count(FeedbackDB.id).label('feedback_count'))
        .outerjoin(FeedbackDB, EventDB.id == FeedbackDB.event_id)
        .filter(EventDB.id == event_id)
        .group_by(EventDB.id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    event, feedback_count = result
    return {
        "id": event.id,
        "name": event.name,
        "earliest_date": event.earliest_date,
        "latest_date": event.latest_date,
        "min_days": event.min_days,
        "max_days": event.max_days,
        "organiser_attends": event.organiser_attends,
        "feedback_count": feedback_count,
        "calculated": event.calculated,
        "is_owner": event.creator_username == x_username,
    }


@app.post("/events/{event_id}/feedback")
async def submit_feedback(
    event_id: str,
    feedback: FeedbackCreate,
    x_username: str = Header(default=""),
    db=Depends(get_db),
):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    edit_token = secrets.token_urlsafe(24)
    row = FeedbackDB(
        event_id=event_id,
        city=feedback.city,
        start_date=feedback.start_date,
        end_date=feedback.end_date,
        attendee_email=feedback.attendee_email or None,
        attendee_username=x_username or None,
        adults=feedback.adults,
        children=feedback.children,
        availability_periods=feedback.availability_periods,
        edit_token=edit_token,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"message": "Feedback submitted successfully", "feedback_id": row.id, "edit_token": edit_token}


@app.get("/events/{event_id}/responses")
async def list_responses(event_id: str, x_username: str = Header(default=""), db=Depends(get_db)):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.creator_username != x_username:
        raise HTTPException(status_code=403, detail="Not authorized")
    rows = db.query(FeedbackDB).filter(FeedbackDB.event_id == event_id).all()
    return [
        {
            "id": r.id,
            "identifier": r.attendee_username or r.attendee_email or "anonymous",
            "city": r.city,
            "adults": r.adults,
            "children": r.children,
            "availability_periods": r.availability_periods,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@app.delete("/events/{event_id}/responses/{feedback_id}")
async def delete_response(event_id: str, feedback_id: int, x_username: str = Header(default=""), db=Depends(get_db)):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.creator_username != x_username:
        raise HTTPException(status_code=403, detail="Not authorized")
    row = db.query(FeedbackDB).filter(FeedbackDB.id == feedback_id, FeedbackDB.event_id == event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Response not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@app.get("/events/{event_id}/feedback/edit/{token}")
async def get_feedback_by_token(event_id: str, token: str, db=Depends(get_db)):
    row = db.query(FeedbackDB).filter(
        FeedbackDB.event_id == event_id,
        FeedbackDB.edit_token == token,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "city": row.city,
        "adults": row.adults,
        "children": row.children,
        "availability_periods": row.availability_periods,
        "attendee_email": row.attendee_email,
    }


@app.put("/events/{event_id}/feedback/edit/{token}")
async def update_feedback_by_token(event_id: str, token: str, body: FeedbackCreate, db=Depends(get_db)):
    row = db.query(FeedbackDB).filter(
        FeedbackDB.event_id == event_id,
        FeedbackDB.edit_token == token,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    row.city = body.city
    row.adults = body.adults
    row.children = body.children
    row.availability_periods = body.availability_periods
    if body.attendee_email:
        row.attendee_email = body.attendee_email
    db.commit()
    return {"ok": True}


@app.delete("/events/{event_id}")
async def delete_event(event_id: str, x_username: str = Header(default=""), db=Depends(get_db)):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.creator_username != x_username:
        raise HTTPException(status_code=403, detail="Not authorized")
    db.delete(event)
    db.commit()
    return {"message": "Event deleted successfully"}


@app.post("/calculate/{event_id}")
async def calculate_event(event_id: str, db=Depends(get_db)):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def run():
            try:
                for line in calculate_module.run_calculation(event_id, SessionLocal):
                    loop.call_soon_threadsafe(queue.put_nowait, line)
            except Exception as exc:
                loop.call_soon_threadsafe(queue.put_nowait, f"Error: {exc}\n")
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        threading.Thread(target=run, daemon=True).start()

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(event_generator(), media_type="text/plain")


@app.get("/events/{event_id}/results")
async def get_event_results(event_id: str, db=Depends(get_db)):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    row = db.query(CalculationResultDB).filter_by(event_id=event_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="No results yet")
    return json.loads(row.result_json)


# ── Internal (server-to-server only, blocked at proxy) ────────────────────────

@app.post("/internal/activity")
async def record_activity(activity: ActivityCreate, db=Depends(get_db)):
    db.add(UserActivityDB(username=activity.username, action=activity.action))
    db.commit()
    return {"ok": True}


@app.post("/internal/users", status_code=201)
async def create_user(data: UserCreate, db=Depends(get_db)):
    if db.query(UserDB).filter(UserDB.username == data.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(UserDB).filter(UserDB.email == data.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    db.add(UserDB(
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        terms_accepted_at=datetime.utcnow(),
    ))
    db.commit()
    return {"ok": True}


@app.post("/internal/auth")
async def verify_auth(data: AuthVerify, db=Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"ok": True, "username": user.username}


@app.get("/internal/users/me")
async def get_user_me(username: str, db=Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "username": user.username,
        "email": user.email,
        "member_since": user.created_at.isoformat(),
    }


@app.put("/internal/users/me/password")
async def update_password(data: PasswordUpdate, db=Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == data.username).first()
    if not user or not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid current password")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"ok": True}


@app.put("/internal/users/me/email")
async def update_email(data: EmailUpdate, db=Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid password")
    if db.query(UserDB).filter(UserDB.email == data.new_email, UserDB.username != data.username).first():
        raise HTTPException(status_code=409, detail="Email already in use")
    user.email = data.new_email
    db.commit()
    return {"ok": True}


@app.delete("/internal/users/me")
async def delete_user(data: AccountDelete, db=Depends(get_db)):
    user = db.query(UserDB).filter(UserDB.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid password")
    db.query(EventDB).filter(EventDB.creator_username == data.username).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}


# ── Admin ──────────────────────────────────────────────────────────────────────

PERIOD_CONFIG = {
    '1h':  (timedelta(hours=1),  'minute'),
    '1d':  (timedelta(days=1),   'hour'),
    '5d':  (timedelta(days=5),   'day'),
    '30d': (timedelta(days=30),  'day'),
    '1y':  (timedelta(days=365), 'month'),
}


@app.get("/admin/stats")
async def admin_stats(period: str = '1d', x_username: str = Header(default=""), db=Depends(get_db)):
    if x_username not in ADMIN_USERS:
        raise HTTPException(status_code=403, detail="Admin only")

    delta, trunc_unit = PERIOD_CONFIG.get(period, PERIOD_CONFIG['1d'])
    since = datetime.utcnow() - delta

    total_groups     = db.query(func.count(EventDB.id)).scalar()
    total_calculated = db.query(func.count(EventDB.id)).filter(EventDB.calculated == True).scalar()
    unique_users     = db.query(func.count(func.distinct(EventDB.creator_username))).filter(EventDB.creator_username != '').scalar()
    total_feedback   = db.query(func.count(FeedbackDB.id)).scalar()

    period_groups     = db.query(func.count(EventDB.id)).filter(EventDB.created_at >= since).scalar()
    period_calculated = db.query(func.count(EventDB.id)).filter(EventDB.calculated == True, EventDB.created_at >= since).scalar()
    period_feedback   = db.query(func.count(FeedbackDB.id)).filter(FeedbackDB.created_at >= since).scalar()
    active_users      = db.query(func.count(func.distinct(UserActivityDB.username))).filter(
        UserActivityDB.created_at >= since,
        UserActivityDB.action == 'login'
    ).scalar()

    def time_series(time_col, extra_filter=None):
        bucket_expr = func.date_trunc(trunc_unit, time_col)
        q = db.query(bucket_expr.label('bucket'), func.count().label('count')).filter(time_col >= since)
        if extra_filter is not None:
            q = q.filter(extra_filter)
        rows = q.group_by(bucket_expr).order_by(bucket_expr).all()
        return [{'bucket': r.bucket.isoformat(), 'count': r.count} for r in rows]

    top_cities = db.query(FeedbackDB.city, func.count().label('count')).group_by(FeedbackDB.city).order_by(func.count().desc()).limit(10).all()

    return {
        'all_time': {
            'total_groups':     total_groups,
            'total_calculated': total_calculated,
            'unique_users':     unique_users,
            'total_feedback':   total_feedback,
        },
        'period': {
            'groups_created':    period_groups,
            'groups_calculated': period_calculated,
            'feedback_submitted': period_feedback,
            'active_users':      active_users,
        },
        'series': {
            'groups':   time_series(EventDB.created_at),
            'feedback': time_series(FeedbackDB.created_at),
            'logins':   time_series(UserActivityDB.created_at, UserActivityDB.action == 'login'),
        },
        'top_cities': [{'city': r.city, 'count': r.count} for r in top_cities],
    }


# ── Airport endpoints ──────────────────────────────────────────────────────────

@app.get("/airports")
def get_airports(city: str, radius_km: int = 200, db=Depends(get_db)):
    results, from_cache, fetched_at = airports_module.get_airports_for_city(city, db, radius_km)
    cache_age_hours = round((datetime.utcnow() - fetched_at).total_seconds() / 3600, 1) if from_cache else None
    return {
        "city":             city.strip().lower(),
        "radius_km":        radius_km,
        "airports":         results,
        "count":            len(results),
        "cached":           from_cache,
        "cache_age_hours":  cache_age_hours,
    }


class AirportRefreshRequest(BaseModel):
    city: str
    radius_km: int = 200


@app.post("/airports/refresh")
def refresh_airports(body: AirportRefreshRequest, db=Depends(get_db)):
    count = airports_module.refresh_airport_cache(body.city, db, body.radius_km)
    return {
        "city":           body.city.strip().lower(),
        "airports_found": count,
        "refreshed_at":   datetime.utcnow().isoformat(),
    }


# ── City search endpoint ───────────────────────────────────────────────────────

@app.get("/cities/search")
def search_cities(q: str, limit: int = 10):
    if not q or len(q.strip()) < 2:
        return {"cities": []}
    results = tequila_client.query_locations(q.strip(), location_types="city", limit=limit)
    return {"cities": [
        {
            "name": loc.get("name", ""),
            "country_code": loc.get("country", {}).get("code", ""),
            "id": loc.get("id", ""),
        }
        for loc in results
    ]}


# ── Flight search endpoint ─────────────────────────────────────────────────────

@app.get("/flights/search")
def search_flights(
    city: str,
    destination: str,
    date_from: str,
    date_to: str,
    radius_km: int = 200,
    curr: str = "EUR",
    db=Depends(get_db),
):
    date_from = _validate_iso_date(date_from)
    date_to   = _validate_iso_date(date_to)

    city_results = tequila_client.query_locations(city, location_types="city", limit=1)
    if not city_results:
        raise HTTPException(status_code=404, detail=f"City '{city}' not found")

    city_loc = city_results[0]
    city_lat = city_loc["location"]["lat"]
    city_lon = city_loc["location"]["lon"]

    fly_from     = f"circle:{city_lat},{city_lon}:{radius_km}km"
    fly_to_upper = destination.upper()

    results, from_cache, fetched_at = flights_module.search_flights_from_city(
        city_lat, city_lon, fly_to_upper, date_from, date_to, radius_km, curr, db
    )

    return {
        "fly_from":   fly_from,
        "fly_to":     fly_to_upper,
        "date_from":  date_from,
        "date_to":    date_to,
        "results":    results,
        "count":      len(results),
        "cached":     from_cache,
        "fetched_at": fetched_at.isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
