# ML Recommender System - Docker Guide

## Quick Start

### Build and Run
```bash
docker-compose up --build
```

### Access the Application
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend UI: http://localhost:8000/ui/

### Stop the Application
```bash
docker-compose down
```

## Manual Docker Commands

### Build Image
```bash
docker build -t ml-recommender .
```

### Run Container
```bash
docker run -p 8000:8000 ml-recommender
```

### Run with Volume Mounts (Development)
```bash
docker run -p 8000:8000 \
  -v ${PWD}/app:/app/app \
  -v ${PWD}/ui:/app/ui \
  -v ${PWD}/data:/app/data:ro \
  -v ${PWD}/models:/app/models:ro \
  ml-recommender
```

## Production Deployment

For production, modify docker-compose.yml to:
1. Remove volume mounts for code
2. Set specific CORS origins in app/main.py
3. Add environment variables for secrets
4. Use a reverse proxy (nginx) for HTTPS

## Troubleshooting

### Port Already in Use
```bash
docker-compose down
# Or kill the process using port 8000
```

### Rebuild After Code Changes
```bash
docker-compose up --build
```

### View Logs
```bash
docker-compose logs -f
```
