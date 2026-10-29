REPLAYBOOK_DIR ?= ../replaybook

.PHONY: validate check oracle smoke-check core-check full-check frontier-check confirmation-check tls-check

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

tls-check: validate
	REPLAYBOOK_DIR=$(REPLAYBOOK_DIR) python -m unittest discover -s 033-tls-trust-rotation -p 'test_*.py'

check: smoke-check core-check full-check frontier-check confirmation-check tls-check

oracle: full-check
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark.toml \
		--oracle

.PHONY: core-hard-check core-hard-oracle
core-hard-check: validate
	python -m unittest discover -s tests -p 'test_core_hard.py'
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--benchmark ./benchmark-core-hard.toml --check

core-hard-oracle: core-hard-check
	python $(REPLAYBOOK_DIR)/integrations/host/run_host_matrix.py \
		--scenario-pack . \
		--scenario 034-checkout-dependency-rollout \
		--scenario 035-notification-outbox-rollout \
		--scenario 036-reservation-write-contention \
		--oracle --attempts 1 --concurrency 1 --base-port 24000
