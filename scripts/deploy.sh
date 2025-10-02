#!/bin/bash
# Production deployment script for BMC AMI DevX Code Pipeline MCP Server
# Handles Docker build, deployment, health checks, and rollback capabilities

set -e

# Configuration
IMAGE_NAME="fastmcp-code-pipeline"
CONTAINER_NAME="fastmcp-server"
DOCKER_COMPOSE_FILE="docker-compose.yml"
HEALTH_ENDPOINT="http://localhost:8080/health"
HEALTH_TIMEOUT=60
BACKUP_TAG="backup-$(date +%Y%m%d-%H%M%S)"
SERVER_FILE="openapi_server.py"

echo "🚀 BMC AMI DevX Code Pipeline MCP Server Deployment"
echo "==================================================="

# Check deployment mode
DEPLOYMENT_MODE=${1:-"compose"}
if [ "$DEPLOYMENT_MODE" != "compose" ] && [ "$DEPLOYMENT_MODE" != "docker" ]; then
    echo "Usage: $0 [compose|docker]"
    echo "  compose - Deploy using docker-compose (recommended)"
    echo "  docker  - Deploy using plain Docker commands"
    exit 1
fi

echo "📋 Deployment mode: $DEPLOYMENT_MODE"
echo "📁 Server file: $SERVER_FILE"

# Pre-deployment checks
echo "🔍 Running pre-deployment checks..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running or not accessible"
    exit 1
fi

echo "✅ Docker is available"

# Check required files
REQUIRED_FILES=("Dockerfile" "openapi_server.py" "requirements.txt" "config/openapi.json")
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file missing: $file"
        exit 1
    fi
done

echo "✅ All required files present"

# Backup existing image if it exists
if docker image inspect "$IMAGE_NAME:latest" >/dev/null 2>&1; then
    echo "💾 Backing up existing image..."
    docker tag "$IMAGE_NAME:latest" "$IMAGE_NAME:$BACKUP_TAG"
    echo "✅ Backup created: $IMAGE_NAME:$BACKUP_TAG"
fi

# Deploy based on mode
if [ "$DEPLOYMENT_MODE" = "compose" ]; then
    echo "🐳 Deploying with Docker Compose..."

    # Check if docker-compose file exists
    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        echo "❌ Docker Compose file not found: $DOCKER_COMPOSE_FILE"
        exit 1
    fi

    # Stop existing services
    if docker-compose ps | grep -q "$CONTAINER_NAME"; then
        echo "🛑 Stopping existing services..."
        docker-compose down
    fi

    # Build and start services
    echo "🔨 Building and starting services..."
    docker-compose up --build -d

    # Get container ID for health check
    CONTAINER_ID=$(docker-compose ps -q)

else
    echo "🐳 Deploying with Docker..."

    # Stop and remove existing container
    if docker ps -a | grep -q "$CONTAINER_NAME"; then
        echo "🛑 Stopping existing container..."
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
    fi

    # Build new image
    echo "🔨 Building Docker image..."
    docker build -t "$IMAGE_NAME:latest" .

    # Run new container
    echo "🚀 Starting new container..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p 8080:8080 \
        --restart unless-stopped \
        "$IMAGE_NAME:latest"

    CONTAINER_ID="$CONTAINER_NAME"
fi

echo "✅ Container started: $CONTAINER_ID"

# Health check with timeout
echo "🏥 Performing health check (timeout: ${HEALTH_TIMEOUT}s)..."
HEALTH_CHECK_START=$(date +%s)

while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - HEALTH_CHECK_START))

    if [ $ELAPSED -gt $HEALTH_TIMEOUT ]; then
        echo "❌ Health check timeout after ${HEALTH_TIMEOUT}s"
        echo "📋 Container logs:"
        if [ "$DEPLOYMENT_MODE" = "compose" ]; then
            docker-compose logs --tail=50
        else
            docker logs --tail=50 "$CONTAINER_NAME"
        fi

        # Rollback if backup exists
        if docker image inspect "$IMAGE_NAME:$BACKUP_TAG" >/dev/null 2>&1; then
            echo "🔄 Rolling back to previous version..."
            if [ "$DEPLOYMENT_MODE" = "compose" ]; then
                docker-compose down
                docker tag "$IMAGE_NAME:$BACKUP_TAG" "$IMAGE_NAME:latest"
                docker-compose up -d
            else
                docker stop "$CONTAINER_NAME" || true
                docker rm "$CONTAINER_NAME" || true
                docker tag "$IMAGE_NAME:$BACKUP_TAG" "$IMAGE_NAME:latest"
                docker run -d --name "$CONTAINER_NAME" -p 8080:8080 "$IMAGE_NAME:latest"
            fi
            echo "✅ Rollback completed"
        fi
        exit 1
    fi

    # Check if container is still running
    if [ "$DEPLOYMENT_MODE" = "compose" ]; then
        if ! docker-compose ps | grep -q "Up"; then
            echo "❌ Container stopped unexpectedly"
            docker-compose logs --tail=50
            exit 1
        fi
    else
        if ! docker ps | grep -q "$CONTAINER_NAME"; then
            echo "❌ Container stopped unexpectedly"
            docker logs --tail=50 "$CONTAINER_NAME"
            exit 1
        fi
    fi

    # Check health endpoint
    if curl -s --max-time 5 "$HEALTH_ENDPOINT" | grep -q "healthy"; then
        echo "✅ Health check passed!"
        break
    fi

    echo "⏳ Waiting for service... (${ELAPSED}s/${HEALTH_TIMEOUT}s)"
    sleep 5
done

# Final verification
echo "🔍 Final deployment verification..."

# Test FastMCP endpoints
echo "📋 Testing FastMCP endpoints..."
if curl -s --max-time 5 "http://localhost:8080/health" | grep -q "healthy"; then
    echo "✅ Health endpoint accessible"
else
    echo "⚠️  Health endpoint not responding"
fi

if curl -s --max-time 5 "http://localhost:8080/status" >/dev/null; then
    echo "✅ Status endpoint accessible"
else
    echo "⚠️  Status endpoint not responding"
fi

if curl -s --max-time 5 "http://localhost:8080/mcp/capabilities" >/dev/null; then
    echo "✅ MCP capabilities endpoint accessible"
else
    echo "⚠️  MCP capabilities endpoint not responding"
fi

# Test observability endpoints
echo "📊 Testing observability endpoints..."
if curl -s --max-time 5 "http://localhost:8080/metrics" >/dev/null; then
    echo "✅ Prometheus metrics endpoint accessible"
else
    echo "⚠️  Prometheus metrics endpoint not responding"
fi

if curl -s --max-time 5 "http://localhost:8080/openapi.json" >/dev/null; then
    echo "✅ OpenAPI specification endpoint accessible"
else
    echo "⚠️  OpenAPI specification endpoint not responding"
fi

# Show container status
echo "📊 Container status:"
if [ "$DEPLOYMENT_MODE" = "compose" ]; then
    docker-compose ps
else
    docker ps | grep "$CONTAINER_NAME"
fi

# Cleanup old images (keep last 3)
echo "🧹 Cleaning up old images..."
OLD_IMAGES=$(docker images "$IMAGE_NAME" --format "table {{.Tag}}" | grep -E "backup-[0-9]+" | sort -r | tail -n +4)
if [ -n "$OLD_IMAGES" ]; then
    echo "$OLD_IMAGES" | xargs -I {} docker rmi "$IMAGE_NAME:{}" || true
    echo "✅ Old backup images cleaned"
fi

echo "==================================================="
echo "🎉 Deployment completed successfully!"
echo ""
echo "📋 Service Information:"
echo "  Health Check:       $HEALTH_ENDPOINT"
echo "  Status Endpoint:    http://localhost:8080/status"
echo "  Metrics Endpoint:   http://localhost:8080/metrics"
echo "  OpenAPI Spec:       http://localhost:8080/openapi.json"
echo "  MCP Capabilities:   http://localhost:8080/mcp/capabilities"
echo "  Container Mode:     $DEPLOYMENT_MODE"
echo "  Image:             $IMAGE_NAME:latest"
echo ""
echo "📚 Management commands:"
echo "  View logs:        docker-compose logs -f (or docker logs -f $CONTAINER_NAME)"
echo "  Stop service:     docker-compose down (or docker stop $CONTAINER_NAME)"
echo "  Restart service:  docker-compose restart (or docker restart $CONTAINER_NAME)"
echo ""
echo "🔄 Rollback available: $IMAGE_NAME:$BACKUP_TAG"
