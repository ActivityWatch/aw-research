.PHONY: build test run

build:
	pip install . -r requirements.txt

test:
	pytest tests
