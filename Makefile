.PHONY: build test run

build:
	poetry install

test:
	pytest tests/ aw_research/classify.py

test-integration:
	aw-research redact
	aw-research merge
	aw-research flood
	aw-research heartbeat
	aw-research classify summary
	aw-research classify cat Uncategorized
	python3 examples/afk_and_audible.py
	python3 examples/redact_sensitive.py
	make vis-aw-development
	#pipenv run python3 aw_research analyse

typecheck:
	mypy --ignore-missing-imports aw_research/ examples/ tests/

.cache-query-result:
	python3 -m aw_client --host localhost:5666 query --json --start 2018-01-01 queries/aw-development.awq > .cache-query-result

vis-aw-development: .cache-query-result
	python3 examples/plot_timeperiods.py .cache-query-result

