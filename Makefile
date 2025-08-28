.PHONY: setup render dash perms

# 1) Prépare les permissions
perms:
	@chmod +x bin/*.sh || true

# 2) Crée et active l'environnement + installe requirements
setup: perms
	@python3 -m venv venv
	@. venv/bin/activate && pip install --upgrade pip setuptools wheel
	@. venv/bin/activate && pip install -r requirements.txt
	@test -f scalp.env || echo "⚠️ Missing scalp.env (create it for API keys)"

# 3) Lance le rendu du report
render:
	@. venv/bin/activate && PYTHONPATH=$$PWD python -m tools.render_report

# 4) Lance le dashboard
dash:
	@. venv/bin/activate && PYTHONPATH=$$PWD python jobs/dashboard.py