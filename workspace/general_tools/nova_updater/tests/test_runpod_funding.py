# Last updated: 2026-10-05 21:33:05
# @nova: Verify RunPod credit preflight and explicit region selection using temporary workspaces and fake provider responses only.
from __future__ import annotations

import json
from unittest.mock import patch
import unittest

from support import Workspace
from nova_updater import jobs, runpod


class FakeCredit:
    def __init__(self, balance=10.0):
        self.credit = balance
        self.calls = []

    def balance(self):
        self.calls.append("balance")
        if isinstance(self.credit, Exception):
            raise self.credit
        return self.credit

    def pod(self, pod_id):
        self.calls.append("pod")
        return {"costPerHr": 3.0, "desiredStatus": "EXITED"}

    def create(self, body):
        self.calls.append(("create", body))
        return {"id": "fake-new-pod"}

    def start(self, pod_id):
        self.calls.append("start")

    def stop(self, pod_id):
        self.calls.append("stop")


class Funding(Workspace):
    def test_official_balance_query_uses_bearer_and_no_profile_fields(self):
        calls = []
        def send(*args):
            calls.append(args)
            return {"data": {"myself": {"clientBalance": 12.34}}}
        client = runpod.RunPodClient("fake-private-key", send=send)
        self.assertEqual(client.balance(), 12.34)
        url, method, body, headers = calls[0]
        self.assertEqual((url, method), ("https://api.runpod.io/graphql", "POST"))
        self.assertEqual(body, {"query": "query NovaFunding { myself { clientBalance } }"})
        self.assertEqual(headers, {"Authorization": "Bearer fake-private-key"})
        self.assertNotIn("fake-private-key", url + json.dumps(body))

    def test_graphql_errors_and_invalid_values_are_sanitized(self):
        for reply in ({"errors": [{"message": "private-provider-detail"}]}, None,
                      {"data": None}, {"data": {"myself": None}},
                      *[{"data": {"myself": {"clientBalance": value}}}
                        for value in (None, True, "5", float("nan"), float("inf"))]):
            with self.subTest(reply=reply):
                client = runpod.RunPodClient("fake-private-key", send=lambda *args: reply)
                with self.assertRaises(runpod.RunPodError) as caught:
                    client.balance()
                self.assertNotIn("private", str(caught.exception))

    def test_missing_api_key_is_unconfigured_not_zero(self):
        with patch.object(runpod, "RunPodClient", side_effect=AssertionError("network forbidden")):
            result = runpod.funding_status(5, 3)
        self.assertEqual(result["state"], "unconfigured")
        self.assertIsNone(result["balance_usd"])
        self.assertIn("Google", result["message"])

    def test_unknown_credit_never_becomes_zero_or_exposes_provider_error(self):
        for value in (None, True, "0", float("nan"), float("inf"), RuntimeError("private-key-secret")):
            result = runpod.funding_status(5, 3, FakeCredit(value))
            self.assertEqual(result["state"], "unavailable")
            self.assertIsNone(result["balance_usd"])
            self.assertNotIn("private-key-secret", json.dumps(result))

    def test_zero_credit_requires_recharge(self):
        result = runpod.funding_status(5, 3, FakeCredit(0.0))
        self.assertEqual((result["state"], result["balance_usd"], result["shortfall_usd"]),
                         ("insufficient", 0.0, 3.0))
        self.assertIn("Billing", result["message"])
        self.assertEqual(result["billing_url"], runpod.BILLING_URL)

    def test_one_hour_minimum_and_available_only_status(self):
        result = runpod.funding_status(0.5, 3.0, FakeCredit(2.0))
        self.assertEqual((result["required_usd"], result["shortfall_usd"]), (3.0, 1.0))
        self.assertEqual(runpod.funding_status(3, 3, FakeCredit(3))["state"], "sufficient")
        read_only = runpod.funding_status(client=FakeCredit(10))
        self.assertEqual(read_only["state"], "available")
        self.assertIsNone(read_only["required_usd"])

    def test_invalid_requirements_do_not_query_credit(self):
        for value in (-1, True, float("nan"), float("inf"), "bad"):
            for key in ("required_usd", "per_hour"):
                client = FakeCredit()
                with self.assertRaises(ValueError):
                    runpod.funding_status(client=client, **{key: value})
                self.assertEqual(client.calls, [])

    def runner(self, client, existing=None, **kwargs):
        key = self.ws / "fake-key"
        key.write_text("fixture-only", encoding="utf-8")
        runner = runpod.RunPodRunner(client, existing, str(key),
                                    run=lambda *a, **kw: self.fail("SSH forbidden"), **kwargs)
        runner.paid_confirmed = True
        return runner

    def test_insufficient_and_unknown_credit_never_mutate_a_pod(self):
        for balance in (0, None, RuntimeError("offline")):
            for existing in (None, "existing-fixture"):
                client = FakeCredit(balance)
                runner = self.runner(client, existing)
                with self.assertRaises(runpod.RunPodError) as caught:
                    runner.run(self.ws / "bundle", self.ws / "out", jobs.Job("train", "fixture"))
                self.assertIn("No paid pod was started", str(caught.exception))
                self.assertTrue(all(call in ("balance", "pod") for call in client.calls))

    def test_credit_is_rechecked_after_estimate(self):
        client = FakeCredit(100)
        runner = self.runner(client)
        estimate = runner.estimate({"estimate_hours": 1})
        self.assertEqual(estimate["funding"]["state"], "sufficient")
        self.assertEqual(estimate["data_center_ids"], ["AP-JP-1"])
        client.credit = 0
        with self.assertRaises(runpod.RunPodError):
            runner.run(self.ws / "bundle", self.ws / "out", jobs.Job("train", "fixture"))
        self.assertEqual(client.calls.count("balance"), 2)
        self.assertFalse(any(isinstance(call, tuple) for call in client.calls))

    def test_new_pod_uses_explicit_japan_default_and_ordered_options(self):
        for regions in (None, ["AP-JP-1", "AP-IN-1"]):
            client = FakeCredit()
            runner = self.runner(client, data_center_ids=regions)
            self.assertEqual(runner._create(jobs.Job("train", "fixture")), "fake-new-pod")
            kind, body = client.calls[0]
            self.assertEqual(kind, "create")
            self.assertEqual(body["dataCenterIds"], regions or ["AP-JP-1"])
            self.assertEqual(body["dataCenterPriority"], "custom")

    def test_unavailable_region_has_no_fallback_and_error_is_sanitized(self):
        client = FakeCredit()
        def unavailable(body):
            client.calls.append(("create", body))
            raise RuntimeError("private-provider-detail")
        client.create = unavailable
        runner = self.runner(client)
        with self.assertRaises(runpod.RunPodError) as caught:
            runner._create(jobs.Job("train", "fixture"))
        self.assertEqual(len(client.calls), 1)
        self.assertIn("No other region", str(caught.exception))
        self.assertIn("AP-JP-1", str(caught.exception))
        self.assertNotIn("private-provider-detail", str(caught.exception))

    def test_missing_paid_confirmation_never_queries_or_starts_pod(self):
        for value in (False, None, 0, 1, "true"):
            client = FakeCredit()
            runner = self.runner(client)
            runner.paid_confirmed = value
            with self.assertRaises(runpod.RunPodError):
                runner.run(self.ws / "bundle", self.ws / "out", jobs.Job("train", "fixture"))
            self.assertEqual(client.calls, [])

    def test_estimate_above_credit_warns_but_only_one_hour_is_required(self):
        result = runpod.funding_status(20, 4.59, FakeCredit(10))
        self.assertEqual(result["state"], "sufficient")
        self.assertEqual(result["required_usd"], 4.59)
        self.assertTrue(result["estimate_exceeds_balance"])
        self.assertEqual(result["estimated_cost_usd"], 20)
        self.assertIn("will not recharge", result["message"])

    def test_missing_actual_price_stops_new_pod_before_training(self):
        client = FakeCredit(100)
        client.pod = lambda pod_id: {"desiredStatus": "RUNNING"}
        runner = self.runner(client)
        with self.assertRaises(runpod.RunPodError) as caught:
            runner.run(self.ws / "bundle", self.ws / "out", jobs.Job("train", "fixture"))
        self.assertIn("valid actual GPU price", str(caught.exception))
        self.assertIn("stop", client.calls)

    def test_ordinary_upload_timeout_still_stops(self):
        import subprocess
        client = FakeCredit(100)
        client.pod = lambda pod_id: {"costPerHr": 3.0, "desiredStatus": "RUNNING", "publicIp": "192.0.2.1", "portMappings": {"22": 22}}
        runner = self.runner(client)
        timeouts = []
        def fake_process(args, **kwargs):
            timeouts.append((args[0], kwargs["timeout"]))
            if args[0] == "scp":
                raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        runner._run = fake_process
        with self.assertRaises(subprocess.TimeoutExpired):
            runner.run(self.ws / "bundle", self.ws / "out", jobs.Job("train", "fixture"))
        self.assertEqual(timeouts, [("ssh", 30), ("ssh", 120), ("scp", 3600)])
        self.assertEqual(client.calls[-2:], ["stop", "balance"])

    def test_shortfall_rounds_cents_without_binary_float_extra_cent(self):
        result = runpod.funding_status(10, 3.2, client=FakeCredit(0.1))
        self.assertEqual(result["shortfall_usd"], 3.1)

    def test_invalid_regions_fail_before_provider_call(self):
        for regions in ([], [""], [None], ["anywhere"], "AP-JP-1"):
            client = FakeCredit()
            with self.assertRaises(runpod.RunPodError):
                self.runner(client, data_center_ids=regions)
            self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
