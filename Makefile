.PHONY: generate test

generate:
	PYTHONPATH=src python -m healthcare_capstone.cli generate --output data/generated --patients 500 --seed 42

test:
	PYTHONPATH=src python -m unittest discover -s tests -v
