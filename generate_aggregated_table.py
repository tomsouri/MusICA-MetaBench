# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
For a single size and seed (that is, for a single instance of benchmark),
aggregate the results across all the models and setups.
"""

import pandas as pd
import argparse
from pathlib import Path

import pandas as pd
import argparse
from pathlib import Path

def aggregate_results(base_path, b_size, seed, fields, setup, output, compare_mode):
    root = Path(base_path)

    if seed is None:
        merge_keys = ['Criterion_Type', 'Criterion_Value']
    else:
        merge_keys = ['Criterion_Type', 'Criterion_Value', 'Total_Items']
    
    # Identify unique models
    all_models = [p.name for p in root.iterdir() if p.is_dir()]
    
    # Prepare list to hold data
    final_cols = []
    loaded_cols = []

    for model in all_models:
        setups = ["normal", "text-only", "white-noise"] if compare_mode else [setup]
        
        for setup in setups:
            
            if seed is None:
                file_path = root / model / b_size / f"{setup}.tsv"
            else:
                # TODO: this will not work as the filename now includes also the jobid
                # we need to find a way to identify the correct file for the given seed
                file_dir = root / model / b_size / setup
                if not file_dir.exists():
                    print(f"Warning: Missing directory {file_dir}. Skipping model {model} setup {setup}.")
                    continue

                # In this setting, only take the results from the first repetition (n=1) to avoid duplicates, since we are comparing across seeds
                n = 1

                # the filepath is in the format jobid_{id}.rs{seed}.rep{n}.res.tsv, but we do not know the id in advance
                # find the file with the correct seed, and if there are multiple files with the same seed, take the one with highest jobid
                candidate_files = list(file_dir.glob(f"jobid_*.rs{seed}.rep{n}.res.tsv"))
                if not candidate_files:
                    # fallback to older format if necessary or skip
                    file_path = file_dir / f"rs{seed}.res.tsv"
                else:
                    # Sort by jobid (extracted from filename) descending
                    def get_jobid(p):
                        try:
                            return int(p.name.split('_')[1].split('.')[0])
                        except (IndexError, ValueError):
                            return -1
                    
                    candidate_files.sort(key=get_jobid, reverse=True)
                    file_path = candidate_files[0]

            if not file_path.exists():
                print(f"Warning: Missing {file_path}. Skipping model {model} setup {setup}.")
                continue
            
            df = pd.read_csv(file_path, sep='\t')

            # Add requested fields for this model/setup
            for field in fields:
                if field not in df.columns:
                    raise ValueError(f"Field '{field}' not in {file_path}")
                
                # Column naming: Model_Setup_Field (e.g., Llama_normal_Accuracy_Percent)
                
                setup_str = f"_{setup}" if len(setups) > 1 else ""
                field_str = field.replace(" ", "_")  # Replace spaces with underscores for column names
                field_str = f"_{field_str}" if len(fields) > 1 else ""
                col_name = f"{model}{setup_str}{field_str}"

                loaded_cols.append((file_path, df, field, col_name))

    # A run limited to some modalities has fewer rows, so the largest run defines the table
    reference = max((df for _, df, _, _ in loaded_cols), key=len)
    base_df = reference[merge_keys].copy()
    align_keys = ['Criterion_Type', 'Criterion_Value']
    base_index = pd.MultiIndex.from_frame(reference[align_keys])

    for file_path, df, field, col_name in loaded_cols:
        # Validation
        if len(df) == len(reference):
            if not base_df.equals(df[merge_keys]):
                raise ValueError(f"Consistency error: {file_path} does not match base keys.")
        else:
            if not pd.MultiIndex.from_frame(df[align_keys]).isin(base_index).all():
                raise ValueError(f"Consistency error: {file_path} has criteria missing from the base keys.")
            print(f"Warning: {file_path} is a partial run ({len(df)} of {len(reference)} rows), missing rows stay empty.")

        final_cols.append(df.set_index(align_keys)[field].reindex(base_index).reset_index(drop=True).rename(col_name))

    # Construct Final DataFrame
    result_df = pd.concat([base_df] + final_cols, axis=1)
    
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output, sep='\t', index=False)
    print(f"Results saved to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", required=True, help="Benchmark size")
    parser.add_argument("--seed", type=int, default=None, help="Seed (e.g., 42)")
    # parser.add_argument("--setup", default="normal", help="Setup name")
    # parser.add_argument("--field", nargs='+', default=["Accuracy_Percent", "Unparsable_Percent", "Model_Error_Percent", "Total_Time_s", "Total_Price"], help="List of fields to extract")
    parser.add_argument("--path", default="aggregated/comparison_between_seeds/", help="Root results directory")
    parser.add_argument("--output", default="aggregated/models_comparison/", help="Path to save the output TSV")
    # parser.add_argument("--normal_vs_textonly_comparison", action="store_true")

    args = parser.parse_args()

    # Either seed should be None (then path should be aggregated/comparison_between_seeds/) 
    # or seed should be provided (then path should be results/)

    
    if args.seed is None:
        interesting_fields = ["Mean_Accuracy (10 runs)", "Mean_Unparsable_Percent", "Mean_Model_Error_Percent", "Sum_Total_Time_s", "Sum_Total_Price"]
        single_field = ["Mean_Accuracy (10 runs)"]
        outdir= Path(args.output) / f"size_{args.size}" / "mean_over_seeds"
    else:
        single_field = ["Accuracy_Percent"]
        interesting_fields = ["Accuracy_Percent", "Unparsable_Percent", "Model_Error_Percent", "Total_Time_s", "Total_Price"]
        outdir= Path(args.output) / f"size_{args.size}" / f"seed_{args.seed}"
    

    for setup in ["normal", "text-only", "white-noise"]:
        print(f"Aggregating results for setup: {setup}")
        for fields in [interesting_fields, single_field]:
            print(f"Processing fields: {fields}")
            outfile = outdir / f"{setup}"
            outfile = (outfile / "all_fields.tsv") if len(fields) > 1 else (outfile / "accuracy_only.tsv")

            aggregate_results(args.path, args.size, args.seed, fields, setup, outfile, False)
    
    outfile = outdir / "comparison_normal_vs_textonly.tsv"
    aggregate_results(args.path, args.size, args.seed, single_field, None, outfile, True)

# example usage:
# .venv/bin/python3 generate_aggregated_table.py --size 20 --seed 55 --output aggregated/