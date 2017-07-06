
install-deps:
	pip install -r requirements.txt

build:
	pip install .

test:
	pytest tests

run:
	python3 -m aw_analysis.main

