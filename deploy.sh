#!/bin/bash
# SignalForge — deploy script (runs on Hetzner server)
# Usage: ssh root@168.119.158.179 'bash /opt/signalforge/deploy.sh'

set -e
cd /opt/signalforge

echo "=== Pulling latest code ==="
git pull origin main

echo "=== Building containers ==="
docker compose -f docker-compose.prod.yml build

echo "=== Restarting services ==="
docker compose -f docker-compose.prod.yml up -d

echo "=== Waiting for health checks ==="
sleep 10
docker ps --format 'table {{.Names}}\t{{.Status}}'

echo "=== Deploy complete ==="
