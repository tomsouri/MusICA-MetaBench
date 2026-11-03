# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os

def shorten_model_name(name):
    # Mapping for common model names to shorter versions
    mapping = {
        'google_gemini-3.1-flash-lite-preview': 'Gemini 3.1 FL',
        'google_gemini-3.1-pro-preview': 'Gemini 3.1 Pro',
        'google_gemini-2.0-flash-lite-001': 'Gemini 2.0 FL',
        'google_gemini-2.5-flash-lite': 'Gemini 2.5 FL',
        'Qwen_Qwen3-Omni-30B-A3B-Thinking': 'Qwen3 Omni 30B',
        'aggregate-gpt-4o': 'agg-GPT-4o',
        'aggregate-gpt-5': 'agg-GPT-5',
        'aggregate-mistral': 'agg-Mistral',
        'aggregate-gpt-5-full': 'agg-GPT-5 Full',
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

def generate_spider_chart(input_file, output_file, criterion_type, excluded_models, included_models, include_baseline, font_size, compact=False, extended_palette=False):
    # Load data
    df = pd.read_csv(input_file, sep='\t')
    
    # Filter by criterion_type
    filtered_df = df[df['Criterion_Type'] == criterion_type]
    
    if filtered_df.empty:
        print(f"No data found for Criterion_Type: {criterion_type}")
        return

    # Extract axes (Criterion_Values)
    labels = filtered_df['Criterion_Value'].tolist()
    num_vars = len(labels)
    
    # Compute angle for each axis
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    
    # Rotation logic for compactness
    if compact:
        # Rotate by 90 degrees (pi/2) to potentially save vertical space if labels are wide
        offset = np.pi / 2
        angles = [(a + offset) % (2 * np.pi) for a in angles]

    # Close the loop
    angles += angles[:1]
    
    plt.rcParams.update({'font.size': font_size})
    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
    
    # Ensure grid and spines are drawn on top of the filled areas
    ax.set_axisbelow(False)
    # Give the grid a high zorder so it's visible through overlapping fills
    ax.grid(True, zorder=10, color='gray', linestyle='--', alpha=0.5)
    model_columns = [col for col in df.columns if col not in ['Criterion_Type', 'Criterion_Value', 'Total_Items']]
    
    # Filter models
    if included_models:
        model_columns = [col for col in model_columns if col in included_models]
    if excluded_models:
        model_columns = [col for col in model_columns if col not in excluded_models]

    # Pre-sort models by their OVERALL ALL value if available, for consistent coloring/legend
    overall_all = df[(df['Criterion_Type'] == 'OVERALL') & (df['Criterion_Value'] == 'ALL')]
    if not overall_all.empty:
        model_scores = {model: overall_all[model].values[0] for model in model_columns}
        model_columns = sorted(model_columns, key=lambda x: model_scores[x], reverse=True)
        
    # High contrast, colorblind-friendly color palette
    cb_colors = ['#0077BB', '#EE7733', '#009988', '#CC3311', '#AA4499', '#EECC66']
    if extended_palette:
        cb_colors += ['#882255', '#332288', '#999933']
        
    max_accuracy = 0
    for i, model in enumerate(model_columns):
        values = filtered_df[model].tolist()
        max_accuracy = max(max_accuracy, max(values))
        # Close the loop
        values += values[:1]
        
        color = cb_colors[i % len(cb_colors)]
        ax.plot(angles, values, linewidth=2, linestyle='solid', label=shorten_model_name(model), color=color)
        ax.fill(angles, values, alpha=0.1, color=color)

    # Add random baseline if requested
    if include_baseline:
        max_accuracy = max(max_accuracy, 20.0)
        baseline_values = [20.0] * num_vars
        baseline_values += baseline_values[:1]
        ax.plot(angles, baseline_values, linewidth=2, linestyle='--', color='gray', label='Random Baseline (20%)')
    
    # Beautify labels
    clean_labels = [l.replace('audio.mastermix.wav', 'Audio').replace('symbolic.abc.txt', 'Symbolic (ABC)').replace('visual.short.png', 'Image') for l in labels]
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(clean_labels)
    
    # Set y-axis range
    if compact and max_accuracy <= 80:
        y_limit = 80
        ticks = [20, 40, 60, 80]
        tick_labels = ["20%", "40%", "60%", "80%"]
    else:
        y_limit = 100
        ticks = [20, 40, 60, 80, 100]
        tick_labels = ["20%", "40%", "60%", "80%", "100%"]
        
    ax.set_ylim(0, y_limit)
    ax.set_yticks(ticks)
    ax.set_yticklabels(tick_labels)
    
    # In compact mode, move the radial labels (accuracy percentages) 
    # away from the vertical axis if it's likely to collide with category labels
    if compact:
        ax.set_rlabel_position(210)

    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=font_size)

    # ensure the output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    plt.savefig(output_file, bbox_inches='tight')
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a spider chart from a TSV table.')
    parser.add_argument('input_file', type=str, help='Path to the input TSV file')
    parser.add_argument('--output_file', type=str, default='spider_chart.png', help='Path to the output image file')
    parser.add_argument('--criterion_type', type=str, default='submodality', help='Criterion type to plot (e.g., submodality, category)')
    parser.add_argument('--exclude', nargs='*', help='List of model names to exclude')
    parser.add_argument('--include', nargs='*', help='List of model names to include (only these will be shown)')
    parser.add_argument('--baseline', action='store_true', help='Include a random baseline at 20%% accuracy')
    parser.add_argument('--font_size', type=int, default=12, help='Font size for the plot labels and legend')
    parser.add_argument('--compact', action='store_true', help='Make the chart more compact (crop axes at 80%% if possible, rotate chart)')
    parser.add_argument('--extended_palette', action='store_true', help='Add 3 more colors, so that up to 9 models do not share a color')

    args = parser.parse_args()

    generate_spider_chart(args.input_file, args.output_file, args.criterion_type, args.exclude, args.include, args.baseline, args.font_size, args.compact, args.extended_palette)
