.PHONY: setup render fix-exec

# Tous les scripts bin/ sont exécutables dans Git
fix-exec:
	chmod +x bin/*.sh || true
	git update-index --chmod=+x bin/bootstrap.sh || true
	git update-index --chmod=+x bin/safe_render.sh || true

# Prépare la machine: venv + pip de base
setup:
	@bin/bootstrap.sh

# Lance le rendu "safe" (logs, idempotent, use /etc/scalp.env)
render:
	@bin/safe_render.sh
render-sync:
	@./bin/safe_render.sh
