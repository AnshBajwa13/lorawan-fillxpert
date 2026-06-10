#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# FillXpert — One-command deploy script for AWS EC2 (Ubuntu 22.04)
# Run this ONCE after SSHing into your EC2 instance:
#   bash deploy.sh
# ──────────────────────────────────────────────────────────────────────────────

set -e   # stop on any error

echo ""
echo "=========================================="
echo "  FillXpert — Production Deploy"
echo "=========================================="

# 1. Install Docker if not already installed
if ! command -v docker &> /dev/null; then
    echo "[1/6] Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "      Docker installed. NOTE: Log out and back in if this is first install."
else
    echo "[1/6] Docker already installed — skipping"
fi

# 2. Install Docker Compose plugin if not present
if ! docker compose version &> /dev/null 2>&1; then
    echo "[2/6] Installing Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin
else
    echo "[2/6] Docker Compose already installed — skipping"
fi

# 3. Check .env exists
echo "[3/6] Checking .env file..."
if [ ! -f ".env" ]; then
    echo ""
    echo "  ERROR: .env file not found!"
    echo "  Create it first:"
    echo "    cp .env.example .env"
    echo "    nano .env          # fill in SECRET_KEY and passwords"
    echo ""
    exit 1
fi
echo "      .env found"

# 4. Build Docker images (bakes code into image)
echo "[4/6] Building Docker images..."
docker compose build --no-cache

# 5. Start all services
echo "[5/6] Starting services..."
docker compose up -d

# 6. Wait for backend to be ready and show status
echo "[6/6] Waiting for backend to start..."
sleep 8
docker compose ps

echo ""
echo "=========================================="
echo "  Deploy complete!"
echo "=========================================="
echo ""
echo "  Backend API : http://$(curl -s ifconfig.me):8000"
echo "  API docs    : http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f backend    # live backend logs"
echo "    docker compose logs -f           # all service logs"
echo "    docker compose restart backend   # restart backend"
echo "    docker compose down              # stop everything"
echo ""
