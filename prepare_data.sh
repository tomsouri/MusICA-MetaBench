#!/bin/bash
# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

# You need to have MuseScore installed and correctly set in the script the path to it in src/musicxml2pdf.py for the
# musicxml to pdf conversion to work. If you don't have MuseScore, the script will still run but will skip the PDF
# conversion step.

# You also need to have ffmpeg installed for the m4a to wav conversion step.

# You also need to have pdftoppm installed for the pdf to png conversion step.

# You also need to have window access to the machine you are running on (e.g., ssh -Y user@host) for the musicxml to pdf conversion step, since MuseScore requires a display.

# TODO: do not use hardcoded symbolic.musicxml etc. paths, get them via utils.py methods


set -euo pipefail

ROOT_DIR="$(pwd)"
DATA_ROOT="$(pwd)/data"
ORIG_ROOT="$DATA_ROOT/original/chorale-bricks"
TARGET_ROOT="$DATA_ROOT/chorale-bricks"
MASTER_MIX_DIR="$ORIG_ROOT/master-mixes"
SHORT_PNG_DIR="$ORIG_ROOT/short-pngs"
ZIP_URL="https://zenodo.org/records/15081741/files/01_AudioAndAnnotations.zip"
ZIP_FILE="$ORIG_ROOT/01_AudioAndAnnotations.zip"
EXTRACT_DIR="$ORIG_ROOT/01_AudioAndAnnotations"
PYTHON="$ROOT_DIR/.venv/bin/python"

# --- Statistics Counters ---
count_m4a2wav_success=0
count_m4a2wav_error=0
count_m4a2wav_skip=0

count_mastermix_download_success=0
count_mastermix_download_error=0
count_mastermix_download_skip=0

count_png_download_success=0
count_png_download_error=0
count_png_download_skip=0

count_xml2pdf_success=0
count_xml2pdf_error=0
count_xml2pdf_skip=0

count_xml2abc_success=0
count_xml2abc_error=0
count_xml2abc_skip=0

count_pdf2png_success=0
count_pdf2png_error=0
count_pdf2png_skip=0

count_audio_copy_success=0
count_audio_copy_error=0
count_audio_copy_skip=0

count_png_copy_success=0
count_png_copy_error=0
count_png_copy_skip=0

count_missing_files=0
# ---------------------------

trap 'echo "Error: command '\''${BASH_COMMAND}'\'' failed at line ${LINENO}" >&2' ERR

log() {
    echo "[prepare] $*"
}

mkdir -p "$MASTER_MIX_DIR"
mkdir -p "$SHORT_PNG_DIR"
mkdir -p "$TARGET_ROOT"

cd "$ORIG_ROOT"
if [[ -d "$EXTRACT_DIR" ]]; then
    log "Archive already extracted at $EXTRACT_DIR; skipping unzip."
else
    if [[ -f "$ZIP_FILE" ]]; then
        log "Zip already downloaded; skipping wget."
    else
        log "Downloading 01_AudioAndAnnotations.zip..."
        wget -nc "$ZIP_URL"
    fi
    log "Unzipping file..."
    unzip -q "$ZIP_FILE"
    log "Extraction complete!"
fi

cd "$MASTER_MIX_DIR"
LIST_FILE="../list-of-master-mix-links.txt"
if [[ -f "$LIST_FILE" ]]; then
    log "Downloading master mixes..."
    while IFS= read -r mix_url; do
        if [[ -z "$mix_url" ]]; then
            continue
        fi

        mix_name="${mix_url##*/}"
        if [[ -z "$mix_name" ]]; then
            echo "Warning: could not derive master mix name from $mix_url" >&2
            count_mastermix_download_error=$((count_mastermix_download_error + 1))
            count_missing_files=$((count_missing_files + 1))
            continue
        fi

        if [[ -f "$mix_name" ]]; then
            log "Master mix already downloaded: $mix_name"
            count_mastermix_download_skip=$((count_mastermix_download_skip + 1))
            continue
        fi

        if wget -O "$mix_name" "$mix_url"; then
            count_mastermix_download_success=$((count_mastermix_download_success + 1))
        else
            echo "Warning: master mix download failed for $mix_url" >&2
            count_mastermix_download_error=$((count_mastermix_download_error + 1))
            count_missing_files=$((count_missing_files + 1))
        fi
    done < "$LIST_FILE"
else
    echo "Warning: master mix list not found at $LIST_FILE" >&2
    count_missing_files=$((count_missing_files + 1))
fi

log "Converting .m4a master mixes to .wav..."
shopt -s nullglob
for file in *.m4a; do
    wav_output="${file%.m4a}.wav"
    if [[ -f "$wav_output" ]]; then
        log "Skipping conversion for $file (already have $wav_output)."
        count_m4a2wav_skip=$((count_m4a2wav_skip + 1))
    else
        log "Converting $file..."
        if ffmpeg -y -i "$file" "$wav_output" -loglevel error; then
            count_m4a2wav_success=$((count_m4a2wav_success + 1))
        else
            echo "Warning: WAV conversion failed for $file" >&2
            count_m4a2wav_error=$((count_m4a2wav_error + 1))
        fi
    fi
done
shopt -u nullglob


cd "$SHORT_PNG_DIR"
PNG_LIST_FILE="../list-of-pngs.txt"
PNG_URL_PREFIX="https://audiolabs-erlangen.de/media/pages/resources/MIR/2025-ChoraleBricks/"
if [[ -f "$PNG_LIST_FILE" ]]; then
    log "Downloading short PNGs..."
    while IFS= read -r png_url; do
        if [[ -z "$png_url" ]]; then
            continue
        fi

        if [[ "$png_url" == "$PNG_URL_PREFIX"* ]]; then
            png_suffix="${png_url#${PNG_URL_PREFIX}}"
            png_name="${png_suffix%%/*}"
        else
            png_name="${png_url##*/}"
        fi

        if [[ -n "$png_name" && "$png_name" != *.png ]]; then
            png_name="${png_name}.png"
        fi

        if [[ -z "$png_name" ]]; then
            echo "Warning: could not derive PNG name from $png_url" >&2
            count_missing_files=$((count_missing_files + 1))
            continue
        fi

        if [[ -f "$png_name" ]]; then
            log "Short PNG already downloaded: $png_name"
            count_png_download_skip=$((count_png_download_skip + 1))
            continue
        fi

        if wget -O "$png_name" "$png_url"; then
            count_png_download_success=$((count_png_download_success + 1))
        else
            echo "Warning: short PNG download failed for $png_url" >&2
            count_png_download_error=$((count_png_download_error + 1))
            count_missing_files=$((count_missing_files + 1))
        fi
    done < "$PNG_LIST_FILE"
else
    echo "Warning: png list not found at $PNG_LIST_FILE" >&2
    count_missing_files=$((count_missing_files + 1))
fi

cd "$EXTRACT_DIR"
for dir in */; do
    subdir_name="${dir%/}"
    tgt_dir="$TARGET_ROOT/$subdir_name"
    log "Preparing $subdir_name..."
    mkdir -p "$tgt_dir"

    # Copy MIDI files (uncomment if needed)
    # src_csv="$dir/$subdir_name.csv"
    # if [[ -f "$src_csv" ]]; then
    #     cp "$src_csv" "$tgt_dir/symbolic.midi.csv"
    # else
    #     echo "Warning: missing $src_csv" >&2
    #     count_missing_files=$((count_missing_files + 1))
    # fi

    # src_mid="$dir/$subdir_name.mid"
    # if [[ -f "$src_mid" ]]; then
    #     cp "$src_mid" "$tgt_dir/symbolic.midi"
    # else
    #     echo "Warning: missing $src_mid" >&2
    #     count_missing_files=$((count_missing_files + 1))
    # fi

    src_musicxml="$dir/$subdir_name.musicxml"
    if [[ -f "$src_musicxml" ]]; then
        cp "$src_musicxml" "$tgt_dir/symbolic.musicxml"

        # TODO: uncomment if needed
        # TODO: after anonymization of mxml, generate also anonymized other
        # "$PYTHON" "$ROOT_DIR/src/conversions/anonymize_musicxml.py" --src "$tgt_dir/symbolic.musicxml" --tgt "$tgt_dir/anonymized.symbolic.musicxml"
        
        # Convert MusicXML to PDF (uncomment if needed, but requires MuseScore and a display)
        # if [[ -f "$tgt_dir/visual.pdf" ]]; then
        #     log "PDF already exists for $subdir_name; skipping musicxml to pdf conversion."
        #     count_xml2pdf_skip=$((count_xml2pdf_skip + 1))
        # else
        #     log "Converting $subdir_name musicxml to pdf..."
        #     if "$PYTHON" "$ROOT_DIR/src/conversions/musicxml2pdf.py" -i "$tgt_dir/symbolic.musicxml" -o "$tgt_dir/visual.pdf"; then
        #         count_xml2pdf_success=$((count_xml2pdf_success + 1))
        #     else
        #         echo "Warning: PDF conversion failed for $subdir_name" >&2
        #         count_xml2pdf_error=$((count_xml2pdf_error + 1))
        #     fi
        # fi
        
        # Convert MusicXML to ABC
        if [[ -f "$tgt_dir/symbolic.abc.txt" ]]; then
            log "ABC already exists for $subdir_name; skipping musicxml to abc conversion."
            count_xml2abc_skip=$((count_xml2abc_skip + 1))
        else
            log "Converting $subdir_name musicxml to abc..."
            if "$PYTHON" "$ROOT_DIR/src/conversions/musicxml2abc.py" "$tgt_dir/symbolic.musicxml" "$tgt_dir/symbolic.abc.txt"; then
                count_xml2abc_success=$((count_xml2abc_success + 1))
            else
                echo "Warning: ABC conversion failed for $subdir_name" >&2
                count_xml2abc_error=$((count_xml2abc_error + 1))
            fi
        fi
        
        # Convert PDF to PNG (uncomment if needed)
        # if [[ -f "$tgt_dir/visual.pdf" ]]; then
        #     if [[ -f "$tgt_dir/visual.png" ]]; then
        #         log "PNG already exists for $subdir_name; skipping pdf to png conversion."
        #         count_pdf2png_skip=$((count_pdf2png_skip + 1))
        #     else
        #         log "Converting $subdir_name pdf to png..."
        #         # Produces a merged png with all pages merged vertically.
        #         # TODO: This may be impractical, maybe it would be better to pass the individual pages as separate png files?

        #         if pdftoppm -png "$tgt_dir/visual.pdf" "$tgt_dir/visual" && \
        #         convert -append "$tgt_dir/visual-"*.png "$tgt_dir/visual-tmp.png"; then
                    
        #             mv "$tgt_dir/visual-tmp.png" "$tgt_dir/visual.png"
        #             # Clean up the individual page files generated by pdftoppm
        #             rm -f "$tgt_dir/visual-"[0-9]*.png
                    
        #             count_pdf2png_success=$((count_pdf2png_success + 1))
        #         else
        #             echo "Warning: PNG conversion failed for $subdir_name" >&2
                    
        #             # Clean up any partial files in case pdftoppm succeeded but convert failed
        #             rm -f "$tgt_dir/visual-"[0-9]*.png
                    
        #             count_pdf2png_error=$((count_pdf2png_error + 1))
        #         fi
        #     fi
        # else
        #     log "PDF not found for $subdir_name; recording as pdf to png error."
        #     count_pdf2png_error=$((count_pdf2png_error + 1))

        #     # We don't increment failure here since PDF creation was the actual point of failure.
        # fi
    else
        echo "Warning: missing $src_musicxml" >&2
        count_missing_files=$((count_missing_files + 1))
    fi


    # Copy the MEI file (uncomment if needed)
    # src_mei="$dir/$subdir_name.mei"
    # if [[ -f "$src_mei" ]]; then
    #     cp "$src_mei" "$tgt_dir/symbolic.mei"
    # else
    #     echo "Warning: missing $src_mei" >&2
    #     count_missing_files=$((count_missing_files + 1))
    # fi

    audio_file=$(find "$MASTER_MIX_DIR" -maxdepth 1 -type f -name "${subdir_name}*.wav" -print -quit || true)
    if [[ -z "$audio_file" ]]; then
        echo "Warning: no master-mix WAV found for $subdir_name" >&2
        count_missing_files=$((count_missing_files + 1))
        count_audio_copy_error=$((count_audio_copy_error + 1))
    elif [[ -f "$tgt_dir/audio.mastermix.wav" ]]; then
        log "Master mix already copied for $subdir_name; skipping."
        count_audio_copy_skip=$((count_audio_copy_skip + 1))
    else
        if cp "$audio_file" "$tgt_dir/audio.mastermix.wav"; then
            count_audio_copy_success=$((count_audio_copy_success + 1))
        else
            echo "Warning: failed to copy master-mix WAV for $subdir_name" >&2
            count_audio_copy_error=$((count_audio_copy_error + 1))
        fi
    fi

    png_file=$(find "$SHORT_PNG_DIR" -maxdepth 1 -type f -name "${subdir_name}*.png" -print -quit || true)
    if [[ -z "$png_file" ]]; then
        echo "Warning: no short PNG found for $subdir_name" >&2
        count_missing_files=$((count_missing_files + 1))
        count_png_copy_error=$((count_png_copy_error + 1))
    elif [[ -f "$tgt_dir/visual.short.png" ]]; then
        log "Short PNG already copied for $subdir_name; skipping."
        count_png_copy_skip=$((count_png_copy_skip + 1))
    else
        if cp "$png_file" "$tgt_dir/visual.short.png"; then
            count_png_copy_success=$((count_png_copy_success + 1))
        else
            echo "Warning: failed to copy short PNG for $subdir_name" >&2
            count_png_copy_error=$((count_png_copy_error + 1))
        fi
    fi
done


# Generate the list of pieces file (pieces-chorale-bricks.tsv)
# (required for the benchmark generation step)
cd $ROOT_DIR
bash generate_pieces_list.sh chorale-bricks
log "List of pieces written to pieces-chorale-bricks.tsv"

log "Data preparation complete."

# Print Statistics
echo ""
echo "=========================================================="
echo "                   CONVERSION STATISTICS                  "
echo "=========================================================="
printf "%-20s | %-10s | %-10s | %-10s\n" "Task" "Successful" "Failed" "Skipped"
echo "----------------------------------------------------------"
printf "%-20s | %-10d | %-10d | %-10d\n" "DL Master Mix"   "$count_mastermix_download_success" "$count_mastermix_download_error" "$count_mastermix_download_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "DL Short PNG"    "$count_png_download_success" "$count_png_download_error" "$count_png_download_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "M4A to WAV"   "$count_m4a2wav_success" "$count_m4a2wav_error" "$count_m4a2wav_skip"
#printf "%-20s | %-10d | %-10d | %-10d\n" "MusicXML to PDF" "$count_xml2pdf_success" "$count_xml2pdf_error" "$count_xml2pdf_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "MusicXML to ABC" "$count_xml2abc_success" "$count_xml2abc_error" "$count_xml2abc_skip"
#printf "%-20s | %-10d | %-10d | %-10d\n" "PDF to PNG"      "$count_pdf2png_success" "$count_pdf2png_error" "$count_pdf2png_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "Copy Audio"    "$count_audio_copy_success" "$count_audio_copy_error" "$count_audio_copy_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "Copy Short PNG" "$count_png_copy_success" "$count_png_copy_error" "$count_png_copy_skip"
echo "=========================================================="
echo "Missing Source Files: $count_missing_files"
echo "=========================================================="
echo ""