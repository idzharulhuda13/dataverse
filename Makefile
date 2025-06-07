.PHONY: help install run clean tunnel all stop

help:
	@echo "Makefile commands:"
	@echo "  install    Install dependencies"
	@echo "  run        Run the application"
	@echo "  clean      Clean up generated files"
	@echo "  tunnel     Start ngrok tunnel"
	@echo "  all        Run application and start ngrok tunnel"
	@echo "  stop       Stop running application and tunnel"

install:
	pip install -r requirements.txt

run:
	streamlit run streamlit_chatbot.py

clean:
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf *.pyc
	rm -rf .DS_Store

tunnel:
	ngrok http 8501

all:
	@echo "Starting Streamlit application and ngrok tunnel..."
	@streamlit run streamlit_chatbot.py &
	@ngrok http 8501

stop:
	pkill -f streamlit || true
	pkill -f ngrok || true
