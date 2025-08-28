.PHONY: setup render dash
setup:
	@bin/bootstrap.sh

render:
	@bin/safe_render.sh

dash:
	@. venv/bin/activate && python jobs/dash.py
