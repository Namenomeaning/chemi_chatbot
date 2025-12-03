.PHONY: help install setup start-qdrant ingest start-backend start-gradio start-all stop clean test

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)Chemistry Chatbot - Available Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

install: ## Install Python dependencies using uv
	@echo "$(BLUE)Installing dependencies...$(NC)"
	uv sync
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

setup: install ## Full setup: install deps + start Qdrant + ingest data
	@echo "$(BLUE)Starting full setup...$(NC)"
	@$(MAKE) start-qdrant
	@sleep 5
	@$(MAKE) ingest
	@echo "$(GREEN)✓ Setup complete!$(NC)"

start-qdrant: ## Start Qdrant vector database (Docker)
	@echo "$(BLUE)Starting Qdrant...$(NC)"
	docker compose up -d
	@echo "$(GREEN)✓ Qdrant started at http://localhost:6333$(NC)"

stop-qdrant: ## Stop Qdrant
	@echo "$(BLUE)Stopping Qdrant...$(NC)"
	docker compose down
	@echo "$(GREEN)✓ Qdrant stopped$(NC)"

ingest: ## Ingest chemistry data into Qdrant
	@echo "$(BLUE)Ingesting data...$(NC)"
	uv run python src/pipeline/ingest.py
	@echo "$(GREEN)✓ Data ingested$(NC)"

start-backend: ## Start FastAPI backend
	@echo "$(BLUE)Starting FastAPI backend...$(NC)"
	@echo "$(YELLOW)Backend will run at http://localhost:8000$(NC)"
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

start-gradio: ## Start Gradio frontend
	@echo "$(BLUE)Starting Gradio interface...$(NC)"
	@echo "$(YELLOW)📍 Local: http://localhost:7860$(NC)"
	@echo "$(YELLOW)🌐 Public URL will be shown below...$(NC)"
	@echo ""
	uv run python gradio/app.py

start-all: ## Start all services (Qdrant, backend, Gradio) in background
	@echo "$(BLUE)Starting all services...$(NC)"
	@$(MAKE) start-qdrant
	@sleep 5
	@echo "$(BLUE)Starting backend in background...$(NC)"
	@nohup uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/backend.log 2>&1 &
	@echo "$(GREEN)✓ Backend started (logs: logs/backend.log)$(NC)"
	@sleep 2
	@echo "$(BLUE)Starting Gradio in background...$(NC)"
	@nohup uv run python gradio/app.py > logs/gradio.log 2>&1 &
	@echo "$(GREEN)✓ Gradio started (logs: logs/gradio.log)$(NC)"
	@echo ""
	@echo "$(GREEN)✓ All services started!$(NC)"
	@echo ""
	@echo "$(YELLOW)📍 Local URLs:$(NC)"
	@echo "  - Backend: http://localhost:8000"
	@echo "  - Gradio:  http://localhost:7860"
	@echo "  - Qdrant:  http://localhost:6333"
	@echo ""
	@echo "$(YELLOW)🌐 For Gradio public URL, run:$(NC)"
	@echo "  make logs-gradio  # Look for 'Running on public URL:' line"

stop: ## Stop all services
	@echo "$(BLUE)Stopping all services...$(NC)"
	@pkill -f "uvicorn src.main:app" || true
	@pkill -f "python gradio/app.py" || true
	@$(MAKE) stop-qdrant
	@echo "$(GREEN)✓ All services stopped$(NC)"

logs-backend: ## View backend logs
	@tail -f logs/backend.log

logs-gradio: ## View Gradio logs
	@tail -f logs/gradio.log

show-gradio-url: ## Show Gradio public URL from logs
	@echo "$(BLUE)Extracting Gradio public URL...$(NC)"
	@grep -h "public URL" logs/gradio.log 2>/dev/null | tail -1 || echo "$(YELLOW)⚠ Public URL not found. Make sure Gradio is running.$(NC)"

test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	uv run pytest tests/ -v
	@echo "$(GREEN)✓ Tests completed$(NC)"

test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	uv run python tests/test_integration.py
	@echo "$(GREEN)✓ Integration tests completed$(NC)"

test-search: ## Test hybrid search
	@echo "$(BLUE)Testing hybrid search...$(NC)"
	uv run python tests/test_hybrid_search.py
	@echo "$(GREEN)✓ Search tests completed$(NC)"

clean: ## Clean up temporary files and caches
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf logs/*.log 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

dev: ## Development mode: start Qdrant and backend with hot reload
	@echo "$(BLUE)Starting development mode...$(NC)"
	@$(MAKE) start-qdrant
	@sleep 3
	@echo "$(BLUE)Starting backend with hot reload...$(NC)"
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

check-env: ## Check if .env file exists and has required variables
	@echo "$(BLUE)Checking environment...$(NC)"
	@if [ ! -f .env ]; then \
		echo "$(YELLOW)⚠ .env file not found. Create it from .env.example$(NC)"; \
		exit 1; \
	fi
	@grep -q "GOOGLE_GEMINI_API_KEY" .env || (echo "$(YELLOW)⚠ GOOGLE_GEMINI_API_KEY not set$(NC)" && exit 1)
	@echo "$(GREEN)✓ Environment OK$(NC)"

status: ## Show status of all services
	@echo "$(BLUE)Service Status:$(NC)"
	@echo ""
	@echo "Qdrant:"
	@curl -s http://localhost:6333/health > /dev/null && echo "  $(GREEN)✓ Running$(NC)" || echo "  $(YELLOW)✗ Not running$(NC)"
	@echo ""
	@echo "Backend:"
	@curl -s http://localhost:8000/ > /dev/null && echo "  $(GREEN)✓ Running$(NC)" || echo "  $(YELLOW)✗ Not running$(NC)"
	@echo ""
	@echo "Gradio:"
	@curl -s http://localhost:7860/ > /dev/null && echo "  $(GREEN)✓ Running$(NC)" || echo "  $(YELLOW)✗ Not running$(NC)"
