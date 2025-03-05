#!/bin/bash

echo "🚀 Deploying FastAPI & React with Docker..."

cd "$(dirname "$0")"

VERBOSE=false
NO_CACHE=false

for arg in "$@"; do
    case $arg in
        --verbose)
            VERBOSE=true
            ;;
        --no-cache)
            NO_CACHE=true
            ;;
    esac
done

if [ "$VERBOSE" == true ]; then
    echo "🛠 Stopping and removing old containers..."
    docker-compose down -v
else
    docker-compose down -v > /dev/null 2>&1
fi

rm -rf frontend/dist

echo "🛠 Building Docker images..."

BUILD_CMD="docker-compose build"
if [ "$NO_CACHE" == true ]; then
    BUILD_CMD="$BUILD_CMD --no-cache"
fi

if [ "$VERBOSE" == true ]; then
    $BUILD_CMD --progress=plain
else
    $BUILD_CMD > /dev/null 2>&1
fi

if [ "$VERBOSE" == true ]; then
    docker-compose up -d
else
    docker-compose up -d > /dev/null 2>&1
fi

if [ "$VERBOSE" == true ]; then
    docker ps
fi

echo "✅ Deployment complete!"
echo "📌 Backend running at: http://localhost:8000"
echo "📌 Frontend running at: http://localhost:5173"

if [ "$VERBOSE" == true ]; then
    echo "📜 Backend logs:"
    docker-compose logs backend | tail -n 20
fi
