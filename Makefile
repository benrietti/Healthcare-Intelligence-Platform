.PHONY: generate test

generate:
	PYTHONPATH=src python -m healthcare_capstone.cli generate --output data/generated --patients 500 --seed 42

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

.PHONY: demo gate review cloud

demo:
	PYTHONPATH=src OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 python -m healthcare_capstone.demo --output data/demo --patients 2000
	python scripts/quality_gate.py --input data/demo
	python scripts/render_demo.py --input data/demo

gate:
	python scripts/quality_gate.py --input data/demo

review:
	python scripts/render_demo.py --input data/demo

cloud:
	PYTHONPATH=src python scripts/cloud_build.py
	python scripts/query_budget.py
	python scripts/cloud_monitor.py
