#!/bin/bash
# Complete Deployment Script for LoRaWAN System
# Run this on fillxpert.com server after uploading code

set -e  # Exit on error

echo "=============================================="
echo "🚀 LoRaWAN System Deployment"
echo "=============================================="

# Configuration
APP_DIR="/home/fillxper/lorawan"
DOMAIN="fillxpert.com"
DB_NAME="fillxper_lorawan"
DB_USER="fillxper_lorawan_user"
DB_PASS="LoRaWAN2026@Secure!"

echo ""
echo "📁 Step 1: Creating directory structure..."
mkdir -p $APP_DIR
cd $APP_DIR

echo ""
echo "📦 Step 2: Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "📥 Step 3: Installing Python dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt

echo ""
echo "⚙️  Step 4: Creating production .env file..."
cat > backend/.env << EOF
SECRET_KEY=puKxYXJKuw9rbiXBpu59I7rB56xhuXWWIN-hD3sjYtY
DATABASE_URL=mysql+pymysql://${DB_USER}:${DB_PASS}@localhost:3306/${DB_NAME}
REDIS_URL=redis://localhost:6379
ENVIRONMENT=production
ALLOWED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=noreply@${DOMAIN}
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
EOF

echo ""
echo "🗄️  Step 5: Setting up database tables..."
cd backend
python3 -c "
from database import Base, engine
from models import SensorReading
from models_auth import User, PasswordResetOTP
Base.metadata.create_all(bind=engine)
print('✅ All database tables created!')
"

echo ""
echo "🔧 Step 6: Installing PM2 (if not already installed)..."
if ! command -v pm2 &> /dev/null; then
    npm install -g pm2
fi

echo ""
echo "🚀 Step 7: Starting backend with PM2..."
cd $APP_DIR/backend
pm2 delete lorawan-backend 2>/dev/null || true
pm2 start "uvicorn app:app --host 0.0.0.0 --port 8000" --name lorawan-backend

echo ""
echo "🔄 Step 8: Starting Celery worker with PM2..."
pm2 delete lorawan-worker 2>/dev/null || true
pm2 start "celery -A tasks worker --loglevel=info" --name lorawan-worker

echo ""
echo "📦 Step 9: Installing frontend dependencies..."
cd $APP_DIR/frontend
npm install

echo ""
echo "🏗️  Step 10: Building frontend..."
npm run build

echo ""
echo "🌐 Step 11: Configuring Nginx..."
sudo tee /etc/nginx/sites-available/$DOMAIN > /dev/null << 'NGINXCONF'
server {
    listen 80;
    listen [::]:80;
    server_name fillxpert.com www.fillxpert.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name fillxpert.com www.fillxpert.com;
    
    # SSL certificate paths (adjust if needed)
    ssl_certificate /etc/letsencrypt/live/fillxpert.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fillxpert.com/privkey.pem;
    
    # Frontend - React build
    root /home/fillxper/lorawan/frontend/build;
    index index.html;
    
    # API proxy to backend
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
    
    # Serve static files
    location /static/ {
        alias /home/fillxper/lorawan/frontend/build/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # React routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINXCONF

# Enable site
sudo ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

echo ""
echo "💾 Step 12: Saving PM2 configuration..."
pm2 save
pm2 startup

echo ""
echo "=============================================="
echo "✅ DEPLOYMENT COMPLETE!"
echo "=============================================="
echo ""
echo "🌐 Your application is now live at:"
echo "   https://fillxpert.com"
echo ""
echo "🔧 Backend API running on:"
echo "   http://localhost:8000"
echo ""
echo "📊 PM2 Process Status:"
pm2 status

echo ""
echo "🔑 Test User Credentials:"
echo "   Username: admin"
echo "   Password: Admin@123"
echo ""
echo "📋 Useful Commands:"
echo "   pm2 logs lorawan-backend    # View backend logs"
echo "   pm2 logs lorawan-worker     # View worker logs"
echo "   pm2 restart all             # Restart all services"
echo "   pm2 stop all                # Stop all services"
echo ""
echo "🎉 Setup complete! Visit https://fillxpert.com"
