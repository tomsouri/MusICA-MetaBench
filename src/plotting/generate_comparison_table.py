# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Generate a nice table comparison of overall results for all models.
Extracts a single row from each model's result TSV based on a criterion (type and value).
Sorts models within each setup (normal, text-only, white-noise) by accuracy.
"""

import pandas as pd
import argparse
from pathlib import Path
import sys

def shorten_model_name(name):
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
        'deepseek_deepseek-v3.2': 'DeepSeek V3.2',
        'google_gemma-3-27b-it': 'Gemma 3 27B',
        'meta-llama_llama-4-scout': 'Llama 4 Scout',
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

def find_result_file(model_dir, b_size, setup, seed):
    file_dir = model_dir / b_size / setup
    if not file_dir.exists():
        return None

    # rep1 is hardcoded as per original script's logic for seed comparison
    n = 1
    candidate_files = list(file_dir.glob(f"jobid_*.rs{seed}.rep{n}.res.tsv"))
    
    if not candidate_files:
        # fallback to older format
        file_path = file_dir / f"rs{seed}.res.tsv"
        if file_path.exists():
            return file_path
        return None
    else:
        # Sort by jobid (extracted from filename) descending
        def get_jobid(p):
            try:
                # jobid_6387272.rs42.rep1.res.tsv -> 6387272
                return int(p.name.split('_')[1].split('.')[0])
            except (IndexError, ValueError):
                return -1
        
        candidate_files.sort(key=get_jobid, reverse=True)
        return candidate_files[0]

def format_time(seconds):
    minutes = seconds / 60
    if minutes < 100:
        # round minutes to whole minutes
        minutes = round(minutes)
        return f"{minutes}m"
    
    hours = minutes / 60
    # if hours < 10:
    #     h = int(hours)
    #     m = int((hours - h) * 60)
    #     return f"{h}h {m}m"
    
    return f"{round(hours)}h"

def main():
    parser = argparse.ArgumentParser(description="Generate a comparison table for all models.")
    parser.add_argument("--base_path", type=str, default="results", help="Path to results directory")
    parser.add_argument("--size", type=str, required=True, help="Benchmark size (e.g., 5, 10, 50)")
    parser.add_argument("--seed", type=str, required=True, help="Seed used (e.g., 42)")
    parser.add_argument("--criterion", type=str, nargs=2, required=True, 
                        metavar=('TYPE', 'VALUE'), help="Criterion Type and Value (e.g., OVERALL ALL)")
    parser.add_argument("--output", type=str, default="comparison_table.tsv", help="Output TSV file")
    parser.add_argument("--tex_output", type=str, help="Optional output path for LaTeX table")
    parser.add_argument("--exclude_errors", action="store_true", help="Exclude error and unparsable percentage columns")
    parser.add_argument("--omit_setup", action="store_true", help="Omit the Setup column from the output")
    parser.add_argument("--multiline_setup", action="store_true", help="Include multiline cells for setups in LaTeX")
    parser.add_argument("--price_decimals", type=int, default=1, help="Number of decimals for price (default: 1)")
    parser.add_argument("--acc_decimals", type=int, default=1, help="Number of decimals for accuracy (default: 1)")
    
    args = parser.parse_args()
    root = Path(args.base_path)
    crit_type, crit_val = args.criterion

    all_models = sorted([p.name for p in root.iterdir() if p.is_dir()])
    setups = ["normal", "text-only", "white-noise"]
    
    data = []

    for setup in setups:
        setup_rows = []
        for model in all_models:
            model_dir = root / model
            file_path = find_result_file(model_dir, args.size, setup, args.seed)
            
            if file_path is None:
                continue
            
            try:
                df = pd.read_csv(file_path, sep='\t')
                # Filter for the specific criterion
                row = df[(df['Criterion_Type'] == crit_type) & (df['Criterion_Value'] == str(crit_val))]
                
                if row.empty:
                    # In some cases Value might be numeric in TSV but passed as string
                    # Try converting crit_val to int/float if it looks like one
                    try:
                        if crit_val.isdigit():
                            row = df[(df['Criterion_Type'] == crit_type) & (df['Criterion_Value'] == int(crit_val))]
                        else:
                            row = df[(df['Criterion_Type'] == crit_type) & (df['Criterion_Value'] == float(crit_val))]
                    except:
                        pass
                
                if row.empty:
                    print(f"Warning: Criterion {crit_type}={crit_val} not found in {file_path}")
                    continue
                
                row = row.iloc[0]
                
                entry = {
                    "Model": shorten_model_name(model),
                    "Setup": setup,
                    "Acc.": round(row["Accuracy_Percent"], args.acc_decimals),
                    "Time": format_time(row["Total_Time_s"]),
                    "Price ($)": round(row["Total_Price"], args.price_decimals) if not pd.isna(row["Total_Price"]) else 0.0,
                }
                
                if not args.exclude_errors:
                    entry["Error (%)"] = round(row["Model_Error_Percent"], 1)
                    entry["Unparsable (%)"] = round(row["Unparsable_Percent"], 1)
                
                setup_rows.append(entry)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
        
        # Sort models in this setup by accuracy descending
        setup_rows.sort(key=lambda x: x["Acc."], reverse=True)
        data.extend(setup_rows)

    if not data:
        print("No data found for the given parameters.")
        return

    # Add random-choice baseline at the bottom
    baseline = {
        "Model": "Random Baseline",
        "Setup": "N/A",
        "Acc.": round(20.0, args.acc_decimals),
        "Time": "N/A",
        "Price ($)": "N/A"
    }
    if not args.exclude_errors:
        baseline["Error (%)"] = 0.0
        baseline["Unparsable (%)"] = 0.0
    
    data.append(baseline)

    final_df = pd.DataFrame(data)
    
    if args.omit_setup or args.multiline_setup:
        final_df = final_df.drop(columns=["Setup"])

    # make directory if it does not exist
    output_dir = Path(args.output).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    final_df.to_csv(args.output, sep='\t', index=False)
    print(f"Table saved to {args.output}")

    if args.tex_output:
        # Generate LaTeX table with booktabs and midrules between setups
        with open(args.tex_output, "w") as f:
            col_spec = "l" * len(final_df.columns)
            if args.multiline_setup:
                # Add a column for the multirow setup label
                col_spec = "l" + col_spec
                
            f.write("\\begin{tabular}{" + col_spec + "}\n")
            f.write("\\toprule\n")
            
            header = list(final_df.columns)
            if args.multiline_setup:
                header = ["Setup Group"] + header
            
            f.write(" & ".join(header).replace("%", "\\%").replace("$", "\\$") + " \\\\\n")
            f.write("\\midrule\n")
            
            # Group by setup to handle multirow logic
            setup_groups = []
            if data:
                current_group = []
                current_setup = data[0]["Setup"]
                for entry in data:
                    if entry["Setup"] == current_setup:
                        current_group.append(entry)
                    else:
                        setup_groups.append((current_setup, current_group))
                        current_setup = entry["Setup"]
                        current_group = [entry]
                setup_groups.append((current_setup, current_group))

            total_idx = 0
            for setup_name, group in setup_groups:
                for i, entry in enumerate(group):
                    row_vals = list(final_df.iloc[total_idx].values)
                    vals = [str(v).replace("%", "\\%").replace("$", "\\$") for v in row_vals]
                    
                    if args.multiline_setup:
                        if i == 0:
                            label = setup_name if setup_name != "N/A" else "Baseline"
                            vals = [f"\\multirow{{{len(group)}}}{{*}}{{{label}}}"] + vals
                        else:
                            vals = [""] + vals
                    
                    f.write(" & ".join(vals) + " \\\\\n")
                    total_idx += 1
                
                # Only add midrule IF we are not omitting the setup info entirely
                # Or if we want clearly separated blocks even without labels
                if setup_name != setup_groups[-1][0]:
                    f.write("\\midrule\n")
                
            f.write("\\bottomrule\n")
            f.write("\\end{tabular}\n")
        print(f"LaTeX table saved to {args.tex_output}")

if __name__ == "__main__":
    main()
