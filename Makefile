REPLAYBOOK_DIR ?= ../replaybook

.PHONY: validate check oracle

validate:
	python $(REPLAYBOOK_DIR)/integrations/host/scenario_pack.py --pack . --list

check: validate
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark.toml \
		--check

oracle: check
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark.toml \
		--oracle
