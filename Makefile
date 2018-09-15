.PHONY: build test run

build:
	pipenv install

test: typecheck
	pipenv run pytest tests/

test-integration:
	pipenv run python3 aw_research redact
	pipenv run python3 aw_research merge
	pipenv run python3 aw_research flood
	pipenv run python3 aw_research heartbeat
	pipenv run python3 -m aw_research.classify
	pipenv run python3 examples/afk_and_audible.py
	pipenv run python3 examples/redact_sensitive.py
	make vis-aw-development
	#pipenv run python3 aw_research analyse

typecheck:
	MYPYPATH="./stubs/mypy-data/numpy-mypy/" pipenv run python3 -m mypy --ignore-missing-imports aw_research/ examples/ tests/

.cache-query-result:
	python3 -m aw_client --host localhost:5666 query --json --start 2018-01-01 queries/aw-development.awq > .cache-query-result

vis-aw-development: .cache-query-result
	python3 examples/plot_timeperiods.py .cache-query-result

