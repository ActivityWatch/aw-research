.PHONY: build test run

build:
	pip install . -r requirements.txt

test:
	python3 -m pytest
