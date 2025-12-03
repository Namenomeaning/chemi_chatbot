# Quick Start for GitHub Codespaces

This project is fully configured to run in GitHub Codespaces with one-command setup.

## 🚀 Getting Started (3 steps)

### Step 1: Create `.env` file

```bash
cp .env.example .env
nano .env  # Add your GOOGLE_GEMINI_API_KEY
```

Get API key: https://makersuite.google.com/app/apikey

### Step 2: Run full setup

```bash
make setup
```

This installs dependencies, starts Qdrant, and ingests data (~2-3 minutes).

### Step 3: Start services

**Development Mode (recommended):**

```bash
# Terminal 1
make dev

# Terminal 2 (click + icon to create new terminal)
make start-gradio
```

**Or start all in background:**

```bash
make start-all
```

## 🌐 Access URLs

After services start, click on "PORTS" tab:

- **Gradio UI** (Port 7860) - Main interface
- **FastAPI Backend** (Port 8000) - API docs
- **Qdrant** (Port 6333) - Vector DB dashboard

## 📝 Common Commands

```bash
make help          # Show all commands
make status        # Check if services are running
make stop          # Stop all services
make logs-backend  # View backend logs
make test          # Run tests
```

## 🐛 Troubleshooting

**Services not starting?**
```bash
make stop
make start-all
```

**API connection error?**
```bash
make status  # Check which services are down
```

See [CODESPACE_SETUP.md](../CODESPACE_SETUP.md) for detailed troubleshooting.

---

💡 **Tip**: Use `make dev` for hot reload during development!
