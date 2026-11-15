.PHONY: test

PYTHON := .venv/bin/python

test:
	cd yolo-service && ../$(PYTHON) -m unittest discover -s tests -p "test_approval_integration.py" -v
	cd dinov2-service && ../$(PYTHON) -m unittest discover -s tests -p "test_recognition_integration.py" -v