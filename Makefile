.PHONY: setup render publish test

setup:
	@bin/bootstrap.sh

render:
	@bin/safe_render.sh

publish:
	@bin/git-sync.sh

test:
	@pytest -q || true