# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

import pandas as pd
import matplotlib.pyplot as plt
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
        'aggregate-gpt-5-full': 'agg-GPT-5 Full'
    }
    if name in mapping:
        return mapping[name]
    
    # Generic shortening
    name = name.replace('google_', '').replace('aggregate-', '')
    if len(name) > 15:
        return name[:12] + '...'
    return name

def plot_stddev(input_file, output_file=None, exclude_size_one=False, log_x=False, multiply_sizes_by=1, figsize=(10, 6), fontsize=10, legend_fontsize=None):
    # Read the TSV file
    df = pd.read_csv(input_file, sep='\t', index_col=0)
    
    if exclude_size_one and '1' in df.columns:
        df = df.drop(columns=['1'])

    # Preprocess header: convert to numeric (benchmark sizes)
    # The header names are like '1', '5', '10', etc.
    df.columns = [str(int(col) * multiply_sizes_by) for col in df.columns]
    
    # Update font size
    plt.rcParams.update({'font.size': fontsize})

    # Plot configuration
    plt.figure(figsize=figsize)
    
    # Color-blind friendly cycle (Okabe-Ito palette)
    cb_colors = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7', '#000000']
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']
    
    for i, (model_name, row) in enumerate(df.iterrows()):
        # Drop NaN values for this model
        valid_data = row.dropna()
        if valid_data.empty:
            continue
            
        x_vals = [int(x) for x in valid_data.index]
        y_vals = valid_data.values
        
        color = cb_colors[i % len(cb_colors)]
        marker = markers[i % len(markers)]
        
        plt.plot(x_vals, y_vals, 
                 label=shorten_model_name(model_name), 
                 marker=marker, 
                 linestyle=':', 
                 color=color,
                 alpha=0.8)

    if log_x:
        plt.xscale('log')
        # Ensure we have sensible ticks for log scale if the sizes are specific values
        unique_x = sorted(list(set([int(x) for col in df.columns for x in [col]])))
        plt.xticks(unique_x, labels=[str(x) for x in unique_x])

    plt.xlabel('Benchmark Size (total item count, s)')
    plt.ylabel('Stddev of acc. (%)')
    # title = f'Standard Deviation vs Benchmark Size'
    title = ""
    plt.title(title, fontsize=fontsize)
    plt.grid(True, linestyle='--', alpha=0.6)
    
    if legend_fontsize is None:
        legend_fontsize = fontsize
    plt.legend(loc='upper right', fontsize=legend_fontsize)
    plt.tight_layout()

    if output_file:
        # make directory if it does not exist
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        plt.savefig(output_file, dpi=300)
        print(f"Plot saved to {output_file}")
    else:
        # Default output name based on input
        base = os.path.splitext(input_file)[0]
        out = f"{base}_plot.png"
        plt.savefig(out, dpi=300)
        print(f"Plot saved to {out}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Plot stddev from TSV table.')
    parser.add_argument('input', help='Path to the input TSV file (e.g., tables/normal/stddev-only/table_ALL.tsv)')
    parser.add_argument('--output', help='Path to the output image file', default=None)
    parser.add_argument('--exclude-size-one', action='store_true', help='Exclude size 1 from the plot')
    parser.add_argument('--log-x', action='store_true', help='Use log scale for x-axis')
    parser.add_argument('--multiply-sizes-by', type=int, default=1, help='Multiply benchmark sizes by this factor')
    parser.add_argument('--figsize', type=float, nargs=2, default=[10, 6], help='Plot size (width height)')
    parser.add_argument('--height', type=float, help='Override the height of the plot (width stays from --figsize)')
    parser.add_argument('--fontsize', type=int, default=10, help='Font size for labels and legend')
    parser.add_argument('--legend-fontsize', type=int, default=None, help='Font size for legend (defaults to --fontsize)')
    
    args = parser.parse_args()
    
    figsize = tuple(args.figsize)
    if args.height:
        figsize = (figsize[0], args.height)
    
    plot_stddev(args.input, args.output, args.exclude_size_one, args.log_x, args.multiply_sizes_by, figsize, args.fontsize, args.legend_fontsize)
