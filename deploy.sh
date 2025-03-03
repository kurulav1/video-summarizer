#!/bin/bash

echo "🚀 Deploying FastAPI & React with Docker..."

# Move to project root
cd "$(dirname "$0")"

# Parse arguments
VERBOSE=false
for arg in "$@"; do
    if [ "$arg" == "--verbose" ]; then
        VERBOSE=true
    fi
done

# Remove old containers and volumes
if [ "$VERBOSE" == true ]; then
    echo "🛠 Stopping and removing old containers..."
    docker-compose down -v
else
    docker-compose down -v > /dev/null 2>&1
fi

# Remove old frontend build directory
rm -rf frontend/dist

echo "🛠 Building Docker images..."

if [ "$VERBOSE" == true ]; then
    docker-compose build --progress=plain
else
    docker-compose build > /dev/null 2>&1
fi

# Start containers
if [ "$VERBOSE" == true ]; then
    docker-compose up -d
else
    docker-compose up -d > /dev/null 2>&1
fi

# Show running containers
if [ "$VERBOSE" == true ]; then
    docker ps
fi

echo "✅ Deployment complete!"
echo "📌 Backend running at: http://localhost:8000"
echo "📌 Frontend running at: http://localhost:5173"

# Show logs if verbose mode is enabled
if [ "$VERBOSE" == true ]; then
    echo "📜 Backend logs:"
    docker-compose logs backend | tail -n 20
fi
