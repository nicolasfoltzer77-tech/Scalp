.PHONY: setup render test dash

setup:
	@echo "[SETUP] Init virtualenv & install deps"
	python3 -m venv venv
	. venv/bin/activate && pip install -U pip setuptools wheel
	. venv/bin/activate && pip install -r requirements.txt
	@chmod +x bin/*.sh   # 🔥 garantit que tout bin/*.sh est exécutable

render:
	./bin/safe_render.sh

dash:
	. venv/bin/activate && python jobs/dash.py

test:
	pytest