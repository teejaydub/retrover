
dev-setup:
	pip install pipenv
	pipenv install
	make help

help:
	pipenv run python retrover.py -h
