init:
	python -m pip install --upgrade pip
	python -m pip install pip-tools
	pip-compile --resolver=backtracking requirements/requirements.in
	pip-compile --resolver=backtracking requirements/dev-requirements.in
	pip-sync requirements/requirements.txt requirements/dev-requirements.txt
	pip install -e .[dev]

deps:
	pip-compile --resolver=backtracking requirements/requirements.in
	pip-compile --resolver=backtracking requirements/dev-requirements.in
	pip-sync requirements/requirements.txt requirements/dev-requirements.txt

black:
	black --check .

flake8:
	flake8 .

lint: black flake8

pytests:
	pytest -v
