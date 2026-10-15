REPLAYBOOK_DIR ?= ../replaybook

.PHONY: validate check oracle smoke-check core-check full-check frontier-check confirmation-check

validate:
	python $(REPLAYBOOK_DIR)/integrations/host/scenario_pack.py --pack . --list

smoke-check: validate
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark-smoke.toml \
		--check

core-check: validate
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark-core.toml \
		--check

full-check: validate
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark.toml \
		--check

frontier-check: validate
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark-real.toml \
		--check

confirmation-check: validate
	REPLAYBOOK_DIR=$(REPLAYBOOK_DIR) python -m unittest discover -s 013-sidekiq-wrong-redis -p 'test_*.py'

check: smoke-check core-check full-check frontier-check confirmation-check

oracle: full-check
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark.toml \
		--oracle
