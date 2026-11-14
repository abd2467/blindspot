PY ?= python3
export PYTHONPATH := src

.PHONY: setup fixtures demo real check test serve clean

setup:
	$(PY) -m pip install -r requirements.txt

fixtures:
	$(PY) scripts/make_fixtures.py

demo: fixtures
	$(PY) scripts/run_pipeline.py --fixtures

real:
	$(PY) scripts/run_pipeline.py

test:
	$(PY) -m pytest -q

check: fixtures test
	BLINDSPOT_DATA=data/fixtures $(PY) -m blindspot.contracts all

serve:
	$(PY) -m http.server -d web 8000

clean:
	rm -rf data/fixtures data/interim/*.nc
