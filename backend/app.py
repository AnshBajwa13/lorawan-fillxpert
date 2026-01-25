from fastapi import FastAPI, Depends, HTTPException, Query, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import List, Optional
from datetime import datetime, timedelta

from database import get_db, init_db
from models import SensorReading
from schemas import SensorDataInput, SensorDataResponse, SensorReadingOutput
from auth import get_current_user, get_current_user_optional
from models_auth import User, APIKey

# Try to import Celery tasks, fallback to direct save if not available
try:
    from tasks import save_sensor_data
    CELERY_AVAILABLE = True
    print(" Celery tasks imported successfully")
except Exception as e:
    print(f"  Celery not available: {e}")
    print("   Using direct database saves (no background processing)")
    CELERY_AVAILABLE = False
    save_sensor_data = None  # Set to None to avoid NameError

# Import authentication router
from routers.auth import router as auth_router

# Import rate limiter
from rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded  # type: ignore

# Initialize FastAPI app
app = FastAPI(
    title="LoRaWAN Data Collection API",
    description="Production-ready API for collecting and managing LoRaWAN sensor data with authentication",
    version="2.0.0"
)

# Add rate limiter state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# CORS configuration - allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include authentication routes
app.include_router(auth_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print(" Database initialized successfully")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "LoRaWAN Data Collection API",
        "version": "1.0.0"
    }


@app.post("/api/sensor-data", response_model=SensorDataResponse)
async def receive_sensor_data(
    data: SensorDataInput, 
    db: Session = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Endpoint to receive sensor data from gateway.
    
    DUAL AUTHENTICATION (either works):
    1. X-API-Key header (recommended for gateways) - never expires
    2. Bearer token (used by frontend) - expires in 1 hour
    
    Example with API Key:
        curl -X POST https://api.example.com/api/sensor-data \\
             -H "X-API-Key: lora_your_key_here" \\
             -H "Content-Type: application/json" \\
             -d '{"gateway_id": "gw01", "node_id": "sensor01", ...}'
    
    Example with Bearer Token:
        curl -X POST https://api.example.com/api/sensor-data \\
             -H "Authorization: Bearer eyJhbGciOiJI..." \\
             -H "Content-Type: application/json" \\
             -d '{"gateway_id": "gw01", "node_id": "sensor01", ...}'
    """
    user = None
    
    # Try API Key first (preferred for gateways)
    if x_api_key:
        api_key = db.query(APIKey).filter(
            APIKey.key_value == x_api_key,
            APIKey.is_active == True
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid or inactive API key"
            )
        
        # Check if key is expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="API key has expired"
            )
        
        # Update last_used_at timestamp
        api_key.last_used_at = datetime.utcnow()
        db.commit()
        
        # Get user from API key
        user = db.query(User).filter(User.id == api_key.user_id).first()
        
    # Fall back to Bearer token
    elif current_user:
        user = current_user
    
    # No authentication provided
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide X-API-Key header or Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        if CELERY_AVAILABLE:
            try:
                # Try Celery queue (non-blocking)
                data_dict = data.model_dump()
                data_dict['timestamp'] = data.timestamp.isoformat()
                data_dict['user_id'] = user.id
                task = save_sensor_data.delay(data_dict)
                
                return SensorDataResponse(
                    status="success",
                    message="Data received and queued for processing",
                    job_id=task.id
                )
            except Exception as celery_error:
                # Celery failed (Redis down?), fall back to direct save
                print(f"⚠️ Celery failed, using direct save: {celery_error}")
        
        # Direct database save (no Celery or Celery failed)
        reading = SensorReading(
            user_id=user.id,
            gateway_id=data.gateway_id,
            node_id=data.node_id,
            timestamp=data.timestamp,
            humidity=data.humidity,
            moisture=data.moisture,
            temperature=data.temperature,
            battery_voltage=data.battery_voltage,
            measurements=data.measurements
        )
        db.add(reading)
        db.commit()
        db.refresh(reading)
        
        return SensorDataResponse(
            status="success",
            message="Data saved successfully",
            job_id=None
        )
    
    except Exception as e:
        if db:
            db.rollback()
        print(f"❌ Error saving sensor data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save data: {str(e)}")


@app.get("/api/sensor-data", response_model=List[SensorReadingOutput])
async def get_sensor_data(
    gateway_id: Optional[str] = Query(None, description="Filter by gateway ID"),
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    hours: Optional[int] = Query(None, ge=1, description="Get data from last N hours"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get sensor readings with optional filters
    - Only returns data for the logged-in user (multi-tenant)
    """
    # Base query - filter by user
    query = db.query(SensorReading).filter(SensorReading.user_id == current_user.id)
    
    # Apply additional filters
    filters = []
    if gateway_id:
        filters.append(SensorReading.gateway_id == gateway_id)
    if node_id:
        filters.append(SensorReading.node_id == node_id)
    if hours:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filters.append(SensorReading.timestamp >= cutoff_time)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Order by timestamp descending (newest first)
    query = query.order_by(desc(SensorReading.timestamp))
    
    # Apply pagination
    readings = query.offset(skip).limit(limit).all()
    
    return readings


@app.get("/api/gateways", response_model=List[str])
async def get_gateways(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all unique gateway IDs for current user"""
    gateways = db.query(SensorReading.gateway_id)\
        .filter(SensorReading.user_id == current_user.id)\
        .distinct().all()
    return [g[0] for g in gateways]


@app.get("/api/nodes", response_model=List[str])
async def get_nodes(
    gateway_id: Optional[str] = Query(None, description="Filter nodes by gateway"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all unique node IDs for current user, optionally filtered by gateway"""
    query = db.query(SensorReading.node_id)\
        .filter(SensorReading.user_id == current_user.id)\
        .distinct()
    
    if gateway_id:
        query = query.filter(SensorReading.gateway_id == gateway_id)
    
    nodes = query.all()
    return [n[0] for n in nodes]


@app.get("/api/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get statistics for current user's data"""
    total_readings = db.query(SensorReading)\
        .filter(SensorReading.user_id == current_user.id)\
        .count()
    total_gateways = db.query(SensorReading.gateway_id)\
        .filter(SensorReading.user_id == current_user.id)\
        .distinct().count()
    total_nodes = db.query(SensorReading.node_id)\
        .filter(SensorReading.user_id == current_user.id)\
        .distinct().count()
    
    latest_reading = db.query(SensorReading)\
        .filter(SensorReading.user_id == current_user.id)\
        .order_by(desc(SensorReading.timestamp))\
        .first()
    
    return {
        "total_readings": total_readings,
        "total_gateways": total_gateways,
        "total_nodes": total_nodes,
        "latest_reading_time": latest_reading.timestamp.isoformat() if latest_reading else None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
