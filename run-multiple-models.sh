#!/bin/bash
# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

#SBATCH -J runAg      # name of job
#SBATCH -p cpu-ms       # name of partition or queue (default=cpu-troja)
#SBATCH -o runAg.out  # name of output file for this submission script
#SBATCH -e runAg.err  # name of error file for this submission script


# to submit the job, you need to be ssh-ed at one of the lrc or sol machines. (from geri/freki/blackbird, ssh lrc1 or sol1)
# Then use: sbatch --dependency=afterany:<JOB_ID>
# sbatch -p cpu-ms -c2 --mem=4G --dependency=afterany:6358156 run_multiple.sh

# - "google/gemini-3.1-pro-preview"
# - "google/gemini-3.1-flash-lite-preview"
# - "llama-4-scout-17b-16e-instruct"
# - "openai/gpt-4o-audio-preview"
# - "openai/gpt-4o-mini"
# - "google/gemini-2.5-flash"
# - "google/gemini-2.0-flash-lite-001"


# TODO: aggregate models need to be run with --disable_zdr in run_benchmark.py
models=(
    "aggregate-mistral"
    "aggregate-gpt-4o"
    "xiaomi/mimo-v2-omni"
    "aggregate-gpt-5"
    # "google/gemini-2.0-flash-lite-001"
    # "google/gemini-2.5-flash-lite"
    # "google/gemini-2.5-pro"
    # "google/gemini-2.5-flash"
    # "google/gemini-3.1-flash-lite-preview"
    # "google/gemini-3.1-pro-preview"
)

# omni models:
#   +   xiaomi/mimo-v2-omni
#   -   google/gemini-3.1-pro-preview
#   -   google/gemini-3-flash-preview
#   +   google/gemini-2.5-pro
#   -   google/gemini-3.1-flash-lite-preview
#   +   google/gemini-2.5-flash-lite
#   +   google/gemini-2.0-flash-lite-001 (going away June 1, 2026)
# aggregate models:
# gpt-5 (less costly):
#   +   openai/gpt-audio-mini
#   +   openai/gpt-5-image-mini
# gpt-4o (costly):
#   -   openai/gpt-4o-audio-preview
#   -   openai/gpt-4o
# mistral (costly)
#   +   mistralai/voxtral-small-24b-2507
#   +   mistralai/mistral-small-3.2-24b-instruct


qpersubcategory=5
seeds=({42..42})
# seeds=({43..43})


benchmarks=() # Initialize an empty array

for seed in "${seeds[@]}"; do
    benchmark_file="benchmark_count_${qpersubcategory}_${seed}.tsv"
    benchmarks+=("$benchmark_file")

    # echo "Generating a benchmark with random seed: $seed"

    # run .venv/bin/python3 generate_benchmark.py --config benchmark-generation-config-chorale-bricks.yaml \
    #     --benchmark_file "$benchmark_file" \
    #     --questions_per_subcategory_count "$qpersubcategory" \
    #     --seed "$seed" \
    #     --submodalities "audio.mastermix.wav" "symbolic.musicxml" "visual.short.png" \
    #     --allowed_metaq_ids 0 1 2 3 4 5 6 7 8 9

    # echo "================================================================================"
done




# .venv/bin/python3 compare_benchmark_files.py --list_of_tsvs "${benchmarks[@]}" | tee "benchmark_comparison_${qpersubcategory}qs.txt"


for model in "${models[@]}"; do
    echo "Running the benchmarks for model ${model}..."

    # 1. Replace all forward slashes / with underscores
    safe_model="${model//\//_}"

    # 2. Replace spaces with underscores
    safe_model="${safe_model// /_}"


    resfiles=()
    textonlyresfiles=()


    for seed in "${seeds[@]}"; do
        benchmark_file="benchmark_count_${qpersubcategory}_${seed}.tsv"

        echo "Running on a benchmark with random seed: $seed"

        mkdir -p "results/${safe_model}/${qpersubcategory}/normal/"
        
        resfile="results/${safe_model}/${qpersubcategory}/normal/rs${seed}.res.tsv"
        resfiles+=("$resfile")
    

        run .venv/bin/python3 run_benchmark.py --config eval-config.yaml \
            --models "${model}" \
            --url "https://openrouter.ai/api/v1/chat/completions" \
            --api-key-env "OPENROUTER_API_KEY" \
            --benchmark_file "$benchmark_file" \
            --modalities "audio" "symbolic" "visual" \
            --run_id "AGGR-${qpersubcategory}-${safe_model}-${seed}"  \
            --max_waiting_time_per_request 300 \
            --verbose \
            --evaluation_output_file "${resfile}" \
            --generate_new_list_with_logs \
            --disable_zdr
        echo "================================================================================"

        mkdir -p "results/${safe_model}/${qpersubcategory}/to/"
        toresfile="results/${safe_model}/${qpersubcategory}/to/rs${seed}.res.tsv"
        textonlyresfiles+=("$toresfile")

        run .venv/bin/python3 run_benchmark.py --config eval-config.yaml \
            --models "${model}" \
            --url "https://openrouter.ai/api/v1/chat/completions" \
            --api-key-env "OPENROUTER_API_KEY" \
            --benchmark_file "$benchmark_file" \
            --modalities "audio" "symbolic" "visual" \
            --run_id "TO-AGGR-${qpersubcategory}-${safe_model}-${seed}"  \
            --max_waiting_time_per_request 300 \
            --text_only_baseline \
            --verbose \
            --evaluation_output_file "${toresfile}" \
            --generate_new_list_with_logs \
            --disable_zdr

        echo "================================================================================"
    done

    # dir="averaged/${safe_model}/${qpersubcategory}"
    # mkdir -p $dir

    # tabname="${safe_model}.${qpersubcategory}"

    # .venv/bin/python3 compute_mean_stddev.py --list_of_tsvs "${resfiles[@]}" --output_file "${dir}/res.tsv" --gsheet_tab_name "${tabname}"
    # .venv/bin/python3 compute_mean_stddev.py --list_of_tsvs "${textonlyresfiles[@]}" --output_file "${dir}/textonly.tsv" --gsheet_tab_name "${tabname}.to"

    # cp "benchmark_comparison_${qpersubcategory}qs.txt" $dir/

done



