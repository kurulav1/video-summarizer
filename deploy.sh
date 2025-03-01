#!/bin/bash

echo "🚀 Deploying FastAPI & React with Docker..."

# Move to project root
cd "$(dirname "$0")"

# Build and run the containers
docker-compose up --build -d

# Show running containers
docker ps

echo "✅ Deployment complete!"
echo "📌 Backend running at: http://localhost:8000"
echo "📌 Frontend running at: http://localhost:5173"
