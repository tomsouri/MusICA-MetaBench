# Music I Care About Meta-Benchmark (MusICA MetaBench)

**Generate a multiple-choice benchmark of music perception, on demand, from the music you care
about.** Give the pipeline a set of pieces and it produces questions about pitch, rhythm and
harmony, asking the same question of an audio recording, a score image and symbolic notation, so
that Multimodal Large Language Models can be compared across representations of the same music.
Ground truth is extracted programmatically from the MusicXML — **there is no LLM in the loop** at
generation time, so the answers are not a model's opinion about the music.

## What you need to bring

- **MusicXML for every piece.** This is where all ground truth comes from; it is the one hard
  requirement.
- **Whichever aligned modalities you want compared** — recordings, score images — of the *same*
  pieces in the *same* key.

Modalities you do not have can be synthesised: score images are rendered from the MusicXML with
MuseScore, and the symbolic condition is produced by converting MusicXML to ABC. See
[CONTRIBUTING.md](CONTRIBUTING.md#adding-a-dataset).

## Current status

Read this before planning work around the pipeline.

- **Verified on two datasets: ChoraleBricks and ChoralSynth.** Extending to the second one
  required real adaptation of the extraction code, not just configuration — see the table below.
  **A new corpus should be expected to need some adaptation too.**
- **Supports tonal repertoire made of one or more monophonic voices** (choral, wind, string).
  Non-tonal music, and polyphonic instruments such as piano, need changes to the question
  templates and the ground-truth extraction.
- **MusicXML is the only verified symbolic input.** MIDI, ABC, LilyPond and Humdrum may work but
  have not been tested.
- Ground-truth extraction should be spot-checked by hand on any new corpus before a full run.

### Datasets known to work

| Dataset | Status | Notes |
| :--- | :--- | :--- |
| [ChoraleBricks](https://doi.org/10.5281/zenodo.15081741) | Verified | Primary development dataset. `prepare_data.sh` downloads and prepares it. |
| [ChoralSynth](https://doi.org/10.5281/zenodo.10161065) | Verified — required adaptation | Lives on the `dataset-choralsynth` branch, **not merged into `main`**. Needed: voices addressed by number instead of the hard-coded `S`/`A`/`T`/`B` mapping; part names extracted from the score behind a `use_xml_part_names` setting; a monophonicity check that skips non-conforming voices; skipping questions when a piece lacks the expected voice count; enharmonic tonality names and a guard for ground truth absent from the ontology; and handling of larger pieces in data preparation. |
| Anything else | Unverified | — |

## Links

- **Preprint:** [*Music I Care About: Automated Multimodal Benchmarking of LLM Music Perception
  Skills on (Almost) Any Music*](https://arxiv.org/abs/2607.06015) (arXiv:2607.06015) — the code,
  data preparation scripts, benchmark instances, inference logs and results behind it are all in
  this repository.
- **Late-breaking demo:** *Bring Your Own Music: Towards Community-Built, On-Demand Benchmarks of
  MLLM Music Perception*, submitted to the ISMIR 2026 Late-Breaking Demo track.
- **[Online demo](https://tomsouri.github.io/MusICA-MetaBench/)** — answer 20 generated benchmark
  items yourself and see what the eight evaluated models answered. Source in [docs/](docs/).
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — how to add a question template, a dataset or a format.
  Contributions are welcome; making question templates fully modality-neutral is an open problem
  we would particularly like help with.

## Which version is which

This repository is the permanent home of the project, and it keeps moving. Frozen states are
reachable by tag:

| Tag | What it is |
| :--- | :--- |
| `v0.0-preprint` | The state released with the arXiv preprint, including the license overhaul. This is what the preprint's link refers to. |
| `provenance-reported-results` | The tree behind the numbers reported in the preprint: it sits after every commit that added results, inference logs and plots. Check this out if you want to verify a reported figure. |

Papers link the repository **root**, not a tag, so that the link stays an invitation to
contribute rather than landing readers on a frozen tree; this table is how you get from the root
to a specific frozen state.

> **Note on the old repository name.** This repository was renamed from `MusICA-MetaBench-preprint`,
> and GitHub redirects the old URL — which matters, because that URL is printed in the published
> arXiv preprint and cannot be edited. **The name `MusICA-MetaBench-preprint` must never be reused
> for a new repository**: creating one silently breaks the redirect and orphans the published link.

## Key Features

- **8-Step Generation Pipeline**: Controlled generation of questions, ground truth, and distractors.
- **Multi-Modality**: Support for evaluating models on different representations of the same musical content — audio (WAV mastermixes), symbolic (MusicXML and ABC), and visual (PNG images of scores).
- **NOTA Support**: Includes "None of the above" as a correct answer for ~20% of questions to test for hallucination/over-confidence.
- **Extensible Configuration**: YAML-based setup for benchmarks, evaluations, and music theory ontologies.
- **Statistical Analysis**: Tools for significance testing (pairwise comparison) and aggregate reporting.

## Table of Contents
1. [Setup](#setup)
2. [Quick Start](#quick-start)
3. [Custom datasets, formats and questions](#custom-datasets-formats-and-questions)
4. [Dataset Information](#dataset-information)
5. [Inference & Parsing](#inference--parsing)
6. [Evaluation & Results](#evaluation--results)
7. [Project Structure](#project-structure)

## Setup

### Prerequisites
Before starting, ensure you have the following installed and configured:
- **Tools**: `ffmpeg`, `pdftoppm`, and **MuseScore**.
- **Display Access**: Required for score rendering (e.g., connect via `ssh -X` or `ssh -Y` if running remotely).
- **MuseScore Configuration**: The path to your MuseScore executable must be correctly set in [src/conversions/musicxml2pdf.py](src/conversions/musicxml2pdf.py) (see `get_musescore_path`).

### Environment
```bash
# Create a virtual environment and install dependencies
bash prepare_venv.sh
```

### API Configuration
Set your OpenRouter API key:
```bash
export OPENROUTER_API_KEY="your-api-key"
```
If not using OpenRouter, you can configure your own API endpoint and environment variable name with the API key in `eval-config.yaml`.

### Data Preparation

#### ChoraleBricks
```bash
# Download ChoraleBricks and process it to the required format
bash prepare_data.sh
```

#### ChoralSynth
```bash
# Checkout to a different branch
git checkout dataset-choralsynth

# Download ChoralSynth and process it to the required format
bash prepare_data_choral_synth.sh
```


## Quick Start

### Step A: Generate a Benchmark
```bash
.venv/bin/python generate_benchmark.py \
    --config benchmark-generation-config.yaml \
    --benchmark_file test_benchmark.tsv \
    --questions_per_subcategory_count 10 
```
*The `questions_per_subcategory_count` parameter specifies questions per category-modality combination.*

### Step B: Run Inference
```bash
.venv/bin/python3 run_benchmark.py \
    --config eval-config.yaml \
    --benchmark_file test_benchmark.tsv \
    --models "openai/gpt-4o"
```
See the logs from the benchmark evaluation in `logs/run_<datetime><other>/logs.tsv`, and the result table in `results/<model>/<benchmark-size>/<setup>`.

## Custom datasets, formats and questions

Applying the pipeline to your own music, adding a question template, or adding a new format is
documented in **[CONTRIBUTING.md](CONTRIBUTING.md)**, with a complete worked example:

- [Adding a question template](CONTRIBUTING.md#adding-a-question-template) — the extraction
  contract, registration in `meta-questions.tsv`, the ontology, and how to iterate for free before
  spending anything on inference.
- [Adding a dataset](CONTRIBUTING.md#adding-a-dataset) — requirements, directory layout,
  synthesising missing modalities, and the pitfalls that have actually bitten us.
- [Adding a new format or submodality](CONTRIBUTING.md#adding-a-new-format-or-submodality).
- [Designing questions that travel across modalities](CONTRIBUTING.md#designing-questions-that-travel-across-modalities)
  — why an absolute pitch question is not a fair question to ask of a recording.

## Dataset Information

### ChoraleBricks
- **Benchmark Instance:** [seed_52.tsv](benchmarks/qs_per_subcat_20/seed_52.tsv) (the one used as the one instance in the experiments)

### ChoralSynth
- **Benchmark Instance:** [choralsynth.size20.seed_52.tsv](benchmarks/choralsynth.size20.seed_52.tsv) (the one used as the one instance in the experiments)

## Inference & Parsing

### User Prompt Template
The prompt template defines how the question and musical context are presented to the LLM. It can be customized in [eval-config.yaml](eval-config.yaml).
- **Template Variable:** `user_prompt_template`
- **Placeholder Replacement:** `<FORMAT>`, `<QUESTION>`, `<OPTIONS_TEXT>`, and `<OPTION_LABELS>` are dynamically replaced during runtime.

### Response Parsing
Responses are parsed to extract the final letter choice. The logic is:
1. **Extraction**: `run_benchmark.py` uses methods loaded from `src/extraction_methods.py` (configured via `path_to_extraction_file`). The methods used now are in `src/mmmu_eval_utils` (adapted from MMMU benchmark).
2. **Format**: The model is instructed to end with `Final Answer: <answer>`.
3. **Regex**: A regex typically searches for the last occurrence of a single letter enclosed in parentheses or following "Final Answer:".

## Evaluation & Results

### Per-Category Analysis

![Per-Category Analysis](aggregated/results-for-paper/chorale-bricks/plots/spiders/subcategory-chorale-bricks_s20_seed52_all.png)
Results, Chorale-bricks, s=300 (20 questions per modality-category pair), one benchmark instance, comparison across categories. Axes for accuracy end at 80%.

### Technical Setup of Running LLMs

- **Environment:** Tested on Linux (Ubuntu 22.04) using Python 3.10+.
- **LLM API & Infrastructure:**
  - **OpenRouter API:** Most models are accessed via a unified [OpenRouter API](https://openrouter.ai/).
  - **Local Deployment:** Qwen-3-omni (specifically `Qwen3-Omni-30B-A3B-Thinking`, full precision) is run locally using [vLLM](https://docs.vllm.ai/) on an NVIDIA GH200 superchip (144GB GPU VRAM).
- **Data Privacy & Leakage Prevention:**
  - **Leakage Prevention:** Use of endpoints that may train on inputs is disabled.
  - **Zero Data Retention (ZDR):** Enabled via [OpenRouter ZDR](https://openrouter.ai/docs/guides/features/zdr) where available (note: this was not available for GPT-family audio models).
- **Inference Configuration:**
  - **Data Encoding:** Symbolic musical files are sent as raw text; audio and image files are sent using Base64 encoding.
  - **Parameters:** Models use default parameters to reflect real-world usage, with the exception of the random seed.
  - **Reproducibility:** A pseudo-random seed is generated for each inference call to ensure better reproducibility (successfully achieved for local Qwen-3-omni, though limited for OpenRouter endpoints). We use distributed seeds rather than a single fixed seed to evaluate the model as a distribution rather than a single fixed instance.


### LLM Inference Logs
Full logs of the inference (prompts and raw JSON responses, parsed and evaluated responses) are provided for the best-performing model, Gemini 3.1 Pro Preview: 
- [Link to Logs Directory](logs/run_2026-04-19_210028_normal-google_gemini-3.1-pro-preview-20-52/logs.tsv) 

### Reproducing Results

There is no single one-shot reproduction command; the full experiment grid was run on a cluster.
The entry points are:

| Script | What it does |
| :--- | :--- |
| [run_all.sh](run_all.sh) | The entry point for the whole experiment grid. Generates benchmark instances for every seed and size via `generate_benchmarks.sh`, then submits the inference jobs. The seeds, sizes and repetition counts are variables at the top of the file — **edit them before running**, and note that inference costs real money. |
| [submit_experiments.sh](submit_experiments.sh), [run-multiple-models.sh](run-multiple-models.sh), [run-model-multiple-times.sh](run-model-multiple-times.sh) | Job submission for a cluster, and the loops over models and repetitions that `run_all.sh` drives. |
| [generate_the_plots.sh](generate_the_plots.sh) | Regenerates the figures in `aggregated/results-for-paper/` from the aggregated result tables already in this repository. This one needs no inference and no API key. |
| [compute_mean_stddev.py](compute_mean_stddev.py), [pairwise_significance.py](pairwise_significance.py), [test_normality.py](test_normality.py), [generate_aggregated_table.py](generate_aggregated_table.py), [generate_averaged_tables.py](generate_averaged_tables.py) | Aggregation, significance testing and the LaTeX/TSV tables used in the paper. |
| [aggregate_results_for_determining_benchmark_size.py](aggregate_results_for_determining_benchmark_size.py), [determine_benchmark_size.sh](determine_benchmark_size.sh) | The benchmark-size calibration behind the "~300 items suffice" figure. |

If you only want the figures and tables, start with `generate_the_plots.sh` — the per-model
results it consumes are already committed under `results/` and `aggregated/`. Note that inference
against commercial APIs is not bit-reproducible: the models drift, and endpoints ignore the seed
(see the reproducibility note above).

## Project Structure
| Path | Description |
| :--- | :--- |
| `benchmarks/` | Pre-generated and custom benchmark TSV files. |
| `data/` | Where source musical pieces are placed. Mostly empty in a fresh clone — the source material is downloaded on demand by `prepare_data.sh` (see [License](#license)). |
| `src/` | Core logic for ground truth extraction and distractor generation, plus format conversions and plotting. |
| `results/` |  Detailed results for all models, for multiple benchmark sizes and benchmark instances. |
| `aggregated/` | Processed results, significance tests, and the LaTeX/TSV tables for the paper. |
| `aggregated/results-for-paper/` | The visualization and selected results for paper. |
| `logs/` | Inference logs. Only one run is committed (the best-performing model, ~34 MB); everything else is gitignored. |

## Authors

- **Tomáš Sourada** — [ÚFAL CUNI], [Prague, Czech Republic] · [ORCID](https://orcid.org/0009-0003-6792-825X)
- **Katia Vendrame** — [FIT VUT], [Brno, Czech Republic] · [ORCID](https://orcid.org/0009-0009-1659-0459)
- **Jan Hajič, jr.** — [ÚFAL CUNI], [Prague, Czech Republic] · [ORCID](https://orcid.org/0000-0002-9207-567X)

**Corresponding author:** Tomáš Sourada — [sourada@ufal.mff.cuni.cz](mailto:sourada@ufal.mff.cuni.cz)



## Citation

If you use this benchmark or code, please cite our paper:

```bibtex
@misc{sourada2026musicicareabout,
      title={Music I Care About: Automated Multimodal Benchmarking of LLM Music Perception Skills on (Almost) Any Music}, 
      author={Tomáš Sourada and Katia Vendrame and Jan Hajič jr},
      year={2026},
      eprint={2607.06015},
      archivePrefix={arXiv},
      primaryClass={cs.SD},
      url={https://arxiv.org/abs/2607.06015}, 
}
``` 

## License

This repository combines original material by the authors with data derived from third-party datasets, so different parts carry different licenses. Please respect the license that applies to whatever you reuse.

| Component | License | Full text |
| :--- | :--- | :--- |
| Source code (all `.py` / `.sh` scripts) and original, non-derived data/config (`ontology.yaml`, `meta-questions.tsv`, `pieces.tsv`, `selected_cadences.yaml`, `all_pox_cadence_types.yaml`, `eval-config.yaml`, `benchmark-generation-config.yaml`) | **GPL-3.0-or-later** | [LICENSE](LICENSE) / [LICENSE-SOURCE-CODE](LICENSE-SOURCE-CODE) |
| Benchmark data **derived from ChoraleBricks** (e.g. `benchmarks/qs_per_subcat_20/seed_52.tsv`) | **CC BY 4.0** | [LICENSE-DATA-CHORALEBRICKS](LICENSE-DATA-CHORALEBRICKS) |
| Benchmark data **derived from ChoralSynth** (`benchmarks/choralsynth.*.tsv` and the `dataset-choralsynth` branch) | **CC BY-SA 4.0** | [LICENSE-DATA-CHORALSYNTH](LICENSE-DATA-CHORALSYNTH) |
| `src/mmmu_eval_utils.py` (modified copy of one file from the MMMU-Benchmark project) | **Apache 2.0**, redistributed as part of the GPL-covered source per Apache-2.0 §4 | [LICENSE-THIRD-PARTY-MMMU](LICENSE-THIRD-PARTY-MMMU); see file header for attribution and the list of changes |
| `results/`, `aggregated/`, `benchmark-comparisons/`, `logs/` (raw and aggregated model outputs, inference logs) | Not separately licensed — provided as-is for reproducibility | — |

Most source files carry a short header identifying them as GPL-3.0-or-later; `meta-questions.tsv` and `pieces.tsv` are GPL-covered too but don't carry an inline header, since prepending a comment line would break the TSV parsing that reads them — their license is documented here instead.

**Why GPL for code but CC for data:** GPL is designed for software; it doesn't fit non-code creative/data works well, so the two ChoraleBricks/ChoralSynth-derived benchmark data licenses follow the upstream datasets' own terms instead of the code's license.

**Why two data licenses:** ChoraleBricks is licensed CC BY 4.0, so instances derived from it stay CC BY 4.0. ChoralSynth is licensed CC BY-SA 4.0, and the **ShareAlike** term is contagious — any material derived from ChoralSynth, including these benchmark instances, must remain under CC BY-SA 4.0 with attribution to ChoralSynth.

**How derived data is delineated:** benchmark instances built from ChoralSynth are named with a `choralsynth` prefix (and the ChoralSynth source pieces live on the `dataset-choralsynth` branch); all other benchmark instances are built from ChoraleBricks. See [benchmarks/README.md](benchmarks/README.md) for the per-file breakdown. When in doubt, treat any `choralsynth*` file as **CC BY-SA 4.0**.

**Outputs are not separately licensed.** `results/`, `aggregated/`, and `benchmark-comparisons/` contain raw and aggregated model outputs (inference results, evaluation tables, comparison files) generated by running the GPL-licensed scripts over the benchmark data; they're kept in the repository for reproducibility but are not themselves assigned a license. `logs/` (mostly gitignored) is the same.

**Source data is not redistributed here.** The `data/` directory does not ship any source material from these datasets; the original audio/scores are downloaded on demand by the setup scripts (`prepare_data.sh`, `prepare_data_choral_synth.sh`) directly from their original sources. Only *derived* benchmark instances (TSV question files) are stored in this repository.

### Dataset attributions

If you use the derived benchmark data, you must also credit the upstream datasets:

```bibtex
@dataset{narang_2023_10161065,
  author       = {Narang, Jyoti and
                  De la Vega, Viviana and
                  Lizarraga, Xavier and
                  Mayor, Oscar and
                  Parra, Hector and
                  Janer, Jordi and
                  Serra, Xavier},
  title        = {ChoralSynth: Synthetic Dataset of Choral Singing},
  month        = nov,
  year         = 2023,
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.10161065},
  url          = {https://doi.org/10.5281/zenodo.10161065},
}

@dataset{balke_2025_15081741,
  author       = {Balke, Stefan and
                  Berndt, Axel and
                  Mueller, Meinard},
  title        = {ChoraleBricks: A Modular Multitrack Dataset for
                   Wind Music Research
                  },
  month        = mar,
  year         = 2025,
  publisher    = {Zenodo},
  version      = {1.0.0},
  doi          = {10.5281/zenodo.15081741},
  url          = {https://doi.org/10.5281/zenodo.15081741},
}
```

