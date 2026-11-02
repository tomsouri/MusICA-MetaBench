# Regenerating the plots

How to add newly evaluated models to the plots and tables, and how to render them for print.
Run all commands from the repository root.

[generate_the_plots.sh](generate_the_plots.sh) holds the commands behind the paper figures. It writes
into `aggregated/results-for-paper/`, so running it replaces the paper figures. (The figures as
published stay available on the `provenance-reported-results` branch.) The commands below write to
`aggregated/results-for-poster/` instead.

The data flow is:

```text
logs/run_*/results.tsv                            one run
  -> results/<model>/<size>/<setup>/*.res.tsv     all runs, by model
  -> aggregated/models_comparison/...             one table, one column per model
  -> plots
```

## 1. Add the new results

`run-model.sh` and `run-model-multiple-times.sh` do this step and the next one for you. If you called
`run_benchmark.py` directly, copy the results by hand. Each finished run has its own
`logs/run_<date>_<uuid>/results.tsv`. Do not use `evaluation_summary.tsv`: all runs write to that one
file, so it only holds the run that finished last.

```bash
copy_result () {  # usage: copy_result logs/run_<date>_<uuid>
    model=$(tail -n 1 "$1/results.tsv" | cut -f1)
    safe_model=${model//\//_}
    mkdir -p "results/$safe_model/20/normal"
    cp "$1/results.tsv" "results/$safe_model/20/normal/jobid_local.rs52.rep1.res.tsv"
}
```

Call it once per run. The destination assumes the normal setup on `benchmarks/qs_per_subcat_20/seed_52.tsv`,
that is, size 20 and seed 52.

## 2. Rebuild the comparison tables

```bash
.venv/bin/python3 generate_aggregated_table.py --size 20 --seed 52 --path results/
```

This rewrites `aggregated/models_comparison/size_20/seed_52/`, with one new column per model.
`Warning: Missing ...` lines are normal, they mean a model was not run in that setup. A
`partial run` warning means a model was run on only some modalities, and its other rows stay empty.

## 3. Render the plots

```bash
POSTER=aggregated/results-for-poster
TABLES=aggregated/models_comparison/size_20/seed_52
mkdir -p $POSTER
```

### Bars by modality

This is `submodality-chorale-bricks_s20_seed52_selected-models_grouped_by_modalities.png`.

```bash
.venv/bin/python3 src/plotting/generate_bar_chart.py $TABLES/normal/accuracy_only.tsv \
      --criterion_type submodality \
      --baseline \
      --font_size 15 \
      --exclude aggregate-gpt-5-full \
      --round \
      --sort_per_group \
      --show_names_below \
      --height 3 \
      --tight_crop \
      --width 18 \
      --extended_palette \
      --output_file $POSTER/bars_by_modality.pdf
```

The three options that differ from the paper version:

- `--output_file` with a `.pdf` or `.svg` extension gives vector output, which stays sharp at any print
  size. Prefer this for a poster.
- `--width 18` makes room for 11 models. The default of 14 fits 8.
- `--extended_palette` adds 3 colors. Without it, colors repeat from the 9th model on.

If the poster tool needs a PNG, use a `.png` output file and add `--dpi 600`. At `--width 18` that gives
about 8800 px across, which prints at 300 dpi up to about 75 cm wide. Text scales with the print: 15 pt
in an 18-inch figure comes out at about 30 pt on a 75 cm print.

A model without results for a modality is left out of that group, so the group has fewer bars.

### Bars by model

Same data, one group of three bars per model. A model without audio has a gap in the audio position.

```bash
.venv/bin/python3 src/plotting/generate_bar_chart.py $TABLES/normal/accuracy_only.tsv \
      --criterion_type submodality \
      --group_by_models \
      --baseline \
      --font_size 15 \
      --exclude aggregate-gpt-5-full \
      --round \
      --height 3 \
      --width 18 \
      --output_file $POSTER/bars_by_model.pdf
```

### Spider chart by subcategory

`--criterion_type` also accepts `submodality`, `category` and the other criteria in the table. Pass the
models to leave out to `--exclude`, or the ones to keep to `--include`.

Leave out models without audio (see [Limitations](#limitations)), as in this example:

```bash
.venv/bin/python3 src/plotting/generate_spider_chart.py $TABLES/normal/accuracy_only.tsv \
      --criterion_type subcategory \
      --exclude aggregate-gpt-5-full openai_gpt-6-astra anthropic_claude-opus-5.5 \
      --baseline \
      --font_size 15 \
      --compact \
      --extended_palette \
      --output_file $POSTER/spider_by_subcategory.pdf
```

### Normal vs no-input vs noise-input

Writes one PNG per panel: overall and each modality, named `<prefix>_OVERALL.png` and so on. This script
always writes PNG, so set the resolution with `--dpi`.

```bash
.venv/bin/python3 src/plotting/generate_plot_with_comparison_of_normal_textonly_noise.py \
      $TABLES/comparison_normal_vs_textonly.tsv \
      --output-prefix $POSTER/normal-vs-textonly-vs-noise \
      --y-max 70 \
      --no-hatch \
      --font-size 15 \
      --height 7 \
      --dpi 600
```

Models that lack a setup go to the "Partial setups" part on the right. For the aggregate over seeds, use
`aggregated/models_comparison/size_20/mean_over_seeds/comparison_normal_vs_textonly.tsv` with
`--ignore-incomplete --print-only-average --y-max 51 --height 2.5`.

### Comparison table

Accuracy, time and price per model, as TSV and LaTeX. It reads `results/` directly. `--criterion` selects
the row to report, here the symbolic modality, which every new model was run on.

```bash
.venv/bin/python3 src/plotting/generate_comparison_table.py \
      --base_path results --size 20 --seed 52 \
      --criterion submodality symbolic.abc.txt \
      --output $POSTER/comparison_symbolic.tsv \
      --tex_output $POSTER/comparison_symbolic.tex \
      --exclude_errors
```

With `--omit_setup`, as in `generate_the_plots.sh`, the rows of all setups stay in the table but
without a label, so a model can appear more than once.

### Standard deviation vs benchmark size

This plot only uses multi-seed runs from `aggregated/comparison_between_seeds/`. The first command writes
its input into `tables/`. Without Google Sheets credentials it prints `Error copying data to ...` lines,
which you can ignore: the tables are still generated.

```bash
.venv/bin/python3 generate_averaged_tables.py --only-print-stddev --input_dir aggregated/comparison_between_seeds/
.venv/bin/python3 src/plotting/plot_stddev_with_benchmark_size.py tables/normal/stddev-only/table_ALL.tsv \
      --output $POSTER/stddevs.pdf \
      --log-x \
      --exclude-size-one \
      --multiply-sizes-by 15 \
      --fontsize 20 \
      --height 4 \
      --legend-fontsize 15
```

## Adding another model

Plots shorten unknown model names to 12 characters, for example `anthropic_cl...`. To get a readable label,
add the model to the mapping in `shorten_model_name()` or `shorten_name()` in each script under
`src/plotting/`.

## Limitations

- **Overall numbers of models without audio are not comparable.** They cover 200 items instead of 300,
  and audio is the hardest modality, so overall and subcategory accuracy look better than they would
  over all three modalities. Compare these models per modality only. Keep them out of spider charts:
  subcategory scores have the same bias, and a missing modality draws a broken polygon. Overall panels
  of the noise plot and of the comparison table show them too, so filter or footnote those.
- **Multi-seed plots will not show single-seed models.** `mean_over_seeds` and the standard deviation
  plot read `aggregated/comparison_between_seeds/`, which needs runs over several seeds, as done by
  `run-model-multiple-times.sh`.
- **Run settings can differ between models.** `run-model.sh` passes a 30 s request timeout, while
  `eval-config.yaml` may set a longer one for direct `run_benchmark.py` calls, so model error rates may
  not match. Compare `Model_Error_Percent` in `all_fields.tsv` before reading much into small gaps.
- **Interrupted runs have no `results.tsv`.** `eval.py` cannot rescore them as is: it looks for
  `benchmark_logs.tsv`, but runs write `logs.tsv`.
