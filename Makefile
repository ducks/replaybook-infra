REPLAYBOOK_DIR ?= ../replaybook
SCENARIO ?= 001-nginx-502-host

.PHONY: validate oracle

validate:
	python $(REPLAYBOOK_DIR)/integrations/host/scenario_pack.py --pack . --list

oracle: validate
	$(REPLAYBOOK_DIR)/integrations/host/run-host-native.sh \
		--scenario-pack . \
		--scenario $(SCENARIO) \
		--oracle
