.PHONY: demo test lint check

demo:
	uv run agentprobe demo

test:
	uv run pytest --cov=agentprobe --cov-report=term-missing

lint:
	uv run ruff check .
	uv run ruff format --check .

check: lint test
