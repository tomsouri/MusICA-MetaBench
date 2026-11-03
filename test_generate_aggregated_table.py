# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Tests for aggregating runs limited to some modalities in generate_aggregated_table.py.

Run from the repository root:
.venv/bin/python3 test_generate_aggregated_table.py
"""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from generate_aggregated_table import aggregate_results

FULL = [("OVERALL", "ALL", 300, 50.0), ("submodality", "audio", 100, 30.0), ("submodality", "symbolic", 100, 70.0), ("submodality", "visual", 100, 50.0)]
NO_AUDIO = [("OVERALL", "ALL", 200, 80.0), ("submodality", "symbolic", 100, 90.0), ("submodality", "visual", 100, 70.0)]


def write_run(root, model, rows):
    run_dir = Path(root) / model / "20" / "normal"
    run_dir.mkdir(parents=True)
    columns = ["Criterion_Type", "Criterion_Value", "Total_Items", "Accuracy_Percent"]
    pd.DataFrame(rows, columns=columns).to_csv(run_dir / "rs52.res.tsv", sep="\t", index=False)


class PartialRunTests(unittest.TestCase):
    def check_partial_run(self, full_model, partial_model):
        with tempfile.TemporaryDirectory() as root:
            write_run(root + "/models", full_model, FULL)
            write_run(root + "/models", partial_model, NO_AUDIO)
            output = Path(root) / "out.tsv"
            aggregate_results(root + "/models", "20", 52, ["Accuracy_Percent"], "normal", output, False)
            table = pd.read_csv(output, sep="\t")

        self.assertEqual(table["Criterion_Value"].tolist(), ["ALL", "audio", "symbolic", "visual"])
        self.assertEqual(table["Total_Items"].tolist(), [300, 100, 100, 100])
        self.assertEqual(table[full_model].tolist(), [50.0, 30.0, 70.0, 50.0])
        self.assertTrue(pd.isna(table[partial_model][1]))
        self.assertEqual(table[partial_model].dropna().tolist(), [80.0, 90.0, 70.0])

    def test_partial_run_is_aligned_by_criterion(self):
        self.check_partial_run("a-full", "b-partial")
        self.check_partial_run("b-full", "a-partial")

    def test_full_runs_with_different_total_items_still_raise(self):
        with tempfile.TemporaryDirectory() as root:
            write_run(root, "a", FULL)
            write_run(root, "b", [("OVERALL", "ALL", 299, 50.0)] + FULL[1:])
            with self.assertRaisesRegex(ValueError, "Consistency error"):
                aggregate_results(root, "20", 52, ["Accuracy_Percent"], "normal", Path(root) / "out.tsv", False)

    def test_partial_run_with_unknown_criterion_raises(self):
        with tempfile.TemporaryDirectory() as root:
            write_run(root, "a", FULL)
            write_run(root, "b", [("OVERALL", "ALL", 100, 50.0), ("submodality", "unknown", 100, 50.0)])
            with self.assertRaisesRegex(ValueError, "Consistency error"):
                aggregate_results(root, "20", 52, ["Accuracy_Percent"], "normal", Path(root) / "out.tsv", False)


if __name__ == "__main__":
    unittest.main()
