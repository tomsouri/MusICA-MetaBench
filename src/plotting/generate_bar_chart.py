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
    name = str(name).replace('google_', '').replace('aggregate-', '')
    if len(name) > 15:
        return name[:12] + '...'
    return name

def clean_label(label):
    return str(label).replace('audio.mastermix.wav', 'Audio').replace('symbolic.abc.txt', 'Symbolic (ABC)').replace('visual.short.png', 'Image')

def generate_bar_chart(input_file, output_file, criterion_type, excluded_models, included_models, include_baseline, font_size, group_by_models, round_to_int, bold_best, sort_per_group, show_names_below, y_limit, height, show_guide_lines, tight_crop, width=14, dpi=None, extended_palette=False, marked_models=None):
    # Load data
    df = pd.read_csv(input_file, sep='\t')
    
    # Filter by criterion_type
    filtered_df = df[df['Criterion_Type'] == criterion_type]
    
    if filtered_df.empty:
        print(f"No data found for Criterion_Type: {criterion_type}")
        return

    # Identification of model columns (skip Criterion_Type, Criterion_Value, Total_Items)
    model_columns = [col for col in df.columns if col not in ['Criterion_Type', 'Criterion_Value', 'Total_Items']]
    
    # Filter models
    if included_models:
        model_columns = [col for col in model_columns if col in included_models]
    if excluded_models:
        model_columns = [col for col in model_columns if col not in excluded_models]

    # Sort models by their OVERALL ALL value if available
    overall_all = df[(df['Criterion_Type'] == 'OVERALL') & (df['Criterion_Value'] == 'ALL')]
    if not overall_all.empty:
        model_scores = {model: overall_all[model].values[0] for model in model_columns}
        model_columns = sorted(model_columns, key=lambda x: model_scores[x], reverse=True)
    else:
        # Fallback: sort by mean accuracy across all criterion values in current view
        model_avg_scores = {model: filtered_df[model].mean() for model in model_columns}
        model_columns = sorted(model_columns, key=lambda x: model_avg_scores[x], reverse=True)

    plt.rcParams.update({'font.size': font_size})
    plt.style.use('tableau-colorblind10') 

    fig, ax = plt.subplots(figsize=(width, height))

    # Colorblind-friendly color palette (Okabe-Ito inspired for the main groups if possible)
    # Using the colors from generate_plot_with_comparison_of_normal_textonly_noise.py
    # and extending them for more categories/models.
    cb_colors = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7", "#F0E442", "#0072B2", "#D55E00", "#000000"]
    if extended_palette:
        cb_colors += ["#882255", "#332288", "#999933"]

    if group_by_models:
        # Grouped by Models: Each model is a group, columns are criterion values
        criterion_values = filtered_df['Criterion_Value'].tolist()
        num_groups = len(model_columns)
        num_bars_per_group = len(criterion_values)
        
        bar_width = 0.8 / num_bars_per_group
        indices = np.arange(num_groups)

        for i, crit_val in enumerate(criterion_values):
            scores = []
            for model in model_columns:
                val = filtered_df[filtered_df['Criterion_Value'] == crit_val][model].values[0]
                scores.append(val)
            
            color = cb_colors[i % len(cb_colors)]
            bars = ax.bar(indices + i * bar_width, scores, bar_width, label=clean_label(crit_val), color=color)
            
            # Add value labels on top
            v_fontsize = font_size * 0.75
            max_score = np.nanmax(scores) if scores else 0
            for idx, bar in enumerate(bars):
                height = bar.get_height()
                if np.isnan(height):
                    continue
                label_text = f"{int(round(height))}" if round_to_int else f"{height:.1f}"
                is_best = bold_best and height == max_score and height > 0
                fontweight = 'bold' if is_best else 'normal'
                
                ax.text(bar.get_x() + bar.get_width() / 2, height + 0.8,
                        label_text, ha='center', va='bottom', fontsize=v_fontsize, fontweight=fontweight)

        ax.set_xticks(indices + bar_width * (num_bars_per_group - 1) / 2)
        ax.set_xticklabels([shorten_model_name(m) for m in model_columns], rotation=45, ha='right')
        ax.set_ylabel('Accuracy (%)')
        ax.set_title(f'Results by Model ({criterion_type})')

    else:
        # Grouped by Criterion Values: Each criterion value is a group, columns are models
        criterion_values = filtered_df['Criterion_Value'].tolist()
        num_groups = len(criterion_values)
        num_bars_per_group = len(model_columns)

        bar_width = 0.8 / num_bars_per_group
        indices = np.arange(num_groups)

        # Plot each group
        for i, crit_val in enumerate(criterion_values):
            group_row = filtered_df[filtered_df['Criterion_Value'] == crit_val]
            # Models without results for this group (e.g. no audio run) are left out of it
            group_models = [m for m in model_columns if pd.notna(group_row[m].values[0])]

            # Use the globally sorted model_columns or sort specifically for this group
            if sort_per_group:
                group_model_scores = {m: group_row[m].values[0] for m in group_models}
                sorted_models_for_group = sorted(group_models, key=lambda x: group_model_scores[x], reverse=True)
            else:
                sorted_models_for_group = group_models
                group_model_scores = {m: group_row[m].values[0] for m in group_models}

            max_score = max(group_model_scores.values()) if group_model_scores else 0

            for j, model in enumerate(sorted_models_for_group):
                score = group_model_scores[model]
                # Keep color consistent for each model
                model_idx = model_columns.index(model)
                color = cb_colors[model_idx % len(cb_colors)]
                
                # Only add to legend if names are NOT shown below
                label = ""
                if not show_names_below and i == 0:
                    label = shorten_model_name(model)
                
                bars = ax.bar(indices[i] + j * bar_width, score, bar_width, color=color, label=label)

                # Add value labels on top
                v_fontsize = font_size * 0.75
                for bar in bars:
                    height = bar.get_height()
                    label_text = f"{int(round(height))}" if round_to_int else f"{height:.1f}"
                    is_best = bold_best and height == max_score and height > 0
                    fontweight = 'bold' if is_best else 'normal'

                    ax.text(bar.get_x() + bar.get_width() / 2, height + 0.8,
                            label_text, ha='center', va='bottom', fontsize=v_fontsize, fontweight=fontweight)
            
            # Show model names below each bar if requested
            if show_names_below:
                for j, model in enumerate(sorted_models_for_group):
                    pos = indices[i] + j * bar_width
                    name = shorten_model_name(model)
                    is_marked = model in (marked_models or [])
                    # Text annotation
                    t = ax.text(pos, -1, name + ('*' if is_marked else ''), rotation=45, ha='right', va='top', fontsize=font_size*0.8,
                                fontstyle='italic' if is_marked else 'normal')
                    
                    if show_guide_lines:
                        # Draw a dotted line from the name label to the bar base
                        # We use ConnectionPatch or simple plot with data/axis transform
                        # To get from the "last character" (which is the top-right of the rotated bounding box)
                        # to the bar center, we can approximate it:
                        ax.plot([pos - 0.1, pos], [-1.2, -0.1], color='gray', linestyle=':', linewidth=0.5, 
                                transform=ax.get_xaxis_transform(), clip_on=False, alpha=0.5)

        ax.set_xticks(indices + bar_width * (num_bars_per_group - 1) / 2)
        ax.set_xticklabels([clean_label(l) for l in criterion_values], rotation=45, ha='right')
        ax.set_ylabel('Accuracy (%)')
        
        # Add dotted vertical lines and criterion labels inside the chart
        for i, crit_val in enumerate(criterion_values):
            # Calculate separators (dotted lines)
            if i > 0:
                prev_end = indices[i-1] + bar_width * num_bars_per_group
                curr_start = indices[i]
                mid_sep = (prev_end + curr_start) / 2 - bar_width/2
                ax.axvline(x=mid_sep, color='gray', linestyle=':', linewidth=1)
            
            # Label inside the chart (at the top but below 100)
            group_row = filtered_df[filtered_df['Criterion_Value'] == crit_val]
            num_bars_in_group = int(group_row[model_columns].notna().sum(axis=1).iloc[0])
            group_center = indices[i] + bar_width * (num_bars_in_group - 1) / 2
            ax.text(group_center, 95, clean_label(crit_val), 
                    ha='center', va='top', fontweight='bold', fontsize=font_size)

        # Remove x-axis tick labels
        ax.set_xticklabels([])
        ax.set_xticks([])
        
        ax.set_ylabel('Accuracy (%)')
        ax.set_ylim(0, y_limit if y_limit else 100) # Use custom limit or 100
        # No overall title (removed)

    # Add random baseline if requested
    if include_baseline:
        ax.axhline(y=20, color='gray', linestyle='--', label='Random Baseline (20%)')
        # Add text label at the rightmost end of the line, rotated 90 degrees
        # Using coordinate system of the axes for X (0 to 1) and data for Y
        # ax.get_yaxis_transform() uses Axes coordinates for X and Data coordinates for Y
        ax.text(0.995, 22, 'Random Baseline (20%)', 
                transform=ax.get_yaxis_transform(),
                rotation=90, va='bottom', ha='right', color='gray', fontsize=font_size*0.7)
    
    if group_by_models:
        if not y_limit:
            ax.set_ylim(0, 105)
        else:
            ax.set_ylim(0, y_limit)
        plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    else:
        # Legend removed as requested, baseline description is now on the line
        pass
    
    # ensure the output directory exists
    if os.path.dirname(output_file):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Save with tight layout or standard padding
    if tight_crop:
        plt.savefig(output_file, bbox_inches='tight', pad_inches=0.01, dpi=dpi)
    else:
        plt.savefig(output_file, bbox_inches='tight', dpi=dpi)
    print(f"Chart saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate a bar chart from a TSV table.')
    parser.add_argument('input_file', type=str, help='Path to the input TSV file')
    parser.add_argument('--output_file', type=str, default='bar_chart.png', help='Path to the output image file')
    parser.add_argument('--criterion_type', type=str, default='submodality', help='Criterion type to plot (e.g., submodality, category)')
    parser.add_argument('--exclude', nargs='*', help='List of model names to exclude')
    parser.add_argument('--include', nargs='*', help='List of model names to include (only these will be shown)')
    parser.add_argument('--baseline', action='store_true', help='Include a random baseline at 20%% accuracy')
    parser.add_argument('--font_size', type=int, default=12, help='Font size for the plot labels and legend')
    parser.add_argument('--group_by_models', action='store_true', help='Group by models instead of criterion values')
    parser.add_argument('--round', action='store_true', help='Round accuracy values to integers on top of bars')
    parser.add_argument('--bold_best', action='store_true', help='Bold the highest accuracy value in each group')
    parser.add_argument('--sort_per_group', action='store_true', help='Sort models by accuracy within each group specifically')
    parser.add_argument('--show_names_below', action='store_true', help='Show model names below bars and remove from legend')
    parser.add_argument('--y_limit', type=int, help='Force a specific Y-axis limit (e.g., 60 for better granularity)')
    parser.add_argument('--height', type=float, default=8, help='Height of the plot in inches (use to shrink/stretch the vertical size)')
    parser.add_argument('--show_guide_lines', action='store_true', help='Show soft dotted guide lines from model names to bars')
    parser.add_argument('--tight_crop', action='store_true', help='Crop the final image to the absolute minimum bounding box')
    parser.add_argument('--width', type=float, default=14, help='Width of the plot in inches (increase for more models)')
    parser.add_argument('--dpi', type=int, help='Resolution of raster output such as PNG (default: matplotlib default of 100)')
    parser.add_argument('--extended_palette', action='store_true', help='Add 3 more colors, so that up to 11 models do not share a color')
    parser.add_argument('--mark_models', nargs='*', help='Models whose names below the bars are written in italics with an asterisk (with --show_names_below)')

    args = parser.parse_args()

    generate_bar_chart(args.input_file, args.output_file, args.criterion_type, args.exclude, args.include, args.baseline, args.font_size, args.group_by_models, args.round, args.bold_best, args.sort_per_group, args.show_names_below, args.y_limit, args.height, args.show_guide_lines, args.tight_crop, args.width, args.dpi, args.extended_palette, args.mark_models)
