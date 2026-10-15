# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Export the quiz items of the online demo (docs/index.html) to docs/items.json.

Reads the per-item inference logs (logs.tsv) of the eight models reported in the paper
for the ChoraleBricks instance benchmarks/qs_per_subcat_20/seed_52.tsv, checks that each
log reproduces the result file committed under results/, selects about 20 items and
writes them in the order the demo shows them.

Usage (from the repository root):
    python docs/export_demo.py <dir containing the run_*_normal-<model>-20-52 directories>
"""

import collections
import csv
import glob
import json
import os
import sys

csv.field_size_limit(sys.maxsize)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
BENCHMARK = os.path.join(ROOT, "benchmarks", "qs_per_subcat_20", "seed_52.tsv")
# Score images are shown from the ChoraleBricks website and not copied here: its sheet music
# is "published with the kind permission of the rights holder", unlike the CC BY 4.0 audio.
SCORE_URLS = os.path.join(ROOT, "data", "original", "chorale-bricks", "list-of-pngs.txt")
PIECE_PAGE = "https://www.audiolabs-erlangen.de/resources/MIR/2025-ChoraleBricks/"

# The eight models of the paper's figure, in its order. Display names follow
# shorten_model_name() in src/plotting/generate_bar_chart.py.
MODELS = {
    "google_gemini-3.1-pro-preview": "Gemini 3.1 Pro",
    "Qwen_Qwen3-Omni-30B-A3B-Thinking": "Qwen3 Omni 30B",
    "google_gemini-3.1-flash-lite-preview": "Gemini 3.1 FL",
    "aggregate-gpt-5": "agg-GPT-5",
    "google_gemini-2.5-flash-lite": "Gemini 2.5 FL",
    "aggregate-gpt-4o": "agg-GPT-4o",
    "google_gemini-2.0-flash-lite-001": "Gemini 2.0 FL",
    "aggregate-mistral": "agg-Mistral",
}
PAIR_MODEL = "google_gemini-3.1-pro-preview"

N_PAIRS, N_EASY, N_TOTAL = 3, 4, 20
EASY_MIN_CORRECT = 7          # "answered correctly by (almost) all models"
SPLIT_RANGE = range(3, 6)     # "models disagree": 3 to 5 of the 8 correct
ABC_PREFIX = "--- Attached Symbolic Data ---\n"


def read_tsv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def reproduces_reported_result(rows, reported):
    """True if the counts recomputed from the log equal every row of the result file."""
    for r in reported:
        ctype, cvalue = r["Criterion_Type"], r["Criterion_Value"]
        sel = rows if ctype == "OVERALL" else [x for x in rows if x[ctype] == cvalue]
        got = (len(sel),
               sum(x["is_correct"] == "True" for x in sel),
               sum(x["label_of_answer"] == "UNPARSABLE" for x in sel))
        if got != (int(r["Total_Items"]), int(r["Correct_Items"]), int(r["Unparsable_Items"])):
            return False
    return True


def load_logs(logs_dir, bench_ids):
    logs = {}
    for model in MODELS:
        reported = glob.glob(os.path.join(ROOT, "results", model, "20", "normal",
                                          "jobid_*.rs52.rep1.res.tsv"))
        assert len(reported) == 1, f"{model}: expected one reported result file, got {reported}"
        reported = read_tsv(reported[0])
        # Several runs can share the name (e.g. a ChoralSynth run with the same size and
        # seed); only the one that reproduces the reported result file is the reported run.
        for run in sorted(glob.glob(os.path.join(logs_dir, f"run_*_normal-{model}-20-52"))):
            rows = read_tsv(os.path.join(run, "logs.tsv"))
            if [r["item_id"] for r in rows] == bench_ids and reproduces_reported_result(rows, reported):
                logs[model] = {r["item_id"]: r for r in rows}
                print(f"verified  {MODELS[model]:15s} {os.path.basename(run)}")
                break
            print(f"WARNING: {os.path.basename(run)} does not reproduce the reported results, skipped")
        assert model in logs, f"{model}: no log reproducing the reported results in {logs_dir}"
    return logs


def select(bench, logs):
    """Return the selected benchmark rows in demo order."""
    n_correct = {r["item_id"]: sum(logs[m][r["item_id"]]["is_correct"] == "True" for m in MODELS)
                 for r in bench}
    chosen = []

    def load_of(r):
        # how crowded r's subcategory, modality and piece already are among the chosen items
        return sum((c["subcategory"] == r["subcategory"]) + (c["modality"] == r["modality"])
                   + (c["piece_id"] == r["piece_id"]) for c in chosen)

    # Failure pairs: same question on the same piece, audio wrong and ABC right for PAIR_MODEL.
    groups = collections.defaultdict(dict)
    for r in bench:
        groups[(r["meta-question_id"], r["piece_id"], r["question"])][r["modality"]] = r
    candidates = [(g["audio"], g["symbolic"]) for g in groups.values()
                  if logs[PAIR_MODEL][g["audio"]["item_id"]]["is_correct"] == "False"
                  and logs[PAIR_MODEL][g["symbolic"]["item_id"]]["is_correct"] == "True"]
    # strongest contrast across all models first
    candidates.sort(key=lambda p: (n_correct[p[0]["item_id"]] - n_correct[p[1]["item_id"]],
                                   p[0]["item_id"]))
    pairs = []
    for audio, symbolic in candidates:
        if len(pairs) < N_PAIRS and all(audio["subcategory"] != p[0]["subcategory"]
                                        and audio["piece_id"] != p[0]["piece_id"] for p in pairs):
            pairs.append((audio, symbolic))
            chosen += [audio, symbolic]

    def pick(pool, n, tiebreak):
        picked = []
        for _ in range(n):
            pool = [r for r in pool if r not in chosen]
            best = min(pool, key=lambda r: (load_of(r), tiebreak(r), r["item_id"]))
            picked.append(best)
            chosen.append(best)
        return picked

    easy = pick([r for r in bench if n_correct[r["item_id"]] >= EASY_MIN_CORRECT],
                N_EASY, lambda r: -n_correct[r["item_id"]])
    split = pick([r for r in bench if n_correct[r["item_id"]] in SPLIT_RANGE],
                 N_TOTAL - len(chosen), lambda r: abs(n_correct[r["item_id"]] - 4))

    # One fixed sequence: a pair opens, the other pairs are spread, easy items mixed in.
    singles = []
    for i, r in enumerate(split):
        singles.append(r)
        if i % 3 == 1 and easy:
            singles.append(easy.pop(0))
    singles += easy
    third = len(singles) // 3
    return ([*pairs[0]] + singles[:third] + [*pairs[1]] + singles[third:2 * third]
            + [*pairs[2]] + singles[2 * third:]), pairs, n_correct


def export_item(r, logs, score_urls):
    answers = []
    for model, name in MODELS.items():
        log = logs[model][r["item_id"]]
        answers.append({"model": name, "answer": log["label_of_answer"],
                        "correct": log["is_correct"] == "True",
                        "response": log["extracted_response"]})
    item = {
        "item_id": r["item_id"],
        "question": r["question"],
        "skill": r["subcategory"],
        "rel_abs": r["rel/abs"],
        "modality": r["modality"],
        "piece_id": r["piece_id"],
        "piece_page": PIECE_PAGE + r["piece_id"],
        "options": json.loads(r["labeled_final_options"]),
        "correct": r["label_of_final_correct_option"],
        "answers": answers,
    }
    if r["modality"] == "audio":
        item["stimulus"] = f"assets/{r['piece_id']}/audio.m4a"
    elif r["modality"] == "visual":
        item["stimulus"] = score_urls[r["piece_id"]]
    else:
        # the ABC text exactly as it was sent to the model
        text = json.loads(logs[PAIR_MODEL][r["item_id"]]["parameters"])["messages"][0]["content"][1]["text"]
        assert text.startswith(ABC_PREFIX)
        item["abc"] = text[len(ABC_PREFIX):]
    return item


def main(logs_dir):
    bench = read_tsv(BENCHMARK)
    logs = load_logs(logs_dir, [r["item_id"] for r in bench])
    sequence, pairs, n_correct = select(bench, logs)
    with open(SCORE_URLS, encoding="utf-8") as f:
        score_urls = {url.split("/")[-3]: url for url in f.read().split()}
    items = [export_item(r, logs, score_urls) for r in sequence]

    # Self-check of the selection.
    assert len(items) == N_TOTAL == len({i["item_id"] for i in items})
    for i in items:
        assert len(i["options"]) == 5 and i["correct"] in "ABCDE"
        assert all(a["answer"] in ("A", "B", "C", "D", "E", "UNPARSABLE", "MODEL_ERROR")
                   for a in i["answers"]) and len(i["answers"]) == len(MODELS)
    ids = [i["item_id"] for i in items]
    assert len(pairs) == N_PAIRS and ids[0] == pairs[0][0]["item_id"]
    for audio, symbolic in pairs:
        assert ids.index(symbolic["item_id"]) == ids.index(audio["item_id"]) + 1
    assert sum(n_correct[i] >= EASY_MIN_CORRECT for i in ids) >= N_EASY
    assert {"relative", "absolute"} <= {i["rel_abs"] for i in items}
    missing = [i["stimulus"] for i in items
               if i["modality"] == "audio" and not os.path.exists(os.path.join(DOCS, i["stimulus"]))]

    with open(os.path.join(DOCS, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)

    pair_ids = {r["item_id"] for p in pairs for r in p}
    print(f"\n{'#':>2}  {'kind':5} {'modality':8} {'skill':22} {'ok/8':>4}  piece / question")
    for n, i in enumerate(items, 1):
        kind = "pair" if i["item_id"] in pair_ids else (
            "easy" if n_correct[i["item_id"]] >= EASY_MIN_CORRECT else "split")
        print(f"{n:>2}  {kind:5} {i['modality']:8} {i['skill']:22} {n_correct[i['item_id']]:>4}  "
              f"{i['piece_id']}: {i['question']}")
    print("\nmodalities:", dict(collections.Counter(i["modality"] for i in items)))
    print("skills:    ", dict(collections.Counter(i["skill"] for i in items)))
    assert not missing, f"audio files missing under docs/: {sorted(set(missing))}"


if __name__ == "__main__":
    main(sys.argv[1])
