.PHONY: help install dev test lint format build docker-build docker-up docker-down clean

# Default target
help:
	@echo "RealEstateRAG Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install production dependencies"
	@echo "  dev         Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  test        Run tests with coverage"
	@echo "  lint        Run linting (ruff + mypy)"
	@echo "  format      Format code with ruff"
	@echo "  run         Run API server locally"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build  Build Docker images"
	@echo "  docker-up     Start all services"
	@echo "  docker-down   Stop all services"
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

lint:
	. .venv/bin/activate && ruff check src/
	. .venv/bin/activate && mypy src/ --ignore-missing-imports

format:
	. .venv/bin/activate && ruff format src/
	. .venv/bin/activate && ruff check --fix src/

run:
	. .venv/bin/activate && python -m realestaterag.api.main

# Docker
docker-build:
	docker-compose -f deployments/docker/docker-compose.yml build

docker-up:
	docker-compose -f deployments/docker/docker-compose.yml up -d

docker-down:
	docker-compose -f deployments/docker/docker-compose.yml down

docker-logs:
	docker-compose -f deployments/docker/docker-compose.yml logs -f

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
