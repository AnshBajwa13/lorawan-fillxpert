#!/usr/bin/env python3
"""
Database Setup Script for LoRaWAN System on Production MySQL
Run this on the fillxpert.com server after uploading code
"""
import sys
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Production MySQL credentials
DB_CONFIG = {
    'host': 'localhost',
    'user': 'fillxper_lorawan_user',
    'password': 'LoRaWAN2026@Secure!',
    'database': 'fillxper_lorawan'
}

def create_tables():
    """Create all database tables"""
    print("🔧 Creating database tables...")
    
    # Connect with SQLAlchemy
    DATABASE_URL = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}/{DB_CONFIG['database']}"
    engine = create_engine(DATABASE_URL, echo=True)
    
    # Import models
    from database import Base
    from models import SensorReading
    from models_auth import User, PasswordResetOTP
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully!")
    
    return engine

def insert_sample_data(engine):
    """Insert sample data for testing"""
    print("\n📊 Inserting sample data...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        from models_auth import User
        from models import SensorReading
        from datetime import datetime, timedelta
        import bcrypt
        
        # Create sample user
        hashed_pw = bcrypt.hashpw("Test@123".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed_pw,
            full_name="Test User",
            is_active=True,
            is_verified=True
        )
        session.add(user)
        session.flush()  # Get user.id
        
        # Create sample sensor readings
        base_time = datetime.now()
        sample_readings = [
            {
                "gateway_id": "GATEWAY001",
                "node_id": "NODE001",
                "timestamp": base_time - timedelta(hours=2),
                "temperature": 25.5,
                "humidity": 65.2,
                "moisture": 45.8,
                "battery_voltage": 3.7,
                "measurements": {"npk_n": 45.2, "npk_p": 23.1, "npk_k": 38.7, "ph": 6.8}
            },
            {
                "gateway_id": "GATEWAY001",
                "node_id": "NODE001",
                "timestamp": base_time - timedelta(hours=1),
                "temperature": 26.1,
                "humidity": 64.8,
                "moisture": 46.2,
                "battery_voltage": 3.7,
                "measurements": {"npk_n": 46.1, "npk_p": 23.5, "npk_k": 39.2, "ph": 6.9}
            },
            {
                "gateway_id": "GATEWAY001",
                "node_id": "NODE002",
                "timestamp": base_time - timedelta(minutes=30),
                "temperature": 24.8,
                "humidity": 66.5,
                "moisture": 44.5,
                "battery_voltage": 3.6,
                "measurements": {"npk_n": 42.8, "npk_p": 21.9, "npk_k": 37.3, "ph": 6.7}
            }
        ]
        
        for reading_data in sample_readings:
            reading = SensorReading(user_id=user.id, **reading_data)
            session.add(reading)
        
        session.commit()
        print(f"✅ Created user: {user.username} (ID: {user.id})")
        print(f"✅ Created {len(sample_readings)} sample sensor readings")
        print(f"\n🔑 Login credentials:")
        print(f"   Username: testuser")
        print(f"   Password: Test@123")
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()

def show_database_info():
    """Show database structure"""
    print("\n" + "="*60)
    print("📋 DATABASE STRUCTURE")
    print("="*60)
    
    print("\n1️⃣  USERS TABLE")
    print("   Columns:")
    print("   - id (INT, PRIMARY KEY, AUTO_INCREMENT)")
    print("   - username (VARCHAR(50), UNIQUE, NOT NULL)")
    print("   - email (VARCHAR(255), UNIQUE, NOT NULL)")
    print("   - hashed_password (VARCHAR(255), NOT NULL)")
    print("   - full_name (VARCHAR(100))")
    print("   - is_active (BOOLEAN, DEFAULT TRUE)")
    print("   - is_verified (BOOLEAN, DEFAULT TRUE)")
    print("   - created_at (DATETIME, DEFAULT NOW)")
    print("   - updated_at (DATETIME, DEFAULT NOW)")
    
    print("\n2️⃣  PASSWORD_RESET_OTPS TABLE")
    print("   Columns:")
    print("   - id (INT, PRIMARY KEY, AUTO_INCREMENT)")
    print("   - email (VARCHAR(255), NOT NULL)")
    print("   - otp_code (VARCHAR(6), NOT NULL)")
    print("   - is_used (BOOLEAN, DEFAULT FALSE)")
    print("   - expires_at (DATETIME, NOT NULL)")
    print("   - created_at (DATETIME, DEFAULT NOW)")
    
    print("\n3️⃣  SENSOR_READINGS TABLE (Multi-Tenant)")
    print("   Columns:")
    print("   - id (INT, PRIMARY KEY, AUTO_INCREMENT)")
    print("   - user_id (INT, FOREIGN KEY -> users.id, NOT NULL)")
    print("   - gateway_id (VARCHAR(50), NOT NULL)")
    print("   - node_id (VARCHAR(50), NOT NULL)")
    print("   - timestamp (DATETIME, NOT NULL)")
    print("   - temperature (FLOAT)")
    print("   - humidity (FLOAT)")
    print("   - moisture (FLOAT)")
    print("   - battery_voltage (FLOAT)")
    print("   - measurements (JSON) - for dynamic fields")
    print("   - created_at (DATETIME, DEFAULT NOW)")
    print("   Indexes:")
    print("   - idx_user_gateway_node_timestamp")
    print("   - idx_user_timestamp")

def show_gateway_example():
    """Show example of data gateway will send"""
    print("\n" + "="*60)
    print("📡 GATEWAY DATA FORMAT")
    print("="*60)
    
    print("\n🔧 API Endpoint: POST https://fillxpert.com/api/sensor_readings")
    print("\n🔑 Authentication: Bearer Token in Authorization header")
    print("   Authorization: Bearer <JWT_TOKEN>")
    
    print("\n📤 Request Body (JSON):")
    print('''
{
  "gateway_id": "GATEWAY001",
  "node_id": "NODE001",
  "timestamp": "2026-01-08T10:30:00",
  "temperature": 25.5,
  "humidity": 65.2,
  "moisture": 45.8,
  "battery_voltage": 3.7,
  "measurements": {
    "npk_n": 45.2,
    "npk_p": 23.1,
    "npk_k": 38.7,
    "ph": 6.8,
    "ec": 1.2
  }
}
''')
    
    print("📝 Field Descriptions:")
    print("   - gateway_id: Unique identifier for gateway device")
    print("   - node_id: Unique identifier for sensor node")
    print("   - timestamp: ISO format datetime when reading was taken")
    print("   - temperature: Temperature in Celsius (optional)")
    print("   - humidity: Relative humidity % (optional)")
    print("   - moisture: Soil moisture % (optional)")
    print("   - battery_voltage: Battery voltage in volts (optional)")
    print("   - measurements: JSON object for any additional sensors")
    print("                  (NPK, pH, EC, light, etc.)")
    
    print("\n✅ Success Response (200):")
    print('''
{
  "id": 123,
  "message": "Sensor reading created successfully"
}
''')
    
    print("\n🚫 Queuing System:")
    print("   - If 6+ requests come simultaneously:")
    print("   - Backend uses Celery queue with Redis")
    print("   - All requests accepted immediately (202)")
    print("   - Processed in background without blocking")
    print("   - No crashes, automatic retry on failure")

if __name__ == "__main__":
    print("="*60)
    print("🚀 LoRaWAN Database Setup - Production")
    print("="*60)
    
    show_database_info()
    show_gateway_example()
    
    print("\n" + "="*60)
    print("🔧 Ready to create tables?")
    print("="*60)
    
    response = input("\nCreate tables now? (yes/no): ").lower()
    if response == 'yes':
        engine = create_tables()
        
        response2 = input("\nInsert sample data? (yes/no): ").lower()
        if response2 == 'yes':
            insert_sample_data(engine)
        
        print("\n✅ Database setup complete!")
        print("🌐 Your system is ready at: https://fillxpert.com")
    else:
        print("\n⏭️  Skipped. Run this script again when ready.")
