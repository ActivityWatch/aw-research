.PHONY: build test run

build:
	pipenv install --dev --skip-lock

test:
	pipenv run pytest tests/ aw_research/classify.py

test-integration:
	pipenv run aw_research redact
	pipenv run aw_research merge
	pipenv run aw_research flood
	pipenv run aw_research heartbeat
	pipenv run aw_research classify summary
	pipenv run aw_research classify cat Uncategorized
	pipenv run python3 examples/afk_and_audible.py
	pipenv run python3 examples/redact_sensitive.py
	make vis-aw-development
	#pipenv run python3 aw_research analyse

typecheck:
	pipenv run python3 -m mypy --ignore-missing-imports aw_research/ examples/ tests/

.cache-query-result:
	pipenv run python3 -m aw_client --host localhost:5666 query --json --start 2018-01-01 queries/aw-development.awq > .cache-query-result

vis-aw-development: .cache-query-result
	pipenv run python3 examples/plot_timeperiods.py .cache-query-result

