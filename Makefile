# TechCorp AI Agents Lab Course
# Every target works offline unless marked otherwise.

UV ?= uv

.PHONY: setup verify test test-live lint format index clean-index help

help:
	@echo "make setup       Create the environment and install pinned dependencies"
	@echo "make verify      Check what is ready and what still needs configuration"
	@echo "make test        Run the offline test suite (no API key needed)"
	@echo "make test-live   Run tests that call a real LLM API (needs OPENAI_API_KEY)"
	@echo "make lint        Check code style"
	@echo "make format      Auto-format code"
	@echo "make index       Build (or rebuild) the TechCorp vector index"
	@echo "make clean-index Delete the local vector index"

setup:
	$(UV) sync
	@test -f .env || cp .env.example .env
	@echo "\nSetup complete. Next: make verify"

verify:
	$(UV) run python scripts/verify_environment.py

test:
	$(UV) run pytest

test-live:
	$(UV) run pytest -m live

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

index:
	$(UV) run python scripts/build_index.py

clean-index:
	rm -rf .chroma
	@echo "Vector index deleted. Rebuild with: make index"
