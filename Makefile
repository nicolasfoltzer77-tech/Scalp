.PHONY: test

test:
	pytest

dash:
	@. .venv/bin/activate && python jobs/dash.py --headless --port 8501
