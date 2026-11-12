#!/usr/bin/env python3
# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Generate comparison plots from a results TSV file.
Produces 4 plots: OVERALL, and one per submodality (audio, symbolic, visual).
"""

import argparse
import csv
import sys
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

plt.style.use('tableau-colorblind10') 

plt.style.use('petroff10')


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate accuracy comparison plots from a results TSV file."
    )
    parser.add_argument("input_tsv", help="Path to the input TSV file.")
    parser.add_argument(
        "--output-prefix",
        default="plot",
        help="Prefix for output PNG files (default: 'plot').",
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="DPI for output images (default: 300)."
    )
    parser.add_argument(
        "--ignore-incomplete",
        action="store_true",
        help="Ignore models with incomplete setups (not all 3 setups present) in both plots and aggregates.",
    )
    parser.add_argument(
        "--print-only-average",
        action="store_true",
        help="Only plot the aggregate bars, omitting individual models. Labels are placed under each bar.",
    )
    parser.add_argument(
        "--y-max",
        type=float,
        default=105.0,
        help="Maximum value for the y-axis (accuracy %) (default: 105.0).",
    )
    parser.add_argument(
        "--no-hatch",
        action="store_true",
        help="Disable hatch patterns (useful if only color-blind friendly colors are desired).",
    )
    parser.add_argument(
        "--font-size", type=float, default=10.0, help="Base font size for the plot (default: 10.0)."
    )
    parser.add_argument(
        "--height", type=float, default=7.0, help="Height of the output plot in inches (default: 7.0)."
    )
    return parser.parse_args()


def shorten_name(name):
    # Mapping for common model names to shorter versions
    mapping = {
        'google_gemini-3.1-flash-lite-preview': 'Gemini 3.1 FL',
        'google_gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
        'google_gemini-2.0-flash-lite-001': 'Gemini 2.0 FL',
        'google_gemini-2.5-flash-lite': 'Gemini 2.5 FL',
        'Qwen_Qwen3-Omni-30B-A3B-Thinking': 'Qwen3 Omni 30B',
        'aggregate-gpt-4o': 'GPT-4o',
        'aggregate-gpt-5': 'GPT-5',
        'aggregate-mistral': 'Mistral',
        'aggregate-gpt-5-full': 'GPT-5 Full',
        'google_gemini-4-argon': 'Gemini 4 Argon',
        'openai_gpt-6-astra': 'GPT-6 Astra',
        'anthropic_claude-opus-5.5': 'Claude Opus 5.5'
    }
    if name in mapping:
        return mapping[name]

    # Generic shortening
    name = name.replace('google_', '').replace('aggregate-', '')
    if len(name) > 15:
        return name[:12] + '...'
    return name

def load_data(tsv_path):
    """Load the TSV and return header + all rows as list of dicts."""
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)
        columns = reader.fieldnames
    return columns, rows


def extract_model_setups(columns):
    """
    From column names, extract (model_base, setup) pairs.
    The setup is the last token after the final '_' and must be one of
    {normal, text-only, white-noise}.  Everything before that is the model base name.
    """
    setups_of_interest = {"normal", "text-only", "white-noise"}
    # columns that are not metadata
    meta_cols = {"Criterion_Type", "Criterion_Value", "Total_Items"}

    model_map = {}  # column_name -> (model_base, setup)
    models = defaultdict(dict)  # model_base -> {setup: column_name}

    for col in columns:
        if col in meta_cols:
            continue
        # Find setup suffix
        for setup in setups_of_interest:
            if col.endswith("_" + setup):
                base = col[: -(len(setup) + 1)]
                model_map[col] = (base, setup)
                models[base][setup] = col
                break

    return models, model_map


def get_row_value(row, col):
    """Safely get a float value from a row, returning None if missing."""
    val = row.get(col)
    if val is None or val == "":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def make_plot(
    title,
    accuracy_dict,
    models,
    output_path,
    dpi=300,
    ignore_incomplete=False,
    print_only_average=False,
    y_max=105.0,
    no_hatch=False,
    base_font_size=10.0,
    height=7.0,
):
    """
    accuracy_dict: {column_name: float} for the row we care about
    models: {model_base: {setup: column_name}}

    Steps:
      1. Separate models into "complete" (all 3 setups) and "incomplete".
      2. Build aggregate bars (average over all models that have a given setup).
      3. Order: aggregate group | complete models | incomplete models (right).
    """
    SETUPS = ["normal", "text-only", "white-noise"]
    # Color-blind friendly palette (Okabe-Ito inspired)
    COLORS = {
        "normal": "#E69F00",       # orange
        "text-only": "#56B4E9",    # sky blue
        "white-noise": "#009E73",  # bluish green
    }
    LABELS = {
        "normal": "Normal",
        "text-only": "no-input",
        "white-noise": "noise-input",
    }
    # Hatch patterns for B&W readability
    HATCHES = {
        "normal": "",           # Solid
        "text-only": "///",     # diagonal stripes
        "white-noise": "...",   # dots
    }
    if no_hatch:
        HATCHES = {s: "" for s in SETUPS}

    # Set base font size using rcParams or locally
    plt.rcParams.update({'font.size': base_font_size})

    # ---- Classify models ----
    complete_models = {}
    incomplete_models = {}
    models_to_use_for_agg = {}

    for base, setup_map in models.items():
        # Check which setups actually have data in this row
        available = {
            s for s in SETUPS if s in setup_map and get_row_value(accuracy_dict, setup_map[s]) is not None
        }
        if available == set(SETUPS):
            complete_models[base] = setup_map
            models_to_use_for_agg[base] = setup_map
        elif len(available) > 0:
            if not ignore_incomplete:
                incomplete_models[base] = setup_map
                models_to_use_for_agg[base] = setup_map

    # Sort by normal accuracy descending (complete), then alphabetically (incomplete)
    def sort_key_complete(item):
        base, sm = item
        val = get_row_value(accuracy_dict, sm.get("normal", ""))
        return -(val if val is not None else 0)

    def sort_key_incomplete(item):
        base, sm = item
        # Sort by the maximum available accuracy descending
        vals = [
            get_row_value(accuracy_dict, sm[s])
            for s in SETUPS
            if s in sm and get_row_value(accuracy_dict, sm[s]) is not None
        ]
        return -(max(vals) if vals else 0)

    complete_sorted = sorted(complete_models.items(), key=sort_key_complete)
    incomplete_sorted = sorted(incomplete_models.items(), key=sort_key_incomplete)

    # ---- Compute aggregates ----
    agg = {}
    for setup in SETUPS:
        vals = []
        for base, sm in models_to_use_for_agg.items():
            if setup in sm:
                v = get_row_value(accuracy_dict, sm[setup])
                if v is not None:
                    vals.append(v)
        agg[setup] = np.mean(vals) if vals else None

    # ---- Build bar groups ----
    # Each group: (label, {setup: value})
    groups = []

    agg_label = "Aggregate\n(all models)" if not ignore_incomplete else "Aggregate\n(complete only)"
    if print_only_average:
        agg_label = ""  # Shorter label if it's the only thing plotted
    groups.append((agg_label, agg))

    if not print_only_average:
        # 2) Complete models
        for base, sm in complete_sorted:
            vals = {s: get_row_value(accuracy_dict, sm[s]) for s in SETUPS}
            label = shorten_name(base)
            groups.append((label, vals))

        # 3) Incomplete models
        for base, sm in incomplete_sorted:
            vals = {}
            for s in SETUPS:
                if s in sm:
                    vals[s] = get_row_value(accuracy_dict, sm[s])
            label = shorten_name(base)
            groups.append((label, vals))

    n_complete = len(complete_sorted) if not print_only_average else 0
    n_incomplete = len(incomplete_sorted) if not print_only_average else 0

    if ignore_incomplete and print_only_average:
        print("Using the following models to compute the aggregate (complete setups only):")
        for base, sm in complete_models.items():
            print(f"  - {shorten_name(base)}")

    # ---- Plotting ----
    n_groups = len(groups)
    bar_width = 0.25
    group_width = bar_width * len(SETUPS) + 0.02  # small internal padding

    fig, ax = plt.subplots(figsize=(max(6 if print_only_average else 14, n_groups * 1.2), height))

    # X positions for group centers
    x_positions = []
    current_x = 0
    for i in range(n_groups):
        x_positions.append(current_x)
        # Add extra gap after aggregate and before incomplete section
        if i == 0:
            current_x += group_width + (0.45 if not print_only_average else 0)  # gap after aggregate
        elif i == n_complete:  # after last complete, before incomplete
            current_x += group_width + 0.45
        else:
            current_x += group_width + 0.15

    # Draw bars
    all_x = []
    all_tick_labels = []
    for i, (label, vals) in enumerate(groups):
        cx = x_positions[i]
        for j, setup in enumerate(SETUPS):
            bx = cx + (j - 1) * bar_width
            v = vals.get(setup)
            if v is not None:
                bar = ax.bar(
                    bx,
                    v,
                    width=bar_width * 0.9,
                    color=COLORS[setup],
                    hatch=HATCHES[setup],
                    edgecolor="black",
                    linewidth=0.5,
                )
                if print_only_average:
                    all_x.append(bx)
                    all_tick_labels.append(LABELS[setup])
                # Value label on top
                v_fontsize = base_font_size * 0.75
                ax.text(
                    bx,
                    v + 0.8,
                    f"{v:.1f}",
                    ha="center",
                    va="bottom",
                    fontsize=v_fontsize,
                    rotation=0,
                )

    # X-axis labels
    if print_only_average:
        ax.set_xticks(all_x)
        ax.set_xticklabels(all_tick_labels, rotation=0, fontsize=base_font_size)
        # Add the aggregate title above the ticks if only average
        ax.text(x_positions[0], -1.2 * base_font_size, agg_label, ha="center", va="top", fontsize=base_font_size * 1.1, fontweight="bold")
    else:
        ax.set_xticks(x_positions)
        ax.set_xticklabels(
            [g[0] for g in groups], rotation=35, ha="right", fontsize=base_font_size * 0.8
        )

    # Separator lines
    if n_complete > 0:
        sep_x = (x_positions[0] + x_positions[1]) / 2
        ax.axvline(sep_x, color="grey", linewidth=0.8, linestyle="--", alpha=0.5)
    if n_incomplete > 0 and n_complete > 0:
        idx_sep = 1 + n_complete
        if idx_sep < n_groups:
            sep_x = (x_positions[idx_sep - 1] + x_positions[idx_sep]) / 2
            ax.axvline(sep_x, color="grey", linewidth=0.8, linestyle="--", alpha=0.5)

    # Baseline
    ax.axhline(20, color="black", linewidth=1.2, linestyle=":", label="Random choice (20%)")

    # Axis formatting
    ax.set_ylim(0, y_max)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(10))
    ax.set_ylabel("Accuracy (%)", fontsize=base_font_size * 1.2)
    ax.set_title(title, fontsize=base_font_size * 1.4, fontweight="bold")
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    # Legend
    from matplotlib.patches import Patch

    if print_only_average:
        legend_elements = [
            plt.Line2D([0], [0], color="black", linewidth=1.2, linestyle=":", label="Random choice (20%)")
        ]
    else:
        legend_elements = [
            Patch(facecolor=COLORS[s], hatch=HATCHES[s], edgecolor="black", label=LABELS[s]) for s in SETUPS
        ] + [
            plt.Line2D([0], [0], color="black", linewidth=1.2, linestyle=":", label="Random choice (20%)")
        ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=base_font_size * 0.9, framealpha=0.9)

    # Section annotations
    # "Aggregate" on the left, "All 3 setups" in the middle, "Partial setups" on the right
    y_ann = y_max - 3
    if n_complete > 0 and n_incomplete > 0:
        ax.text(x_positions[0], y_ann, "◄ Aggregate", ha="center", fontsize=base_font_size * 0.7, color="grey")
        mid_c = (x_positions[1] + x_positions[n_complete]) / 2
        ax.text(mid_c, y_ann, "— All 3 setups —", ha="center", fontsize=base_font_size * 0.7, color="grey")
        mid_i = (x_positions[1 + n_complete] + x_positions[-1]) / 2
        ax.text(mid_i, y_ann, "— Partial setups →", ha="center", fontsize=base_font_size * 0.7, color="grey")
    elif n_complete > 0:
        ax.text(x_positions[0], y_ann, "◄ Aggregate", ha="center", fontsize=base_font_size * 0.7, color="grey")
        mid_c = (x_positions[1] + x_positions[-1]) / 2
        ax.text(mid_c, y_ann, "— All 3 setups —", ha="center", fontsize=base_font_size * 0.7, color="grey")

    plt.tight_layout()
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"  ✓ Saved: {output_path}")


# def shorten_name(base):
#     """Shorten model base names for readability on the x-axis."""
#     # Replace common prefixes
#     name = base
#     replacements = [
#         ("google_", ""),
#         ("Qwen_", ""),
#         ("meta-llama_", ""),
#         ("deepseek_", ""),
#         ("aggregate-", "agg-"),
#     ]
#     for old, new in replacements:
#         name = name.replace(old, new)
#     # Wrap long names
#     if len(name) > 25:
#         # Try to break at a hyphen or underscore near the middle
#         mid = len(name) // 2
#         for offset in range(10):
#             for pos in [mid + offset, mid - offset]:
#                 if 0 < pos < len(name) and name[pos] in "-_":
#                     name = name[:pos] + "\n" + name[pos:]
#                     return name
#         name = name[:mid] + "\n" + name[mid:]
#     return name


def main():
    args = parse_args()
    columns, rows = load_data(args.input_tsv)
    models, model_map = extract_model_setups(columns)

    print(f"Loaded {len(rows)} rows, {len(models)} distinct model bases.")
    print(f"Model bases: {list(models.keys())}\n")

    # ---- Identify the rows we need ----
    # 1) OVERALL row: Criterion_Type == "OVERALL"
    # 2) submodality rows: Criterion_Type == "submodality"
    target_rows = {}
    for row in rows:
        ctype = row.get("Criterion_Type", "")
        cval = row.get("Criterion_Value", "")
        if ctype == "OVERALL":
            target_rows["OVERALL"] = row
        elif ctype == "submodality":
            target_rows[f"submodality: {cval}"] = row

    if not target_rows:
        print("ERROR: Could not find OVERALL or submodality rows.", file=sys.stderr)
        sys.exit(1)

    # ---- Generate plots ----
    for label, row in sorted(target_rows.items()):
        # Build accuracy_dict from this row
        accuracy_dict = {}
        for col in columns:
            if col in {"Criterion_Type", "Criterion_Value", "Total_Items"}:
                continue
            accuracy_dict[col] = row.get(col)

        safe_label = label.replace(" ", "_").replace(":", "").replace("/", "-")
        output_path = f"{args.output_prefix}_{safe_label}.png"

        total = row.get("Total_Items", "?")
        plot_title = "" # f"Model Accuracy — {label}  (N = {total})"
        print(f"Generating plot: {plot_title}")
        make_plot(
            plot_title,
            accuracy_dict,
            models,
            output_path,
            dpi=args.dpi,
            ignore_incomplete=args.ignore_incomplete,
            print_only_average=args.print_only_average,
            y_max=args.y_max,
            no_hatch=args.no_hatch,
            base_font_size=args.font_size,
            height=args.height,
        )

    print("\nDone!")


if __name__ == "__main__":
    main()
