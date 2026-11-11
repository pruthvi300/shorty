.PHONY: help dev dev-d stop logs logs-api install test lint clean

help:
	@echo "Shorty - Commands"
	@echo ""
	@echo "  make dev       Start all services with Docker"
	@echo "  make stop      Stop all services"
	@echo "  make logs      View logs"
	@echo "  make install   Install backend dev dependencies"
	@echo "  make test      Run backend tests"
	@echo "  make lint      Run ruff"
	@echo "  make clean     Remove containers and volumes"

dev:
	docker compose up --build

dev-d:
	docker compose up -d --build

stop:
	docker compose down

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

install:
	cd api && pip install -r requirements-dev.txt

test:
	cd api && pytest -v

lint:
	cd api && ruff check app tests

clean:
	docker compose down -v
