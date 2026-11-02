# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Tests for run_benchmark.py. All HTTP is mocked, nothing is sent to any API.

To run:
.venv/bin/python3 test_run_benchmark.py
"""

import csv
import json
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

import requests
import yaml

import run_benchmark


def fake_response(status: int, body) -> requests.Response:
    """Builds a real Response, so that raise_for_status and json behave as in production."""
    response = requests.Response()
    response.status_code = status
    response._content = (body if isinstance(body, str) else json.dumps(body)).encode()
    return response


class ApiErrorTests(unittest.TestCase):
    error = {"error": {"code": 400, "message": "Provider error", "metadata": {"raw": "upstream detail"}}}

    def call(self, *responses):
        """Runs call_api_with_backoff on the given responses and returns (result, error log content)."""
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(run_benchmark.requests, "post", side_effect=list(responses)), \
                mock.patch.object(run_benchmark.time, "sleep"), \
                mock.patch.object(run_benchmark.random, "uniform", return_value=0):
            log_path = os.path.join(tmp, "api_errors.log")
            result = run_benchmark.call_api_with_backoff("http://test", {}, {"model": "m"}, max_waiting_time=5, error_log_path=log_path)
            log = pathlib.Path(log_path).read_text(encoding="utf-8") if os.path.exists(log_path) else ""
        return result, log

    def test_http_error_keeps_metadata_and_retried_failure_is_logged(self):
        result, log = self.call(fake_response(400, self.error), fake_response(200, {"choices": []}))
        self.assertEqual(result, {"choices": []})
        self.assertIn("upstream detail", log)

    def test_final_failure_is_retained(self):
        failure = requests.exceptions.ConnectionError("connection lost")
        with mock.patch.object(run_benchmark.time, "time", side_effect=[0, 0, 0, 0, 0, 100]):
            result, log = self.call(fake_response(400, self.error), failure)
        self.assertEqual(len(result["original_errors"]), 2)
        self.assertIn("upstream detail", result["original_errors"][0])
        self.assertIn("connection lost", result["original_errors"][1])
        self.assertIn("connection lost", log)

    def test_non_json_body_is_kept(self):
        self.assertEqual(run_benchmark.format_api_error(fake_response(502, "<html>Bad gateway</html>")), "<html>Bad gateway</html>")

    def test_error_in_http_200_is_reported(self):
        result, log = self.call(fake_response(200, self.error))
        self.assertEqual(result, self.error)
        self.assertIn("upstream detail", log)


class PromptCachingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.context_file = os.path.join(tmp.name, "score.png")
        pathlib.Path(self.context_file).write_bytes(b"png")

    def content(self, prompt_caching, **kwargs):
        args = {"model": "m", "user_prompt": "Question", "system_prompt": None, "content_file": self.context_file,
                "modality": "visual", "submodality": "visual.short.png", **kwargs}
        payload, _ = run_benchmark.prepare_llm_payload(prompt_caching=prompt_caching, **args)
        return payload["messages"][-1]["content"]

    def test_disabled_sends_no_cache_control(self):
        content = self.content({"enabled": False, "file_first": True, "ttl": "1h"})
        self.assertEqual([part["type"] for part in content], ["text", "image_url"])
        self.assertNotIn("cache_control", json.dumps(content))

    def test_defaults_keep_question_first(self):
        for prompt_caching in (None, {"enabled": True}):
            question, image = self.content(prompt_caching)
            self.assertEqual(question["cache_control"], {"type": "ephemeral"})
            self.assertEqual(image["type"], "image_url")

    def test_file_first_puts_breakpoint_after_file(self):
        image, marker, question = self.content({"file_first": True, "ttl": "1h"})
        self.assertEqual(image["type"], "image_url")
        self.assertEqual(marker["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        self.assertEqual((question["text"], "cache_control" in question), ("Question", False))

    def test_no_content_file(self):
        content = self.content({"file_first": True}, no_content_file=True)
        self.assertEqual(len(content), 1)
        self.assertIn("cache_control", content[0])


def make_item(item_id: str, modality: str, context_file: str) -> dict:
    return {"item_id": item_id, "question": "Which note?", "labeled_final_options": json.dumps(["(A) G4", "(B) F4"]),
            "all_choices": json.dumps(["A", "B"]), "index2ans": json.dumps({"A": "G4", "B": "F4"}),
            "label_of_final_correct_option": "A", "path_to_question_context_file": context_file,
            "modality": modality, "submodality": f"{modality}.abc.txt"}


def write_benchmark(path: str, context_file: str, modalities=("symbolic",)):
    """Writes a tiny benchmark TSV with one item per given modality."""
    items = [make_item(f"item{i}", modality, context_file) for i, modality in enumerate(modalities)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(items[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(items)


class MainTestCase(unittest.TestCase):
    """Runs main() end to end on a tiny benchmark, with mocked HTTP."""
    api_response = {"choices": [{"message": {"content": "Answer: A"}}], "usage": {"cost": 0.01}}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.context_file = os.path.join(self.tmp, "piece.abc.txt")
        pathlib.Path(self.context_file).write_text("X:1\nK:C\nCDEF|")

    def run_main(self, overrides=None, argv=(), modalities=("symbolic",), zdr_models=("m",), zdr_status=200):
        """Runs main() and returns the mocked requests.post, so that sent payloads can be inspected."""
        with open("eval-config.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        benchmark_file = os.path.join(self.tmp, "benchmark.tsv")
        write_benchmark(benchmark_file, self.context_file, modalities)
        config.update({"models": ["m"], "benchmark_file": benchmark_file, "logdir": self.tmp, "evaluation_criteria": [],
                       "evaluation_output_file": None, "log_to_google_sheet": False, **(overrides or {})})
        config_path = os.path.join(self.tmp, "config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f)

        zdr_list = fake_response(zdr_status, {"data": [{"model_id": model} for model in zdr_models]})
        self.post = post = mock.Mock(side_effect=lambda *a, **k: fake_response(200, self.api_response))
        with mock.patch.object(sys, "argv", ["run_benchmark.py", "--config", config_path, *argv]), \
                mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), \
                mock.patch.object(run_benchmark.requests, "get", return_value=zdr_list) as self.get, \
                mock.patch.object(run_benchmark.requests, "post", post):
            run_benchmark.main()
        return post

    @staticmethod
    def sent_zdr(post):
        """Returns {model: zdr flag} of the sent requests."""
        return {call.kwargs["json"]["model"]: call.kwargs["json"]["provider"]["zdr"] for call in post.call_args_list}


class ZdrTests(MainTestCase):
    aggregate = {"models": ["agg"], "supported_aggregate_models": {"agg": {"audio": "a", "symbolic": "s", "visual": "v"}}}

    def test_available_keeps_zdr(self):
        self.assertEqual(self.sent_zdr(self.run_main()), {"m": True})

    def test_missing_stops_before_any_model_call(self):
        with self.assertRaisesRegex(ValueError, "No ZDR endpoint available for \\['m'\\].*--disable_zdr"):
            self.run_main(zdr_models=())
        self.post.assert_not_called()

    def test_missing_with_turn_off_switches_only_that_model(self):
        post = self.run_main({"turn_zdr_off_if_no_zdr_endpoint_available": True, **self.aggregate},
                             modalities=("symbolic", "visual"), zdr_models=("v",))
        self.assertEqual(self.sent_zdr(post), {"s": False, "v": True})

    def test_aggregate_ignores_filtered_out_modalities(self):
        post = self.run_main(self.aggregate, zdr_models=("s",))
        self.assertEqual(self.sent_zdr(post), {"s": True})

    def test_list_fetch_failure_stops(self):
        with self.assertRaisesRegex(ValueError, "cannot be verified"):
            self.run_main(zdr_status=500)

    def test_disabled_in_config_or_cmdline_skips_check(self):
        for overrides, argv in (({"zdr": False}, ()), ({}, ("--disable_zdr",))):
            post = self.run_main(overrides, argv, zdr_models=())
            self.assertEqual(self.sent_zdr(post), {"m": False})
            self.get.assert_not_called()


class WaitForApprovalTests(unittest.TestCase):
    def wait(self, stdin_text=None, close=False, timeout=0.01, on_timeout="stop"):
        read_end, write_end = os.pipe()
        with os.fdopen(read_end) as stdin, os.fdopen(write_end, "w") as writer, mock.patch.object(sys, "stdin", stdin):
            if stdin_text:
                writer.write(stdin_text)
                writer.flush()
            if close:
                writer.close()
            run_benchmark.wait_for_approval(timeout, on_timeout)

    def test_enter_approves(self):
        self.wait("\n", timeout=30)

    def test_timeout_stops_with_error(self):
        with self.assertRaises(SystemExit) as exit_info:
            self.wait()
        self.assertIn("No approval", str(exit_info.exception.code))

    def test_timeout_can_continue(self):
        self.wait(on_timeout="continue")

    def test_closed_stdin_does_not_wait_and_is_no_approval(self):
        start = time.monotonic()
        with self.assertRaises(SystemExit):
            self.wait(close=True, timeout=30)
        self.wait(close=True, timeout=30, on_timeout="continue")
        self.assertLess(time.monotonic() - start, 5)


class CostEstimateTests(MainTestCase):
    def estimate(self, items, post_response=None):
        with open("eval-config.yaml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        config.update({"models": ["m1", "m2"], "dry_run": False, "zdr": True, "api_error_log": None})
        post = mock.Mock(side_effect=lambda *a, **k: post_response(k["json"]) if post_response else fake_response(200, self.api_response))
        with mock.patch.object(run_benchmark.requests, "post", post):
            return run_benchmark.estimate_cost(config, items, set()), post

    def context_file_of_size(self, size):
        path = os.path.join(self.tmp, f"{size}.txt")
        pathlib.Path(path).write_text("x" * size)
        return path

    def test_scales_each_modality_by_its_item_count_per_model(self):
        items = [make_item(str(i), "symbolic", self.context_file) for i in range(3)] + [make_item("v", "visual", self.context_file)]
        (total, complete), post = self.estimate(items)
        self.assertEqual(post.call_count, 4)
        self.assertAlmostEqual(total, 2 * (3 + 1) * 0.01)
        self.assertTrue(complete)

    def test_samples_the_median_context_size(self):
        items = [make_item(str(size), "symbolic", self.context_file_of_size(size)) for size in (300, 1, 20)]
        _, post = self.estimate(items)
        sent = post.call_args_list[0].kwargs["json"]["messages"][-1]["content"]
        self.assertTrue(any("x" * 20 in part["text"] and "x" * 21 not in part["text"] for part in sent))

    def test_failed_sample_gives_lower_bound(self):
        def respond(payload):
            return fake_response(200, {"error": {"message": "failed"}} if payload["model"] == "m2" else self.api_response)
        (total, complete), _ = self.estimate([make_item("1", "symbolic", self.context_file)], respond)
        self.assertAlmostEqual(total, 0.01)
        self.assertFalse(complete)

    def test_approved_run_matches_a_run_without_estimate(self):
        def seeds(post):
            return [call.kwargs["json"]["seed"] for call in post.call_args_list]
        modalities = ("symbolic", "visual")
        plain = seeds(self.run_main(modalities=modalities))
        with mock.patch.object(run_benchmark, "wait_for_approval") as wait:
            estimated = seeds(self.run_main(argv=("--cost_estimate",), modalities=modalities))
        wait.assert_called_once_with(120, "stop")
        self.assertEqual(estimated[2:], plain)

    def test_refused_run_sends_only_the_samples(self):
        with mock.patch.object(run_benchmark, "wait_for_approval", side_effect=SystemExit("stop")), self.assertRaises(SystemExit):
            self.run_main({"cost_estimate": {"enabled": True}}, modalities=("symbolic", "visual"))
        self.assertEqual(self.post.call_count, 2)

    def test_off_by_default_and_skipped_on_dry_run(self):
        with mock.patch.object(run_benchmark, "estimate_cost") as estimate:
            self.run_main()
            self.run_main(argv=("--cost_estimate", "--dry_run"))
        estimate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
