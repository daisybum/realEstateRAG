.PHONY: help install dev test test-unit test-integration lint format build docker-build docker-up docker-down clean security ingest migrate proto services-up services-down

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
	@echo "Docker (Monolith):"
	@echo "  docker-build  Build Docker images"
	@echo "  docker-up     Start all services"
	@echo "  docker-down   Stop all services"
	@echo "  docker-logs   View service logs"
	@echo ""
	@echo "Microservices:"
	@echo "  proto           Generate gRPC code from proto files"
	@echo "  services-build  Build all microservice images"
	@echo "  services-up     Start microservices stack"
	@echo "  services-down   Stop microservices stack"
	@echo "  services-logs   View microservices logs"
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

# Docker (Monolith)
docker-build:
	docker-compose -f deployments/docker/docker-compose.yml build

docker-up:
	docker-compose -f deployments/docker/docker-compose.yml up -d

docker-down:
	docker-compose -f deployments/docker/docker-compose.yml down

docker-logs:
	docker-compose -f deployments/docker/docker-compose.yml logs -f

# Microservices
proto:
	@echo "Generating gRPC code..."
	python -m grpc_tools.protoc \
		-I./shared/proto \
		--python_out=./shared/proto \
		--grpc_python_out=./shared/proto \
		./shared/proto/graph_service.proto

services-build:
	docker-compose -f deployments/docker/docker-compose.microservices.yml build

services-up:
	@echo "Starting infrastructure services..."
	docker-compose -f deployments/docker/docker-compose.microservices.yml up -d
	@echo ""
	@echo "Infrastructure running:"
	@echo "  - RabbitMQ: http://localhost:15672 (admin/admin123)"
	@echo "  - PostgreSQL: localhost:5432"
	@echo "  - FalkorDB: localhost:6380"
	@echo "  - Redis: localhost:6379"
	@echo ""
	@echo "To start all services: docker-compose -f deployments/docker/docker-compose.microservices.yml --profile services up -d"

services-down:
	docker-compose -f deployments/docker/docker-compose.microservices.yml down

services-logs:
	docker-compose -f deployments/docker/docker-compose.microservices.yml logs -f

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
