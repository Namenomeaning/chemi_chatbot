# GitHub Codespaces Setup Guide

## 🚀 Quick Start

### 1. Open in Codespaces

Click the "Code" button on GitHub → "Codespaces" → "Create codespace on main"

### 2. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Google Gemini API key
nano .env
```

Get your Gemini API key from: https://makersuite.google.com/app/apikey

### 3. Run Full Setup

```bash
make setup
```

This will:
- Install all dependencies
- Start Qdrant vector database
- Ingest chemistry data

### 4. Start Services

**Option A: Run in foreground (recommended for development)**
```bash
# Terminal 1: Backend
make start-backend

# Terminal 2 (new terminal): Gradio
make start-gradio
```

**Option B: Run all in background**
```bash
make start-all
```

### 5. Access Services

Codespaces will automatically forward ports:
- **Gradio UI**: Port 7860 (should open automatically)
- **FastAPI Backend**: Port 8000
- **Qdrant Dashboard**: Port 6333

Click on the "PORTS" tab in VS Code to see all forwarded URLs.

---

## 📋 Available Commands

Run `make help` to see all available commands:

```bash
make help              # Show all commands
make install           # Install dependencies only
make setup             # Full setup (install + Qdrant + ingest)

make start-qdrant      # Start Qdrant database
make start-backend     # Start FastAPI backend
make start-gradio      # Start Gradio frontend
make start-all         # Start all services in background

make stop              # Stop all services
make status            # Check status of all services

make dev               # Development mode (Qdrant + backend with hot reload)

make test              # Run all tests
make test-integration  # Run integration tests
make test-search       # Test hybrid search

make logs-backend      # View backend logs
make logs-gradio       # View Gradio logs

make clean             # Clean up temp files
```

---

## 🔧 Development Workflow

### Quick Development Cycle

```bash
# Start Qdrant and backend with hot reload
make dev

# In another terminal, start Gradio
make start-gradio
```

Backend will auto-reload on code changes.

### Running Tests

```bash
# Run all tests
make test

# Run specific test suite
make test-integration
make test-search
```

### Check Service Status

```bash
make status
```

### View Logs

```bash
# Backend logs
make logs-backend

# Gradio logs
make logs-gradio
```

---

## 🐛 Troubleshooting

### Port Already in Use

```bash
# Stop all services and restart
make stop
make start-all
```

### Qdrant Not Starting

```bash
# Check Docker status
docker ps

# Restart Qdrant
docker compose down
docker compose up -d
```

### Environment Variables Not Set

```bash
# Check .env file exists
cat .env

# If missing, copy from example
cp .env.example .env
nano .env
```

### Backend API Connection Error

```bash
# Check backend is running
make status

# If not, start it
make start-backend
```

---

## 📦 Project Structure

```
chemistry_chatbot/
├── .devcontainer/          # Codespaces configuration
│   └── devcontainer.json
├── data/                   # Chemistry data (elements + compounds)
│   ├── chemistry_data.json
│   ├── images/            # Structure images
│   └── audio/             # TTS audio files
├── src/
│   ├── agent/             # LangGraph agent
│   │   ├── nodes/         # Agent nodes
│   │   ├── state.py       # Agent state
│   │   └── graph.py       # Workflow graph
│   ├── services/          # External services
│   │   ├── gemini_service.py
│   │   ├── qdrant_service.py
│   │   └── embedding_service.py
│   ├── pipeline/          # Data ingestion
│   │   └── ingest.py
│   └── main.py            # FastAPI backend
├── gradio/
│   └── app.py             # Gradio frontend
├── tests/                 # Test suite
├── Makefile              # Build commands
├── docker-compose.yml    # Qdrant setup
├── pyproject.toml        # Python dependencies
└── .env.example          # Environment template
```

---

## 🌐 Deployment

### To Production

For production deployment, consider:

1. **Backend API**: Deploy FastAPI to Render, Railway, or Fly.io
2. **Frontend**: Deploy Gradio to Hugging Face Spaces
3. **Qdrant**: Use Qdrant Cloud or self-hosted

### Hugging Face Spaces Deployment

See `gradio/app.py` - update `API_URL` to point to your deployed backend.

---

## 📚 Additional Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Gemini API Docs](https://ai.google.dev/docs)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [Gradio Documentation](https://gradio.app/docs/)

---

## 💡 Tips

1. **API Quota**: Free tier Gemini has 15 requests/minute limit. Upgrade for production.
2. **Model Loading**: First run takes ~5 mins to download embedding model.
3. **Hot Reload**: Backend auto-reloads on file changes with `make dev`.
4. **Logs**: Check `logs/` directory for service logs when running `make start-all`.
