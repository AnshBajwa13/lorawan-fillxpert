from celery import Celery
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import SensorReading, Base
from config import get_settings
from datetime import datetime

settings = get_settings()

# Initialize Celery
celery_app = Celery(
    'lorawan_tasks',
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=4,  # Number of tasks to prefetch
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
)


@celery_app.task(bind=True, name='tasks.save_sensor_data', max_retries=3)
def save_sensor_data(self, data: dict):
    """
    Background task to save sensor data to database
    Retries up to 3 times on failure
    Includes user_id for multi-tenancy
    """
    db: Session = SessionLocal()
    try:
        # Create sensor reading object
        sensor_reading = SensorReading(
            user_id=data['user_id'],  # Multi-tenant support
            gateway_id=data['gateway_id'],
            node_id=data['node_id'],
            timestamp=datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00')),
            humidity=data.get('humidity'),
            moisture=data.get('moisture'),
            temperature=data.get('temperature'),
            battery_voltage=data.get('battery_voltage'),
            measurements=data.get('measurements')
        )
        
        # Add to database
        db.add(sensor_reading)
        db.commit()
        db.refresh(sensor_reading)
        
        return {
            'status': 'success',
            'id': sensor_reading.id,
            'gateway_id': sensor_reading.gateway_id,
            'node_id': sensor_reading.node_id
        }
    
    except Exception as e:
        db.rollback()
        # Retry the task with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    
    finally:
        db.close()


@celery_app.task(name='tasks.cleanup_old_data')
def cleanup_old_data(days: int = 90):
    """
    Periodic task to cleanup old data (optional)
    Can be scheduled to run monthly
    """
    from datetime import timedelta
    db: Session = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = db.query(SensorReading).filter(
            SensorReading.timestamp < cutoff_date
        ).delete()
        db.commit()
        return {'status': 'success', 'deleted_count': deleted_count}
    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


# Initialize database tables when worker starts
Base.metadata.create_all(bind=engine)
