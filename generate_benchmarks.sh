#!/usr/bin/env bash
# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

# generate_benchmarks.sh
#
# Generates benchmark files (once per size and seed combination)
# and writes a cross-seed comparison for each size.
#
# Usage:
#   ./generate_benchmarks.sh \
#       --sizes 20 25 \
#       --seeds 55 56 57 \
#       [--submodalities "audio.mastermix.wav" "symbolic.abc.txt" "visual.short.png"] \
#       [--allowed_metaq_ids 1 2 3 4 5 6 7 8 9] \
#       [--config benchmark-generation-config-chorale-bricks.yaml]

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
declare -a sizes=()
declare -a seeds=()
declare -a submodalities=("audio.mastermix.wav" "symbolic.abc.txt" "visual.short.png")
declare -a allowed_metaq_ids=(1 2 3 4 5 6 7 8 9 10 11)
config="benchmark-generation-config-chorale-bricks.yaml"
path_to_pregenerated_full_benchmark="benchmarks/pre-generated_full_benchmark.tsv"




# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --sizes)
            shift
            while [[ $# -gt 0 && ! "$1" == --* ]]; do
                sizes+=("$1"); shift
            done
            ;;
        --seeds)
            shift
            while [[ $# -gt 0 && ! "$1" == --* ]]; do
                seeds+=("$1"); shift
            done
            ;;
        --submodalities)
            submodalities=()
            shift
            while [[ $# -gt 0 && ! "$1" == --* ]]; do
                submodalities+=("$1"); shift
            done
            ;;
        --allowed_metaq_ids)
            allowed_metaq_ids=()
            shift
            while [[ $# -gt 0 && ! "$1" == --* ]]; do
                allowed_metaq_ids+=("$1"); shift
            done
            ;;
        --config)
            config="$2"; shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2; exit 1
            ;;
    esac
done

if [[ ${#sizes[@]} -eq 0 || ${#seeds[@]} -eq 0 ]]; then
    echo "Error: --sizes and --seeds are required." >&2
    exit 1
fi


if [ -f "${path_to_pregenerated_full_benchmark}" ]; then
    rm "${path_to_pregenerated_full_benchmark}"
    echo "File ${path_to_pregenerated_full_benchmark} removed."
else
    echo "File ${path_to_pregenerated_full_benchmark} not found."
fi



# ── Generation ───────────────────────────────────────────────────────────────
for size in "${sizes[@]}"; do
    benchmarks=()

    for seed in "${seeds[@]}"; do
        mkdir -p "benchmarks/qs_per_subcat_${size}/"
        benchmark_file="benchmarks/qs_per_subcat_${size}/seed_${seed}.tsv"

        # Skip if the file already exists (idempotent)
        if [[ -f "$benchmark_file" ]]; then
            echo "Benchmark already exists, skipping: $benchmark_file"
            benchmarks+=("$benchmark_file")
            continue
        fi

        echo "Generating benchmark  size=${size}  seed=${seed}"

        .venv/bin/python3 generate_benchmark.py \
            --config "$config" \
            --benchmark_file "$benchmark_file" \
            --questions_per_subcategory_count "$size" \
            --seed "$seed" \
            --submodalities "${submodalities[@]}" \
            --allowed_metaq_ids "${allowed_metaq_ids[@]}" \
            --path_to_pregenerated_full_benchmark_file ${path_to_pregenerated_full_benchmark} \
            --use_pregenerated_benchmark_file

        benchmarks+=("$benchmark_file")
        echo "================================================================================"
    done

    # Cross-seed comparison (only meaningful when there are ≥ 2 seeds)
    if [[ ${#benchmarks[@]} -ge 2 ]]; then
        mkdir -p benchmark-comparisons
        .venv/bin/python3 compare_benchmark_files.py \
            --list_of_tsvs "${benchmarks[@]}" \
            | tee "benchmark-comparisons/${size}qs_${#benchmarks[@]}_benchmarks.txt"
        echo "Comparison written to benchmark-comparisons/${size}qs_${#benchmarks[@]}_benchmarks.txt"
    fi

    echo "================================================================================"
    echo "================================================================================"
done