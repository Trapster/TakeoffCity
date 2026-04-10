import asyncio
import random
import uuid
import os
from datetime import datetime, timedelta, date
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, func
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/takeoffcity")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class EventDB(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    earliest_date = Column(String)
    latest_date = Column(String)
    calculated = Column(Boolean, default=False)
    creator_username = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class FeedbackDB(Base):
    __tablename__ = "feedbacks"
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String)
    city = Column(String)
    start_date = Column(String)
    end_date = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserActivityDB(Base):
    __tablename__ = "user_activity"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, default="")
    action = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

app = FastAPI(title="TakeoffCity Backend")

ADMIN_USERS = {'jame'}


# ── Pydantic models ────────────────────────────────────────────────────────────

def _validate_iso_date(v: str) -> str:
    try:
        date.fromisoformat(v)
    except ValueError:
        raise ValueError(f'"{v}" is not a valid YYYY-MM-DD date')
    return v


class EventCreate(BaseModel):
    name: str
    earliest_date: str
    latest_date: str

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
    city: str
    start_date: str
    end_date: str

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date(cls, v: str) -> str:
        return _validate_iso_date(v)

    @model_validator(mode='after')
    def validate_date_order(self):
        if date.fromisoformat(self.start_date) > date.fromisoformat(self.end_date):
            raise ValueError('start_date must not be after end_date')
        return self


class ActivityCreate(BaseModel):
    username: str
    action: str


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
        "feedback_count": feedback_count,
        "calculated": event.calculated,
        "is_owner": event.creator_username == x_username,
    }


@app.post("/events/{event_id}/feedback")
async def submit_feedback(event_id: str, feedback: FeedbackCreate, db=Depends(get_db)):
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.add(FeedbackDB(
        event_id=event_id,
        city=feedback.city,
        start_date=feedback.start_date,
        end_date=feedback.end_date,
    ))
    db.commit()
    return {"message": "Feedback submitted successfully"}


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

    event.calculated = True
    db.commit()

    async def event_generator():
        for i in range(5):
            await asyncio.sleep(2)
            yield f"Step {i+1}: {random.choice(FUNNY_PHRASES)}\n"
        yield "Calculation complete! Your event is ready for takeoff.\n"

    return StreamingResponse(event_generator(), media_type="text/plain")


# ── Internal (server-to-server only, blocked at proxy) ────────────────────────

@app.post("/internal/activity")
async def record_activity(activity: ActivityCreate, db=Depends(get_db)):
    db.add(UserActivityDB(username=activity.username, action=activity.action))
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
