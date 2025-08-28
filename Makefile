.PHONY: setup render dash test perms

# corrige les permissions des scripts
perms:
	@chmod +x bin/*.sh || true

# installe l’env Python + dépendances
setup: perms
	@./bin/bootstrap.sh

# rendu du rapport (via ton safe_render)
render: perms
	@./bin/safe_render.sh

# lance le dashboard
dash: perms
	@. venv/bin/activate && python jobs/dashboard.py

# exécuter les tests
test:
	pytest