.PHONY: setup render watch clean

setup:
	./bin/bootstrap.sh

render:
	./bin/safe_render.sh

watch:
	./bin/watch_render.sh

clean:
	rm -rf venv logs/* __pycache__ */__pycache__