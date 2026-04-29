#!/usr/bin/env bash
# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.
set -euo pipefail

# Usage: generate_pieces_list.sh [DATA_DIR]
DATA_DIR="${1:-data}"
OUTPUT_FILE="pieces.tsv"

printf "%s\t%s\t%s\t%s\n" "piece_id" "dataset" "name" "path" > "$OUTPUT_FILE"

if [ ! -d "$DATA_DIR" ]; then
    echo "Error: Directory '$DATA_DIR' does not exist." >&2
    exit 1
fi

# Expand globs to empty lists rather than literal patterns
shopt -s nullglob

for dataset_path in "$DATA_DIR"/*/; do
    [ -d "$dataset_path" ] || continue
    dataset_name=$(basename "$dataset_path")
    echo "Processing dataset: $dataset_name"

    case "$dataset_name" in
        original|white_noise)
            continue
            ;;
    esac

    for piece_path in "$dataset_path"*/; do
        [ -d "$piece_path" ] || continue
        piece_name=$(basename "$piece_path")
        clean_path="$DATA_DIR/$dataset_name/$piece_name"
        printf "%s\t%s\t%s\t%s\n" "$piece_name" "$dataset_name" "$piece_name" "$clean_path" >> "$OUTPUT_FILE"
    done
done

echo "Successfully generated $OUTPUT_FILE"