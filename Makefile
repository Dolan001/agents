.PHONY: test lint typecheck check

test:
	python -m pytest

lint:
	ruff check .

typecheck:
	mypy src

check: lint typecheck test

