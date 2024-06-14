.PHONY: lint
lint:
	docker compose run --rm --entrypoint=pylint test /src/gmsa

.PHONY: typecheck
typecheck:
	docker compose run --rm test --mypy /src/gmsa

.PHONY: test
test:
	docker compose run --rm test --disable-pytest-warnings /src/test

.PHONY: dist
dist:
	pip install wheel build
	python -m build
