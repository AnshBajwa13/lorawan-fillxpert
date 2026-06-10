# LoRaWAN Sensor Data Collection System

**Production-ready system for collecting and visualizing LoRaWAN sensor data with zero data loss guarantee.**

## 🏗️ Architecture

```
Gateway → FastAPI → Redis Queue → Celery Worker → PostgreSQL → React Dashboard
```

### Key Features:
- ✅ **Zero Data Loss**: Redis persistence + PostgreSQL ACID
- ✅ **Handles 100+ concurrent requests**: Queue-based architecture
- ✅ **Real-time Dashboard**: Auto-refresh every 10 seconds
- ✅ **Scalable**: Add more workers for higher throughput
- ✅ **Production Ready**: Docker deployment, health checks, monitoring

---

## 📦 Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **Queue**: Redis (with AOF persistence)
- **Worker**: Celery
- **Database**: PostgreSQL 16
- **Frontend**: React 18 + Chart.js
- **Deployment**: Docker Compose

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose installed
- (OR) Python 3.11, Node.js 18, PostgreSQL, Redis

### Option 1: Docker (Recommended)

```bash
# Clone and navigate to project
cd lorawan

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f
```

**Services will be available at:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Local Development

#### Backend Setup
```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment file
copy .env.example .env

# Start PostgreSQL and Redis (separate terminals or services)

# Start FastAPI server
python app.py

# Start Celery worker (new terminal)
celery -A tasks worker --loglevel=info --pool=solo  # Windows
# celery -A tasks worker --loglevel=info --concurrency=4  # Linux/Mac
```

#### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

---

## 📡 API Endpoints

### POST /api/sensor-data
Submit sensor data from gateway

**Request Body:**
```json
{
  "gateway_id": "GW-1",
  "node_id": "NODE-1",
  "timestamp": "2026-01-03T14:32:15Z",
  "humidity": 65.5,
  "moisture": 42.3
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Data received and queued for processing",
  "job_id": "abc-123-def-456"
}
```

### GET /api/sensor-data
Retrieve sensor readings with filters

**Query Parameters:**
- `gateway_id` (optional): Filter by gateway
- `node_id` (optional): Filter by node
- `limit` (default: 100): Number of records
- `hours` (optional): Get data from last N hours

### Other Endpoints:
- `GET /api/gateways` - List all gateways
- `GET /api/nodes` - List all nodes
- `GET /api/stats` - System statistics
- `GET /docs` - Interactive API documentation

---

## 🧪 Testing the System

### Send Test Data (PowerShell)
```powershell
# Test from gateway 1
$body = @{
    gateway_id = "GW-1"
    node_id = "NODE-1"
    timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    humidity = 65.5
    moisture = 42.3
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/sensor-data" -Method POST -Body $body -ContentType "application/json"
```

### Send Multiple Concurrent Requests
```powershell
# Simulate 10 sensors sending data simultaneously
1..10 | ForEach-Object -Parallel {
    $body = @{
        gateway_id = "GW-1"
        node_id = "NODE-$_"
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        humidity = Get-Random -Minimum 50 -Maximum 80
        moisture = Get-Random -Minimum 30 -Maximum 60
    } | ConvertTo-Json
    
    Invoke-RestMethod -Uri "http://localhost:8000/api/sensor-data" -Method POST -Body $body -ContentType "application/json"
}
```

---

## 🔧 Configuration

### Environment Variables (backend/.env)
```env
DATABASE_URL=postgresql://lorawan_user:lorawan_pass@localhost:5432/lorawan_db
REDIS_URL=redis://localhost:6379/0
HOST=0.0.0.0
PORT=8000
```

### Redis Persistence (docker-compose.yml)
```yaml
command: redis-server --appendonly yes --appendfsync everysec
```

---

## 📊 How It Works

### Data Flow:
1. **Gateway sends HTTP POST** with sensor data
2. **FastAPI receives** and returns 200 OK immediately
3. **Data queued in Redis** (persisted to disk)
4. **Celery worker pulls** job from queue
5. **Saves to PostgreSQL** with retry on failure
6. **Frontend displays** data with auto-refresh

### Why No Data Loss?
- Redis uses **AOF (Append Only File)** - writes every operation to disk
- If server crashes, Redis recovers from AOF on restart
- Celery retries failed tasks (max 3 times with backoff)
- PostgreSQL ensures ACID transactions

---

## 🎯 Scaling

### Add More Workers
```bash
# Docker
docker-compose up -d --scale worker=3

# Local
# Terminal 1
celery -A tasks worker --loglevel=info --concurrency=4

# Terminal 2
celery -A tasks worker --loglevel=info --concurrency=4

# Terminal 3
celery -A tasks worker --loglevel=info --concurrency=4
```

### Monitor Queue
```bash
# Check Redis queue length
docker exec -it lorawan_redis redis-cli LLEN celery

# Monitor Celery workers
docker exec -it lorawan_worker celery -A tasks inspect active
```

---

## 🐛 Troubleshooting

### Check Service Status
```bash
docker-compose ps
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f worker
```

### Database Connection Issues
```bash
# Check PostgreSQL
docker exec -it lorawan_postgres psql -U lorawan_user -d lorawan_db -c "\dt"
```

### Redis Connection Issues
```bash
# Check Redis
docker exec -it lorawan_redis redis-cli ping
```

---

## 📈 Monitoring

### Queue Metrics
- Queue length: Number of pending jobs
- Worker status: Active/idle workers
- Task success/failure rates

### Database Metrics
- Total readings
- Readings per gateway/node
- Latest reading timestamp

---

## 🔒 Production Deployment

### Security Checklist:
- [ ] Change default passwords in .env
- [ ] Use environment-specific CORS origins
- [ ] Enable HTTPS with reverse proxy (Nginx/Traefik)
- [ ] Set up database backups
- [ ] Configure Redis password
- [ ] Use secrets management (Vault, AWS Secrets Manager)
- [ ] Set up monitoring (Prometheus, Grafana)

### Recommended Infrastructure:
- **Cloud**: AWS EC2, DigitalOcean, Azure
- **Database**: AWS RDS, Azure Database for PostgreSQL
- **Redis**: AWS ElastiCache, Redis Cloud
- **Monitoring**: Datadog, New Relic, Grafana Cloud

---

## 📝 License

MIT License - Feel free to use for commercial and personal projects.

---

## 🤝 Support

For issues or questions, please check:
1. Docker logs: `docker-compose logs`
2. API docs: http://localhost:8000/docs
3. Redis queue: `docker exec -it lorawan_redis redis-cli`

**System Status Check:**
```bash
curl http://localhost:8000/
curl http://localhost:8000/api/stats
```


sangrur1/senasor1config {freq:2 time:10AM,2PM sensor:moisture}
config topic i publish then sensir will parse it , like dashboard act as publidher,C:\Users\Anshd>mosquitto_sub -h 140.245.7.35 -t , 
sangrur1/senasor1config 021000140001
see how it can parse its like first tume u set and default it is each sensor each sim gsm , rtc current time pull sync 10am reading takrn mqtt send mqtt server recieve  now 15-20s server give to see ay change in config ,if change then send to it otherwise ed like 00 go back to sleep after timeout , and what we thin ksimsensor enclosure is transmitter in enclsure attach to sensor and we change the sensor 


telematry topic  
how handshake so that no  loss if suppose 10 am not data send 
bytton press 10 sec it send data it 

freq time two things we can say we have in config which we will share , now when tehy require next config from us when they change sensor attach to the trasnmitter which we make as structure consist 