.PHONY: help install run clean tunnel all stop test stress-test

help:
	@echo "Makefile commands:"
	@echo "  install       Install dependencies"
	@echo "  run           Run the application"
	@echo "  test          Run unit tests"
	@echo "  stress-test   Run agent stress test (5 questions, saves report)"
	@echo "  clean         Clean up generated files"
	@echo "  tunnel        Start ngrok tunnel"
	@echo "  all           Run application and start ngrok tunnel"
	@echo "  stop          Stop running application and tunnel"

install:
	uv sync

run:
	uv run streamlit run streamlit_agent_dashboard.py

test:
	uv run pytest

stress-test:
	uv run python tests/stress_test.py $(ARGS)

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf *.pyc
	rm -rf .DS_Store
	rm -rf .venv
	rm -rf deprecated
	rm -rf "demo video"

tunnel:
	ngrok http --domain snail-tough-cowbird.ngrok-free.app 8015

all:
	@echo "Starting Streamlit application and ngrok tunnel..."
	@streamlit run streamlit_agent_dashboard.py &
	@ngrok http --domain snail-tough-cowbird.ngrok-free.app 8501

stop:
	pkill -f streamlit || true
	pkill -f ngrok || true
