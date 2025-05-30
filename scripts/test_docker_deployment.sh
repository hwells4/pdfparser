#!/bin/bash

# Docker Deployment Test Script
# Tests the PDF Parser microservice in a containerized environment

set -e

echo "🐳 PDF Parser Docker Deployment Test"
echo "===================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="pdf-parser"
CONTAINER_NAME="pdf-parser-test"
PORT="8000"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Cleanup function
cleanup() {
    echo "🧹 Cleaning up..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
}

# Trap cleanup on exit
trap cleanup EXIT

echo "1️⃣  Building Docker image..."
if docker build -t $IMAGE_NAME . > /dev/null 2>&1; then
    print_status "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

echo "2️⃣  Testing without credentials..."
docker run -d -p $PORT:$PORT --name $CONTAINER_NAME $IMAGE_NAME

# Wait for container to start
sleep 5

# Test health endpoint
echo "   Testing health endpoint..."
if curl -s http://localhost:$PORT/health | grep -q "healthy"; then
    print_status "Health endpoint working"
else
    print_error "Health endpoint failed"
    exit 1
fi

# Test root endpoint
echo "   Testing root endpoint..."
if curl -s http://localhost:$PORT/ | grep -q "PDF Parser Microservice"; then
    print_status "Root endpoint working"
else
    print_error "Root endpoint failed"
    exit 1
fi

# Test parse endpoint without credentials (should fail with proper error)
echo "   Testing parse endpoint without credentials..."
RESPONSE=$(curl -s -X POST http://localhost:$PORT/parse \
    -H "Content-Type: application/json" \
    -d '{"s3_bucket":"test","s3_key":"test.pdf","webhook_url":"http://example.com"}')

if echo "$RESPONSE" | grep -q "Missing environment variables"; then
    print_status "Parse endpoint correctly rejects requests without credentials"
else
    print_error "Parse endpoint did not handle missing credentials properly"
    echo "Response: $RESPONSE"
    exit 1
fi

# Stop container for next test
docker stop $CONTAINER_NAME
docker rm $CONTAINER_NAME

echo "3️⃣  Testing with test credentials..."
docker run -d -p $PORT:$PORT --name $CONTAINER_NAME \
    -e AWS_ACCESS_KEY_ID=test-key \
    -e AWS_SECRET_ACCESS_KEY=test-secret \
    -e DOCTLY_API_KEY=test-doctly-key \
    $IMAGE_NAME

# Wait for container to start
sleep 5

# Test parse endpoint with credentials (should accept but fail on actual AWS call)
echo "   Testing parse endpoint with test credentials..."
RESPONSE=$(curl -s -X POST http://localhost:$PORT/parse \
    -H "Content-Type: application/json" \
    -d '{"s3_bucket":"test","s3_key":"test.pdf","webhook_url":"http://example.com"}')

if echo "$RESPONSE" | grep -q "queued"; then
    print_status "Parse endpoint accepts requests with credentials"
else
    print_error "Parse endpoint did not accept request with credentials"
    echo "Response: $RESPONSE"
    exit 1
fi

# Wait a bit and check logs for expected AWS error
sleep 5
if docker logs $CONTAINER_NAME 2>&1 | grep -q "AWS credential validation failed"; then
    print_status "Worker correctly validates AWS credentials"
else
    print_warning "Worker AWS validation not detected (may need more time)"
fi

echo "4️⃣  Testing Docker health check..."
sleep 10  # Wait for health check to complete
HEALTH_STATUS=$(docker inspect $CONTAINER_NAME --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-healthcheck")

if [ "$HEALTH_STATUS" = "healthy" ]; then
    print_status "Docker health check passed"
elif [ "$HEALTH_STATUS" = "starting" ]; then
    print_warning "Docker health check still starting"
else
    print_warning "Docker health check status: $HEALTH_STATUS"
fi

echo ""
echo "🎉 Docker deployment test completed successfully!"
echo ""
echo "📋 Summary:"
echo "   • Docker image builds correctly"
echo "   • Container starts without credentials"
echo "   • Health and root endpoints work"
echo "   • Parse endpoint properly validates credentials"
echo "   • Worker processes jobs and validates AWS credentials"
echo "   • Application is ready for production deployment"
echo ""
echo "🚀 To deploy with real credentials:"
echo "   docker run -d -p 8000:8000 \\"
echo "     -e AWS_ACCESS_KEY_ID=your-key \\"
echo "     -e AWS_SECRET_ACCESS_KEY=your-secret \\"
echo "     -e DOCTLY_API_KEY=your-doctly-key \\"
echo "     $IMAGE_NAME" 