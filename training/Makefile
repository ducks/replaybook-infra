REPLAYBOOK_DIR ?= ../../replaybook

.PHONY: validate check oracle test
validate:
	python $(REPLAYBOOK_DIR)/integrations/host/scenario_pack.py --pack . --list
check: validate
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py --benchmark benchmark-training.toml --check
test:
	python -m unittest discover -s tests -p 'test_*.py'
oracle: check
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py --benchmark benchmark-training.toml --oracle --concurrency 1 --base-port 20400
