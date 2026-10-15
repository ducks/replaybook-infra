"""Controller contract regressions; no model calls or VM required."""

import itertools
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCENARIO = Path(__file__).resolve().parent
REPLAYBOOK = Path(os.environ.get("REPLAYBOOK_DIR", SCENARIO.parents[1] / "replaybook"))
sys.path.insert(0, str(REPLAYBOOK / "integrations/host"))
import scenario_phase as phase


class ConfirmationContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name)
        self.queues = [set(), set()]
        self.completed = set()
        self.producer = 0
        self.worker = 1
        self.manifest = SCENARIO / "scenario.toml"
        for mocker in (
            patch.object(phase, "request", side_effect=self.request),
            patch.object(phase.time, "sleep"),
            patch.object(phase.time, "monotonic", side_effect=itertools.count()),
        ):
            mocker.start()
            self.addCleanup(mocker.stop)
        self.run_phase("preflight")
        self.backlog = phase.load_state(self.state)["backlog_jobs"]

    def request(self, base_url, step, path):
        if path == "/health":
            return phase.Response(200, "ok")
        identifier = path.removeprefix("/jobs/")
        if step.get("method", "GET") == "POST":
            self.queues[self.producer].add(identifier)
            return phase.Response(202, "")
        self.completed.update(self.queues[self.worker])
        self.queues[self.worker].clear()
        return phase.Response(200, "completed") if identifier in self.completed else phase.Response(404, "")

    def run_phase(self, name):
        phase.run_phase(self.manifest, name, "http://fixture", self.state)

    def assert_backlog_failure(self):
        with self.assertRaises(phase.PhaseFailure) as raised:
            self.run_phase("immediate")
        self.assertEqual(raised.exception.category, "backlog_not_recovered")

    def test_web_only_fix_leaves_backlog_and_fails(self):
        self.producer = 1
        self.assertEqual(self.request("", {"method": "POST"}, "/jobs/new-request").status, 202)
        self.assertEqual(self.request("", {}, "/jobs/new-request").body, "completed")
        self.assert_backlog_failure()

    def test_deleting_backlog_fails(self):
        self.queues[0].clear()
        self.worker = 0
        self.assert_backlog_failure()

    def test_missing_controller_state_fails_closed(self):
        (self.state / phase.STATE_FILE).unlink()
        self.worker = 0
        self.assert_backlog_failure()

    def assert_lifecycle_and_neutral_ids(self):
        identifiers = list(self.backlog)
        for name in ("immediate", "service_restart", "host_reboot"):
            self.run_phase(name)
            state = phase.load_state(self.state)
            self.assertEqual(state["backlog_jobs"], self.backlog)
            identifiers.extend(state["verification_jobs"])
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for identifier in identifiers:
            self.assertRegex(identifier, r"^confirmation-[0-9]+-[0-9]+-[0-9a-f]+-[0-9]+$")

    def test_worker_alignment_recovers_existing_and_new_work(self):
        self.worker = 0
        self.assert_lifecycle_and_neutral_ids()

    def test_web_alignment_with_backlog_migration_passes(self):
        self.producer = 1
        self.queues[1].update(self.queues[0])
        self.queues[0].clear()
        self.assert_lifecycle_and_neutral_ids()


if __name__ == "__main__":
    unittest.main()
