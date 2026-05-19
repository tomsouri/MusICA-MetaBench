#!/bin/bash

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
ORIG_ROOT="$DATA_ROOT/original/choral-synth"
TARGET_ROOT="$DATA_ROOT/choral-synth"
MASTER_MIX_DIR="$ORIG_ROOT/master-mixes"
ZIP_URL="https://zenodo.org/records/10137883/files/Dataset.zip"
ZIP_FILE="$ORIG_ROOT/Dataset.zip"
EXTRACT_DIR="$ORIG_ROOT/Dataset"
PYTHON="$ROOT_DIR/.venv/bin/python"

# --- Statistics Counters ---
count_m4a2wav_success=0
count_m4a2wav_error=0
count_m4a2wav_skip=0

count_xml2pdf_success=0
count_xml2pdf_error=0
count_xml2pdf_skip=0

count_xml2abc_success=0
count_xml2abc_error=0
count_xml2abc_skip=0

count_pdf2png_success=0
count_pdf2png_error=0
count_pdf2png_skip=0

count_merge_voices_success=0
count_merge_voices_error=0
count_merge_voices_skip=0

count_missing_files=0
# ---------------------------

trap 'echo "Error: command '\''${BASH_COMMAND}'\'' failed at line ${LINENO}" >&2' ERR

log() {
    echo "[prepare] $*"
}

mkdir -p "$MASTER_MIX_DIR"
mkdir -p "$TARGET_ROOT"

cd "$ORIG_ROOT"
if [[ -d "$EXTRACT_DIR" ]]; then
    log "Archive already extracted at $EXTRACT_DIR; skipping unzip."
else
    if [[ -f "$ZIP_FILE" ]]; then
        log "Zip already downloaded; skipping wget."
    else
        log "Dataset.zip..."
        wget -nc "$ZIP_URL"
    fi
    log "Unzipping file..."
    unzip -q "$ZIP_FILE"
    log "Extraction complete!"
fi

# cd "$MASTER_MIX_DIR"
# LIST_FILE="../list-of-master-mix-links.txt"
# if [[ -f "$LIST_FILE" ]]; then
#     log "Downloading master mixes..."
#     wget -nc -i "$LIST_FILE"
# else
#     echo "Warning: master mix list not found at $LIST_FILE" >&2
#     count_missing_files=$((count_missing_files + 1))
# fi

# log "Converting .m4a master mixes to .wav..."
# shopt -s nullglob
# for file in *.m4a; do
#     wav_output="${file%.m4a}.wav"
#     if [[ -f "$wav_output" ]]; then
#         log "Skipping conversion for $file (already have $wav_output)."
#         count_m4a2wav_skip=$((count_m4a2wav_skip + 1))
#     else
#         log "Converting $file..."
#         if ffmpeg -y -i "$file" "$wav_output" -loglevel error; then
#             count_m4a2wav_success=$((count_m4a2wav_success + 1))
#         else
#             echo "Warning: WAV conversion failed for $file" >&2
#             count_m4a2wav_error=$((count_m4a2wav_error + 1))
#         fi
#     fi
# done
shopt -u nullglob

cd "$EXTRACT_DIR"
#find . -name "score.musicxml" -exec sh -c 'mkdir -p "$TARGET_ROOT/$(basename $(dirname "$1"))/" &&cp "$1" "$TARGET_ROOT/$(basename $(dirname "$1"))/symbolic.musicxml"' _ {} \;

for dir in */; do
    subdir_name="${dir%/}"
    tgt_dir="$TARGET_ROOT/$subdir_name"
    log "Preparing $subdir_name..."
    mkdir -p "$tgt_dir"

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

    src_musicxml="$dir/score.musicxml"
    if [[ -f "$src_musicxml" ]]; then
        cp "$src_musicxml" "$tgt_dir/symbolic.musicxml"

        # TODO: after anonymization of mxml, generate also anonymized other
        # "$PYTHON" "$ROOT_DIR/src/conversions/anonymize_musicxml.py" --src "$tgt_dir/symbolic.musicxml" --tgt "$tgt_dir/anonymized.symbolic.musicxml"
        
        # Convert MusicXML to PDF
        if [[ -f "$tgt_dir/visual.pdf" ]]; then
            log "PDF already exists for $subdir_name; skipping musicxml to pdf conversion."
            count_xml2pdf_skip=$((count_xml2pdf_skip + 1))
        else
            log "Converting $subdir_name musicxml to pdf..."
            if "$PYTHON" "$ROOT_DIR/src/conversions/musicxml2pdf.py" -i "$tgt_dir/symbolic.musicxml" -o "$tgt_dir/visual.pdf"; then
                count_xml2pdf_success=$((count_xml2pdf_success + 1))
            else
                echo "Warning: PDF conversion failed for $subdir_name" >&2
                count_xml2pdf_error=$((count_xml2pdf_error + 1))
            fi
        fi
        
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
        
        # Convert PDF to PNG
        if [[ -f "$tgt_dir/visual.pdf" ]]; then
            if [[ -f "$tgt_dir/visual.png" ]]; then
                log "PNG already exists for $subdir_name; skipping pdf to png conversion."
                count_pdf2png_skip=$((count_pdf2png_skip + 1))
            else
                log "Converting $subdir_name pdf to png..."
                # Produces a merged png with all pages merged vertically.
                # TODO: This may be impractical, maybe it would be better to pass the individual pages as separate png files?

                # We use a local policy.xml to override ImageMagick limits for large music scores
                cat <<EOF > "$tgt_dir/policy.xml"
<policymap>
  <policy domain="resource" name="width" value="128MP"/>
  <policy domain="resource" name="height" value="128MP"/>
  <policy domain="resource" name="area" value="8GP"/>
  <policy domain="resource" name="memory" value="4GiB"/>
  <policy domain="resource" name="map" value="8GiB"/>
  <policy domain="resource" name="disk" value="16GiB"/>
</policymap>
EOF

                if pdftoppm -png "$tgt_dir/visual.pdf" "$tgt_dir/visual" && \
                MAGICK_CONFIGURE_PATH="$tgt_dir" convert -append "$tgt_dir/visual-"*.png "$tgt_dir/visual-tmp.png"; then
                    
                    mv "$tgt_dir/visual-tmp.png" "$tgt_dir/visual.png"
                    # Clean up the individual page files generated by pdftoppm and the temporary policy
                    rm -f "$tgt_dir/visual-"[0-9]*.png "$tgt_dir/policy.xml"
                    
                    count_pdf2png_success=$((count_pdf2png_success + 1))
                else
                    echo "Warning: PNG conversion failed for $subdir_name" >&2
                    
                    # Clean up any partial files in case pdftoppm succeeded but convert failed
                    rm -f "$tgt_dir/visual-"[0-9]*.png "$tgt_dir/policy.xml"
                    
                    count_pdf2png_error=$((count_pdf2png_error + 1))
                fi
            fi
        else
            log "PDF not found for $subdir_name; recording as pdf to png error."
            count_pdf2png_error=$((count_pdf2png_error + 1))

            # We don't increment failure here since PDF creation was the actual point of failure.
        fi
    else
        echo "Warning: missing $src_musicxml" >&2
        count_missing_files=$((count_missing_files + 1))
    fi

    # src_mei="$dir/$subdir_name.mei"
    # if [[ -f "$src_mei" ]]; then
    #     cp "$src_mei" "$tgt_dir/symbolic.mei"
    # else
    #     echo "Warning: missing $src_mei" >&2
    #     count_missing_files=$((count_missing_files + 1))
    # fi
    if [[ -f "$tgt_dir/audio.mastermix.wav" ]]; then
        log "Master mix already exists for $subdir_name; skipping audio preparation."
        count_merge_voices_skip=$((count_merge_voices_skip + 1))
    else
        # Check if voices directory exists
        if [ -d "$dir/voices" ]; then
            # Get a list of all mp3 files in the voices folder
            files=("$dir"/voices/*.mp3)
            
            # Count how many files were found
            count=${#files[@]}
            
            if [ "$count" -gt 0 ]; then
                echo "Found $count MP3 files, combining..."
                # Build the FFmpeg command dynamically
                # -i input1 -i input2 ... -filter_complex amix=inputs=N:duration=longest
                input_args=()
                for f in "${files[@]}"; do
                    input_args+=("-i" "$f")
                done
                
                if ffmpeg "${input_args[@]}" -filter_complex "amix=inputs=$count:duration=longest" "$tgt_dir/audio.mastermix.wav" -y -loglevel error; then
                    echo "Created $tgt_dir/audio.mastermix.wav"
                    count_merge_voices_success=$((count_merge_voices_success + 1))
                else
                    echo "Warning: merging voices failed for $subdir_name" >&2
                    count_merge_voices_error=$((count_merge_voices_error + 1))
                fi
            else
                echo "No MP3s found in $dir/voices"
                count_merge_voices_error=$((count_merge_voices_error + 1))
            fi
        else
            echo "No voices directory in $dir"
            count_merge_voices_error=$((count_merge_voices_error + 1))
        fi
    fi
    # audio_file=$(find "$MASTER_MIX_DIR" -maxdepth 1 -type f -name "${subdir_name}*.wav" -print -quit || true)
    # if [[ -z "$audio_file" ]]; then
    #     echo "Warning: no master-mix WAV found for $subdir_name" >&2
    #     count_missing_files=$((count_missing_files + 1))
    # elif [[ -f "$tgt_dir/audio.mastermix.wav" ]]; then
    #     log "Master mix already copied for $subdir_name; skipping."
    # else
    #     cp "$audio_file" "$tgt_dir/audio.mastermix.wav"
    # fi
done


# Generate the list of pieces file (pieces.tsv)
# (required for the benchmark generation step)
cd $ROOT_DIR
bash generate_pieces_list.sh
log "List of pieces written to pieces.tsv"

log "Data preparation complete."

# Print Statistics
echo ""
echo "=========================================================="
echo "                   CONVERSION STATISTICS                  "
echo "=========================================================="
printf "%-20s | %-10s | %-10s | %-10s\n" "Task" "Successful" "Failed" "Skipped"
echo "----------------------------------------------------------"
# printf "%-20s | %-10d | %-10d | %-10d\n" "M4A to WAV"   "$count_m4a2wav_success" "$count_m4a2wav_error" "$count_m4a2wav_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "MusicXML to PDF" "$count_xml2pdf_success" "$count_xml2pdf_error" "$count_xml2pdf_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "MusicXML to ABC" "$count_xml2abc_success" "$count_xml2abc_error" "$count_xml2abc_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "PDF to PNG"      "$count_pdf2png_success" "$count_pdf2png_error" "$count_pdf2png_skip"
printf "%-20s | %-10d | %-10d | %-10d\n" "Merge Voices"    "$count_merge_voices_success" "$count_merge_voices_error" "$count_merge_voices_skip"
echo "=========================================================="
echo "Missing Source Files: $count_missing_files"
echo "=========================================================="
echo ""