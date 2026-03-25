# Email Classifier - Makefile
# Fluxo recomendado: make setup -> make up -> make dev

.DEFAULT_GOAL := help

.PHONY: help up down backend frontend dev install setup venv logs status clean test db-upgrade db-migration-status db-check-alembic

# Cria venv se não existir
venv:
	@if [ ! -d $(VENV) ]; then \
		echo "$(YELLOW)Criando venv em backend/.venv$(NC)"; \
		python3 -m venv $(VENV); \
	fi

# Cores para output
GREEN  := \033[0;32m
YELLOW := \033[1;33m
NC     := \033[0m

# Python venv (backend/.venv)
VENV := backend/.venv
PYTHON := $(VENV)/bin/python
# Use "python -m pip" so a venv copiado de outra máquina não quebra (shebang do pip).
# Quando rodando de dentro de backend/
BACKEND_PY := .venv/bin/python

help:
	@echo ""
	@echo "$(GREEN)Email Classifier - Comandos disponíveis$(NC)"
	@echo ""
	@echo "  make setup     - Instala dependências (backend + frontend)"
	@echo "  make up        - Sobe PostgreSQL via Docker"
	@echo "  make down      - Para e remove containers"
	@echo "  make backend   - Inicia API FastAPI (porta 8000)"
	@echo "  make frontend  - Inicia Next.js (porta 3000)"
	@echo "  make dev       - Sobe DB + Backend + Frontend (fluxo completo)"
	@echo "  make logs      - Ver logs do PostgreSQL"
	@echo "  make status    - Verifica status dos serviços"
	@echo "  make clean     - Limpa cache e artefatos"
	@echo "  make test      - Executa testes do backend"
	@echo "  make db-upgrade - Alembic upgrade head (use DATABASE_URL do backend/.env)"
	@echo "  make db-migration-status - mostra revisão atual e head esperado"
	@echo "  make db-check-alembic - garante um único head de migração (sem DB)"
	@echo ""

# Docker / Banco
up:
	@echo "$(YELLOW)Subindo PostgreSQL...$(NC)"
	docker compose up -d
	@echo "$(GREEN)PostgreSQL rodando em localhost:5432$(NC)"
	@sleep 2

down:
	@echo "$(YELLOW)Parando containers...$(NC)"
	docker compose down

logs:
	docker compose logs -f

# Backend (FastAPI)
backend:
	@echo "$(YELLOW)Iniciando API em http://localhost:8000$(NC)"
	cd backend && $(BACKEND_PY) -m uvicorn app.main:app --reload --port 8000

# Frontend (Next.js)
frontend:
	@echo "$(YELLOW)Iniciando frontend em http://localhost:3000$(NC)"
	cd frontend && npm run dev

# Instalação
install: venv
	@echo "$(YELLOW)Instalando dependências do backend...$(NC)"
	@$(PYTHON) -m pip install -r backend/requirements.txt
	@echo "$(YELLOW)Instalando dependências do frontend...$(NC)"
	cd frontend && npm install
	@echo "$(GREEN)Dependências instaladas!$(NC)"

# Setup completo (primeira vez)
setup: install
	@if [ ! -f backend/.env ]; then \
		cp backend/.env.example backend/.env 2>/dev/null || true; \
		echo "$(YELLOW)Crie backend/.env a partir de .env.example$(NC)"; \
	fi
	@$(MAKE) up
	@echo ""
	@echo "$(GREEN)Setup concluído!$(NC)"
	@echo "Próximo passo: make dev"
	@echo ""

# Fluxo de desenvolvimento completo
# Sobe o banco, depois inicia backend e frontend em paralelo
dev: up
	@echo ""
	@echo "$(GREEN)Banco pronto. Iniciando backend e frontend...$(NC)"
	@echo "  API:      http://localhost:8000"
	@echo "  Frontend: http://localhost:3000"
	@echo ""
	@echo "Pressione Ctrl+C para parar ambos."
	@echo ""
	@(cd backend && $(BACKEND_PY) -m uvicorn app.main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

# Alternativa: dev em terminais separados (mais estável)
dev-backend: up
	@echo "$(GREEN)Banco pronto. Iniciando backend...$(NC)"
	cd backend && $(BACKEND_PY) -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# Status
status:
	@echo "$(YELLOW)Status dos serviços:$(NC)"
	@docker compose ps 2>/dev/null || echo "  Docker: não disponível"
	@echo ""
	@(curl -s -o /dev/null -w "  API (8000): %{http_code}\n" http://localhost:8000/docs 2>/dev/null) || echo "  API (8000): offline"
	@(curl -s -o /dev/null -w "  Frontend (3000): %{http_code}\n" http://localhost:3000 2>/dev/null) || echo "  Frontend (3000): offline"

# Banco: mesmo fluxo que produção (PostgreSQL + Alembic)
db-check-alembic:
	@$(PYTHON) backend/scripts/verify_single_alembic_head.py

db-upgrade: up
	@echo "$(YELLOW)Alembic upgrade head (backend/.env)...$(NC)"
	cd backend && $(BACKEND_PY) -m alembic upgrade head

db-migration-status: up
	@echo "$(YELLOW)Revisão aplicada no banco:$(NC)"
	@cd backend && $(BACKEND_PY) -m alembic current
	@echo "$(YELLOW)Head no repositório:$(NC)"
	@cd backend && $(BACKEND_PY) -m alembic heads

# Testes (SQLite em memória; não espelha produção)
test:
	@echo "$(YELLOW)Executando testes...$(NC)"
	cd backend && USE_SQLITE=1 DISABLE_JOB_SCHEDULER=1 $(BACKEND_PY) -m pytest tests/ -v
	@echo "$(GREEN)Testes concluídos!$(NC)"

# Limpeza
clean:
	@echo "$(YELLOW)Limpando cache...$(NC)"
	rm -rf frontend/.next
	find backend -depth -type d -name __pycache__ -exec rm -rf {} \; 2>/dev/null || true
	@echo "$(GREEN)Cache removido.$(NC)"
