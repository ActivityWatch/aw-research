.PHONY: build test run

build:
	pip install -r requirements.txt
	pip install .

test:
	pytest tests

run:
	python3 -m aw_analysis.main

install-deps:
	pip install -r requirements.txt
