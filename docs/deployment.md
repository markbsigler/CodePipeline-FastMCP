# FastMCP OpenAPI Server Deployment Guide

## Local Development
1. Copy example config files:
   ```sh
   cp config/.env.example config/.env
   cp config/openapi.json config/openapi.json
   ```
2. Install dependencies:
   ```sh
   npm install
   ```
3. Start the server:
   ```sh
   npm run dev
   ```

## Docker Deployment
1. Build and run with Docker Compose:
   ```sh
   docker-compose up --build
   ```
2. The server will be available at `http://localhost:8080`

## Production Deployment
- Set `NODE_ENV=production` in your `.env` file
- Use a strong `BEARER_TOKEN_SECRET`
- Mount your OpenAPI spec and config as volumes
- Use a reverse proxy (e.g., NGINX) for HTTPS
- Monitor health endpoints and logs

## Scaling & Monitoring
- Use Docker Swarm/Kubernetes for scaling
- Monitor with Prometheus/Grafana
- Enable audit logging

---
See `README.md` and `docs/api-reference.md` for more details.
