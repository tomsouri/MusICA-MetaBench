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

import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import requests

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


if __name__ == "__main__":
    unittest.main()
