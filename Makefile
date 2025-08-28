.SILENT:
.DEFAULT_GOAL := help

PY      := python3
VENV    := venv
ACT     := . $(VENV)/bin/activate;

.PHONY: help setup perms venv install render dash clean

help:
	@echo "make setup   - chmod +x, create venv, pip install"
	@echo "make render  - build dashboard (tools.render_report)"
	@echo "make dash    - run jobs/dashboard.py"
	@echo "make clean   - delete venv"

# 1) permissions for all scripts
perms:
	find . -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \;

# 2) create venv + modern pip
$(VENV)/bin/python:
	$(PY) -m venv $(VENV)
	$(ACT) $(PY) -m pip install -U pip setuptools wheel

# 3) install deps
install: $(VENV)/bin/python
	$(ACT) $(PY) -m pip install -r requirements.txt

# 4) one-liner for fresh clones
setup: perms install
	@echo "✓ setup ok (perms + venv + deps)"

# 5) commands you’ll actually run
render:
	$(ACT) PYTHONPATH=$(PWD) SCALP_SKIP_BOOT=1 $(PY) -m tools.render_report

dash:
	$(ACT) PYTHONPATH=$(PWD) $(PY) jobs/dashboard.py

clean:
	rm -rf $(VENV)