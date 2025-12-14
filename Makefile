.PHONY: help install dev test test-unit test-integration lint format build docker-build docker-up docker-down clean security ingest migrate

# Default target
help:
	@echo "RealEstateRAG Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install production dependencies"
	@echo "  dev         Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  test            Run all tests with coverage"
	@echo "  test-unit       Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  lint            Run linting (ruff + mypy)"
	@echo "  format          Format code with ruff"
	@echo "  run             Run API server locally"
	@echo ""
	@echo "Data:"
	@echo "  ingest      Run batch ingestion"
	@echo "  migrate     Run data migration"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build  Build Docker images"
	@echo "  docker-up     Start all services"
	@echo "  docker-down   Stop all services"
	@echo "  docker-logs   View service logs"
	@echo ""
	@echo "Security:"
	@echo "  security    Run security scan (bandit)"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean       Remove build artifacts"

# Setup
install:
	uv venv
	. .venv/bin/activate && uv pip install -e .

dev:
	uv venv
	. .venv/bin/activate && uv pip install -e ".[dev]"

# Development
test:
	. .venv/bin/activate && pytest tests/ -v --cov=src/realestaterag

test-unit:
	. .venv/bin/activate && pytest tests/unit/ -v

test-integration:
	. .venv/bin/activate && pytest tests/integration/ -v

lint:
	. .venv/bin/activate && ruff check src/
	. .venv/bin/activate && mypy src/ --ignore-missing-imports

format:
	. .venv/bin/activate && ruff format src/
	. .venv/bin/activate && ruff check --fix src/

run:
	. .venv/bin/activate && python -m realestaterag.api.main

# Data operations
ingest:
	. .venv/bin/activate && python scripts/batch_ingest.py

migrate:
	. .venv/bin/activate && python scripts/migrate_v2_to_v3.py

# Docker
docker-build:
	docker-compose -f deployments/docker/docker-compose.yml build

docker-up:
	docker-compose -f deployments/docker/docker-compose.yml up -d

docker-down:
	docker-compose -f deployments/docker/docker-compose.yml down

docker-logs:
	docker-compose -f deployments/docker/docker-compose.yml logs -f

# Security
security:
	. .venv/bin/activate && pip install bandit && bandit -r src/ -ll

# Cleanup
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
