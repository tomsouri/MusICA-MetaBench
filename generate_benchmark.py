# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
Sample run:

.venv/bin/python3 generate_benchmark.py --config benchmark-generation-config-chorale-bricks.yaml 

--- Starting Pipeline ---
Step  0  [Instantiate Questions]                   Items:       16  Errors:    0
Step  1  [Product & Extraction]                    Items:      160  Errors:    0
Step  2  [Sort Distractors]                        Items:      160  Errors:    0
Step  3  [Submodalities Product]                   Items:      480  Errors:    0
Step  4  [Generate Initial Final Options]          Items:      480  Errors:    0
Step  5  [Add NOTA-correct items]                  Items:      593  Errors:    0
Step  6  [Labels & Sorting Options]                Items:      593  Errors:    0

Step 7 [Final Save] complete. File saved to: final_benchmark.tsv

--- Step 8: Final Statistics ---
Total Benchmark Items : 38
NOTA Correct Items    : 8 (21.05%)
Total Errors Recorded : 0
--------------------------------

Prompt used to generate the script (also describes quite accurately what the script does):

Generate a python script and provide a sample config yaml file. The script should integrate the logic of the script below as a first step, and then add additional
steps, as described below. After each step, the script should print the intermediate benchmark into a tsv file in
subdirectory "intermediate_benchmarks" with a name that reflects the step that was just completed. The final output
should be a tsv file in the root directory with the name specified by the user in the --output argument.
Also, the script should take notes on error statistics and counts of items in the benchmark after each step, and print
the statistics after each step, and at the end of the script.

The steps to be implemented are as follows:
- 0.step: load a config file in yaml format that specifies further settings of the benchmark:
    - name of the method to be used for sorting the distractor pool by difficulty (to be applied in step 2)
    - number of options to be included in each question
    - NOTA text ("none of the other options is correct")
    - whether to add NOTA as one of the options
    - list of submodalities to be included in the current version of the benchmark, specified by the name of the file
      ("audio.mastermix.wav", "image.pdf", "symbolic.musicxml")
    - desired percentage of NOTA-correct questions in the benchmark
    - labels to be added to the options (e.g., "(A)", "(B)", "(C)", "(D)")
    - seed for random sorting (to ensure reproducibility, use the seed right at the beginning of the script)
    - the cmdline args of the script below, to be used for step 1 (e.g., paths to the meta-questions and pieces files, and the python file containing the methods for ground truth and distractor pool extraction)
- 1.step: generate the product of meta-questions and pieces, and compute the ground truth and distractor pool for each
question-piece pair using the methods specified in the meta-questions file. This is the logic that is currently
implemented in the script below.
- 2.step: apply a method as specified in the config to sort the distractor pool for each question-piece pair (with
preliminary dummy implementation of the method that just shuffles the distractor pool, to be replaced later with a real
implementation). This method should be applied to each question-piece pair in the benchmark generated in step 1, the
distractors sorted should be added to a new column "sorted_distractors" and
the output should be saved in an intermediate benchmark file named "benchmark_distractors_sorted.tsv".
- 3.step: generate a product of the benchmark from the 2. step with the list of submodalities specified in the config
(excluding submodalities that are not part of any modality that is supported for the given question, as specified in
`modality_in_question` column in the meta-questions file), adding the submodality name as a new column "submodality", and the column "path_to_question_context_file", which would
be the concatenation of the piece directory (column "path" from the pieces file, e.g. pieces-chorale-bricks.tsv) and the submodality name. The output should
be saved in an intermediate benchmark file named "benchmark_with_submodalities.tsv".
- 4.step: for each question-piece-submodality triplet, generate the final options to be included in the benchmark:
    - if NOTA is to be included, take it (the text specified in config) as one of the options,
    - take the ground truth as one of the options,
    - and take the desired number of remaining options from the sorted distractor pool, in order of difficulty (e.g., if
      the desired number of options is 5 and both NOTA and ground truth are included, take the top 3 most difficult distractors from the
      sorted distractor pool, and if NOTA is not included, take the top 4 most difficult distractors from the sorted
      distractor pool).
    - add the ground truth to a new column "final_correct_option"
    - The final options should be added in a new column "final_options" as a JSON string (list of options), and the output should be saved in an intermediate benchmark file named "benchmark_with_final_options.tsv".
- 5.step: add questions where ground-truth is excluded from the options (NOTA is correct answer) - only if the
  percentage of such desired questions is non-zero:
    - compute the probability that a random item should be added with NOTA as the correct option, such that the final
      percentage of NOTA-correct questions in the benchmark is as specified in the config (e.g., if the desired
      percentage is 20%, the probability would be 25%, because if we add an item with NOTA as the correct option with
      25% probability, we would have 25% NOTA-correct items among the newly added items, and if we add these items to
      the existing benchmark where 0% of items are NOTA-correct, we would end up with 20% NOTA-correct items in the
      final benchmark).
    - for each item from the benchmark after step 4, witch probability computed in the previous step, add a new item to
      the benchmark where the options are:
        - NOTA text
        - the top (N-1) most difficult distractors from the sorted distractor pool 
    - the column "final_correct_option" is set to NOTA text. The output should be saved in an intermediate benchmark file named
      "benchmark_with_NOTA_correct_items_added.tsv".
- 6.step: 
    - first, sort the options alphabetically, and then sort them randomly
    - add labels to the options (e.g., "(A)", "(B)", "(C)", "(D)") as specified in the config
    - add column all_choices (Type: list of str): A list containing all valid choice identifiers (usually letters
      or numbers). Example: ['A', 'B', 'C', 'D']
    - add column index2ans (Type: Dict[str, str]): A dictionary mapping the choice identifiers to their actual textual
      content. Example: {'A': '10 cm', 'B': '15 cm', 'C': '20 cm', 'D': '25cm', 'E': 'none of the other options is
      correct'}
    - The options should be in a new column "labeled_final_options" as a JSON string (list of options with labels), and the
  correct option should be in a new column "labeled_final_correct_option".
    - save the output as the intermediate bechmark file named "benchmark_with_labeled_sorted_final_options.tsv".
- 7.step:
    - save the final output (the same) in a tsv file in the root directory with the name specified in the config (e.g.,
      "final_benchmark.tsv").
- 8.step:
    - print the  final statistics of the benchmark, including the total number of items, the number and percentage of NOTA-correct
  items, and any errors encountered during the process.
"""


"""
Adjust the following script, such that before step 1, it would perform step 0 as described here:
- from generation config yaml, read the following variables:
    - questions_per_skill_count: 3 # number of questions to generate per skill (for the draft, we can keep it small, e.g. 10, and then scale up after analyzing the results and iterating on the question templates)
    - ontology_path: "ontology.yaml" # Add this to specify the path to the ontology file
        - sample content of ontology.yaml:
            order:
            - 1: "first"
            - 2: "second"
            - 3: "third"
            - end: "last"

            voice:
            - S: "soprano"
            - A: "alto"
            - T: "tenor"
            - B: "bass"

- load the tsv file with meta-questions (as it was previously in the step 1), with focus on the following fields:
    - meta-question_id
    - skill
    - text_with_wildcards (e.g., "What is the scientific pitch notation of the {order} {voice} note in the provided excerpt?")
    - question_keys (e.g. ["order", "voice"])

- for each unique skill, generate the desired number of question instances (as configured in questions_per_skill_count):
    - iteratively sample a random meta-question corresponding to the given skill, until the desired number is reached
    - for the meta-question, sample the values for the specified variables, from the allowed values as described in the
      ontology.yaml
        - e.g., for the question in the example, we may sample "voice": "S", and "order": 1.
    - create a `values` dict with the selected values (e.g. {"voice": "S", "order": 1}) - save to field `values`
    - replace the wildcards in the `text_with_wildcards` with the values from ontology yaml file to get the question text - save to field `question` (e.g., "What is the scientific pitch notation of the first soprano note in the provided excerpt?")
- so the new data will contain `questions_per_skill_count` * skill_count items. For each item, copy all the fields that were already in the meta-questions tsv file, and add the fields
- also after the step 0, print the statistics (similarly to other steps) and save as intermediate file
- the data output from step 0 would be the data input for step 1.

Further, adjust the step 1 to not only pass the path to the extraction_func, but also the `values`, because in the new implementation, extraction_func expects `path` and `values` dict.



(Additional)
Further, suggest a way to automatically control the number final benchmark items, such that in cases were full product is created in the original implementation, some kind of random sampling would be performed in the new implementation. This should be again controlled by parameters from generation config.
"""



# TODO:
# This needs to be re-implemented to:
# - use huggingface dataset instead of tsv files for intermediate steps
# - first generate full populated benchmark with all possible options, and after then randomly sample from the full
#   benchmark with desired settings
#       - desired percentage of NOTA-correct questions
#       - desired amount of (question-piece pairs)_per_skill 
# - generating full benchmark means:
#       - no sampling when generating questions from meta-questions
#       - generating NOTA-correct version for every question
# - subsampling at the end is then performed in the following setting:
#       - every question-piece that is selected, is selected in all submodalities
#       - number of question-piece pairs per skill is controlled
#           - but if the desired number exceeds the maximum possible number, the actual amount is kept lower  
#       - for each NOTA-correct version, the NOTA-incorrect question is also sampled
#       - this can be performed with different random seeds and different size settings, to obtain multiple different versions of the benchmark, both of the same size and differing in size


import argparse
import ast
import csv
import datetime
import importlib.util
import json
import os
import numpy as np
import sys
from collections import defaultdict
from pathlib import Path
import yaml
import uuid
import itertools

import math


from utils import load_methods_module

stats = {
    "errors": 0,
    "step_counts": {}
}
from src import ground_truth_and_distractor_pool_extractions

PROJECT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "benchmark-generation")
INTERMEDIATE_DIR = None

def deterministic_uuid(data):
    """Generates a deterministic UUID based on the input data dictionary."""
    normalized = json.dumps(data, sort_keys=True)
    return uuid.uuid5(PROJECT_NAMESPACE, normalized)

def save_intermediate(data, filename, fieldnames):
    filepath = os.path.join(INTERMEDIATE_DIR, filename)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()
        writer.writerows(data)
    stats["step_counts"][filename] = len(data)

def print_checkpoint(step_num, title, filename):
    count = stats["step_counts"].get(filename, 0)
    title_with_brackets = f"[{title}]"
    print(
        f"Step {step_num:>2}  "
        f"{title_with_brackets:<45}  "
        f"Items: {count:>8}  "
        f"Errors: {stats['errors']:>4}"
    )


def step_0_minus_2_load_meta(config):
    """Loads all raw meta-questions from the source file."""
    args = config['cmdline_args']
    with open(args['meta'], 'r', encoding='utf-8') as f_meta:
        meta_questions = list(csv.DictReader(f_meta, delimiter='\t'))
    
    fields = list(meta_questions[0].keys())
    save_intermediate(meta_questions, "00_minus_2_raw_meta.tsv", fields)
    print_checkpoint(-2, "Load Raw Meta", "00_minus_2_raw_meta.tsv")
    return meta_questions, fields

def step_0_minus_1_filter_meta(meta_questions, config, fields):
    """Filters the meta-questions list based on config."""
    if 'allowed_metaq_ids' in config:
        allowed_ids = [str(id) for id in config['allowed_metaq_ids']]
        if len(allowed_ids) > 0:
            meta_questions = [q for q in meta_questions if str(q.get('meta-question_id')) in allowed_ids]

    save_intermediate(meta_questions, "00_minus_1_filtered_meta.tsv", fields)
    print_checkpoint(-1, "Filter Meta", "00_minus_1_filtered_meta.tsv")
    return meta_questions, fields


def step_0_instantiate_questions(meta_questions, config, ontology):
    questions_by_skill = defaultdict(list)
    for q in meta_questions:
        questions_by_skill[q['skill']].append(q)

    output_data = []
    
    for skill, questions in questions_by_skill.items():
        for meta_q in questions:
            try:
                var_names = ast.literal_eval(meta_q.get('question_keys', '[]'))
            except (ValueError, SyntaxError):
                var_names = []

            # 1. Prepare lists for each variable based on the ontology
            variable_options = []
            ordered_keys = []
            
            for v in var_names:
                if v in ontology:
                    ordered_keys.append(v)
                    # We create a list of (key, word) tuples for each variable
                    options = [(list(entry.keys())[0], list(entry.values())[0]) for entry in ontology[v]]
                    variable_options.append(options)
            
            # 2. Use itertools.product to generate every combination
            for combination in itertools.product(*variable_options):
                keys_dict = {}
                words_dict = {}
                
                for i, (k, word) in enumerate(combination):
                    v_name = ordered_keys[i]
                    keys_dict[v_name] = k
                    words_dict[v_name] = word

                # 3. Create the row
                row = dict(meta_q)
                row['values'] = json.dumps(keys_dict)
                try:
                    row['question'] = meta_q['text_with_wildcards'].format(**words_dict)
                except KeyError:
                    row['question'] = meta_q['text_with_wildcards']
                
                output_data.append(row)

    fields = list(meta_questions[0].keys()) + ['values', 'question']
    save_intermediate(output_data, "00_benchmark_step0_instantiated_questions.tsv", fields)
    print_checkpoint(0, "Instantiate Questions", "00_benchmark_step0_instantiated_questions.tsv")
    # save_intermediate and print_checkpoint logic remains the same
    return output_data, fields


def step_1_generate_product(meta_questions, config, fields):
    """Generates the product of meta-questions and pieces."""
    args = config['cmdline_args']
    
    with open(args['pieces'], 'r', encoding='utf-8') as f_pieces:
        pieces = list(csv.DictReader(f_pieces, delimiter='\t'))

    output_data = []
    
    for meta in meta_questions:        
        for piece in pieces:
            row = {**meta, **piece}
            output_data.append(row)

    # Combination of original fields from meta-questions and pieces, without duplicates
    out_fields = fields + list(pieces[0].keys())

    # Deduplicate fields in case of identical column names (though unlikely to overlap destructively)
    out_fields = list(dict.fromkeys(out_fields))

    save_intermediate(output_data, "01_benchmark_step1_product.tsv", out_fields)
    print_checkpoint(1, "Product & Extraction", "01_benchmark_step1_product.tsv")
    return output_data, out_fields

def step_1_5_extract_ground_truth_and_distractors(data, config, fields):
    """For each question-piece pair, extracts the ground truth answer and distractor pool using the specified method."""

    #methods_module = load_methods_module(args['methods_path'])
    AnswerDistractorExtractors = ground_truth_and_distractor_pool_extractions.AnswerDistractorExtractors(config)

    output_data = []
    
    for row in data:
        method_name = row['method_for_ground_truth_extraction'] 
        method_func = getattr(AnswerDistractorExtractors, method_name)

        # Parse values dict safely
        if not hasattr(AnswerDistractorExtractors, method_name):
            print(f"Error: Method '{method_name}' not found.")

            stats["errors"] += 1
            continue

        values_dict = json.loads(row['values']) if row.get('values') else {}
        
        # try:
        ground_truth, distractor_pool, values_dict, new_values_word = AnswerDistractorExtractors.extract_answer_and_distractors(method_func, row['path'], values_dict)
        if ground_truth is None:
            print(f"Warning: Ground truth extraction returned None for item (meta-qid: {row.get('meta-question_id', 'Unknown')}). This item will be skipped.")
            stats["errors"] += 1
            continue
        row['values']  = json.dumps(new_values_word)
        row['question'] = row['text_with_wildcards'].format(**{**values_dict, **new_values_word})
        
        if distractor_pool is not None:
            row['ground_truth'] = str(ground_truth)
            distractor_pool = [str(d) for d in distractor_pool]
            row['distractor_pool'] = json.dumps(distractor_pool)
            output_data.append(row)
            # print(row)
            # print(new_values_dict)
        # except Exception as e:
        #     print(f"Error on Q '{row.get('meta-question_id', '')}' / Piece '{row.get('piece_id', '')}': {e}")
        #     stats["errors"] += 1

    out_fields = fields + ['ground_truth', 'distractor_pool']
    # Deduplicate fields in case of identical column names (though unlikely to overlap destructively)
    out_fields = list(dict.fromkeys(out_fields))

    save_intermediate(output_data, "01_5_benchmark_step1.5_extraction.tsv", out_fields)
    print_checkpoint(1.5, "Ground Truth & Distractor Extraction", "01_5_benchmark_step1.5_extraction.tsv")
    return output_data, out_fields


def step_2_sort_distractors(data, config, fields):
    out_fields = fields + ['sorted_distractors']
    method_name = config.get('sorting_method')
    methods_path = config.get('sorting_methods_path')

    if not method_name or not methods_path:
        print("Error: 'sorting_method' or 'sorting_methods_path' missing in config.")
        stats["errors"] += 1
        return data, out_fields

    try:
        sorting_module = load_methods_module(methods_path)
        if not hasattr(sorting_module, method_name):
            raise AttributeError(f"Method '{method_name}' not found in '{methods_path}'")
        sort_func = getattr(sorting_module, method_name)
    except Exception as e:
        print(f"Error loading sorting method: {e}")
        stats["errors"] += 1
        return data, out_fields

    for row in data:
        pool = json.loads(row['distractor_pool'])
        try:
            sorted_pool = sort_func(distractors=pool, row=row, rng=config['rng'])
            row['sorted_distractors'] = json.dumps(sorted_pool)
        except Exception as e:
            print(f"Error sorting distractors for item: {e}")
            stats["errors"] += 1
            row['sorted_distractors'] = json.dumps(pool)
    
    save_intermediate(data, "02_benchmark_distractors_sorted.tsv", out_fields)
    print_checkpoint(2, "Sort Distractors", "02_benchmark_distractors_sorted.tsv")
    return data, out_fields

def step_1_7_remove_duplicates(data, config, fields):
    """Removes duplicate questions based on question text and piece path."""
    seen = set()
    unique_data = []
    for row in data:
        identifier = (row['question'], row['path'])
        if identifier not in seen:
            seen.add(identifier)
            unique_data.append(row)

    save_intermediate(unique_data, "01_7_benchmark_deduplicated.tsv", fields)
    print_checkpoint(1.7, "Remove Duplicates", "01_7_benchmark_deduplicated.tsv")
    return unique_data, fields

def step_1_4_subsample(data, config, fields):
    """
    Subsamples the benchmark data to ensure a target count per subcategory,
    balanced by meta-question_id.

    Logic:
    1. Initially calculates an even distribution of items across all unique 
       `meta-question_id` groups within each subcategory to reach `q_count`.
    2. If `allow_meta_question_backoff` is True:
       - The method enters an iterative balancing loop. 
       - If a meta-question has fewer items available than its allocated target, 
         it locks its target to the available count (the "backoff").
       - The resulting deficit is redistributed across other meta-questions 
         within the same subcategory that possess a surplus of items.
       - This process repeats until all items are distributed or no meta-questions 
         remain with a surplus of items to "absorb" the deficit.
    3. The method ensures no over-sampling by capping requests at the 
       available population size.

    Args:
        data: List of dictionary records containing 'subcategory' and 'meta-question_id'.
        config: Configuration dict containing:
            - 'questions_per_subcategory_count' (int): Target total items per subcategory.
            - 'allow_meta_question_backoff' (bool): Whether to redistribute deficits.
        fields: Metadata fields to pass through during saving.

    Returns:
        tuple: (out_data, fields)
    """

    q_count = config.get('questions_per_subcategory_count', 10)
    allow_backoff = config.get('allow_meta_question_backoff', True)

    hierarchy = defaultdict(lambda: defaultdict(list))
    for q in data:
        hierarchy[q['subcategory']][q['meta-question_id']].append(q)

    out_data = []

    for subcategory, meta_groups in hierarchy.items():
        # Calculate total available in this subcategory to check against q_count
        total_available_in_sub = sum(len(items) for items in meta_groups.values())
        if total_available_in_sub < q_count:
            print(f"Warning: Subcategory '{subcategory}' has a total of {total_available_in_sub} "
                  f"items, which is less than the requested {q_count}. Using all available items.\n"
                  f"You may try setting `use_all_inds` to true in config, which may increase the number of generated items per meta-question.")

        meta_ids = list(meta_groups.keys())
        # Initial targets
        base, remainder = divmod(q_count, len(meta_ids))

        # target is the target count of items sampled from a given meta-question
        targets = {m_id: base + (1 if i < remainder else 0) for i, m_id in enumerate(meta_ids)}
        
        if allow_backoff:
            while True:
                deficit = 0
                # Identify which meta-questions are maxed out/short
                for m_id in meta_ids:
                    available = len(meta_groups[m_id])
                    if targets[m_id] > available:
                        deficit += (targets[m_id] - available)
                        print(f"Warning: Meta-question '{m_id}' (subcategory {subcategory}) has insufficient items (has {available}, requested {targets[m_id]}). "
                              f"Will try to redistribute the remaining {deficit} items across other meta-questions from the subcategory.")
                        targets[m_id] = available
                
                # Find meta-questions that can actually take more items
                candidates = [m for m in meta_ids if len(meta_groups[m]) > targets[m]]
                
                if deficit > 0 and candidates:
                    # print(f"Warning: Subcategory '{subcategory}' has insufficient items. "
                    #       f"Redistributing {deficit} items.")
                    
                    # Distribute deficit among candidates
                    share = deficit // len(candidates)
                    extra = deficit % len(candidates)
                    for i, m_id in enumerate(candidates):
                        targets[m_id] += share + (1 if i < extra else 0)
                else:
                    # Break if no deficit or no more room to distribute
                    break

        # Extraction
        for m_id, target in targets.items():
            pool = meta_groups[m_id]
            if len(pool) < target and not allow_backoff and total_available_in_sub >= q_count:
                print(f"Warning: Meta-question '{m_id}' (subcategory {subcategory}) has insufficient items (has {len(pool)}, requested {target})."
                      f"This will lead to lower number of questions per subcategory than requested ({q_count})."
                      f"If you allow backoff (`allow_meta_question_backoff: true` in config), will try to achieve the desired number by using other meta-questions from the subcategory.")
            out_data.extend(config['rng'].choice(pool, min(len(pool), target), replace=False))

    save_intermediate(out_data, "01_4_benchmark_subsampled.tsv", fields)
    print_checkpoint(1.4, "Subsample Benchmark", "01_4_benchmark_subsampled.tsv")
    return out_data, fields

def is_submodality_part_of_modality(submodality, modality):
    return modality in submodality

def modality_from_submodality(submodality):
    if "audio" in submodality:
        return "audio"
    if "visual" in submodality:
        return "visual"
    if "symbolic" in submodality:
        return "symbolic"
    return "UNDEFINED_MODALITY"

def step_3_submodalities(data, config, fields):
    out_fields = fields + ['modality', 'submodality', 'path_to_question_context_file']
    out_data = []
    for row in data:
        question_modalities = row.get('modality_in_question', '').split(',')
        
        for sub in config.get('submodalities', []):
            if any(is_submodality_part_of_modality(sub, mod) for mod in question_modalities):
                new_row = dict(row)
                new_row['modality'] = modality_from_submodality(sub)
                new_row['submodality'] = sub
                new_row['path_to_question_context_file'] = os.path.join(row['path'], sub)
                out_data.append(new_row)

    save_intermediate(out_data, "03_benchmark_with_submodalities.tsv", out_fields)
    print_checkpoint(3, "Submodalities Product", "03_benchmark_with_submodalities.tsv")
    return out_data, out_fields

def step_4_final_options(data, config, fields):
    out_fields = fields + ['final_correct_option', 'final_options', 'random_guess_performance_accuracy', 'is_nota_correct']
    num_opt = config['num_options']
    nota_text = config['nota_text']
    add_nota = config['add_nota']

    for row in data:
        distractors = json.loads(row['sorted_distractors'])
        gt = row['ground_truth']
        
        options = [gt]
        if add_nota:
            options.append(nota_text)
            distractors_needed = num_opt - 2
        else:
            distractors_needed = num_opt - 1
            
        options.extend(distractors[:distractors_needed])

        if len(options) < num_opt:
            print(f"Warning: Not enough distractors for item (meta-qid: {row.get('meta-question_id', 'Unknown')}). Needed {num_opt - 1} distractors, but only {len(distractors)} available.")
            stats["errors"] += 1
        
        row['final_correct_option'] = gt
        row['final_options'] = json.dumps(options)
        row['random_guess_performance_accuracy'] = 1.0 / len(options) if options else 0.0
        row['is_nota_correct'] = 0

    save_intermediate(data, "04_benchmark_with_final_options.tsv", out_fields)
    print_checkpoint(4, "Generate Initial Final Options", "04_benchmark_with_final_options.tsv")
    return data, out_fields

def step_5_nota_correct(data, config, fields):
    T = config.get('nota_correct_percentage', 0.0)
    out_data = []

    if T > 0:
        N = config['num_options']
        nota_text = config['nota_text']

        # 1) Determine number of items to select
        expected_count = round(len(data) * T)

        # 2) Select items in a single step
        all_indices = list(range(len(data)))
        selected_indices = set(config['rng'].choice(
            all_indices, expected_count, replace=False
        ))

        # 3) Iterate through all rows, replacing selected ones with derived rows
        for idx, row in enumerate(data):
            new_row = dict(row)

            if idx in selected_indices:
                distractors = json.loads(row['sorted_distractors'])
                options = [nota_text] + distractors[:N-1]
                new_row['final_correct_option'] = nota_text
                new_row['final_options'] = json.dumps(options)
                new_row['is_nota_correct'] = 1

            out_data.append(new_row)
    else:
        out_data = data

    save_intermediate(out_data, "05_benchmark_with_NOTA_correct_items_added.tsv", fields)
    print_checkpoint(5, "Add NOTA-correct items", "05_benchmark_with_NOTA_correct_items_added.tsv")
    return out_data, fields

def step_6_formatting(data, config, fields):
    """Shuffle options randomly, add labels."""
    out_fields = ['item_id'] + fields + ['all_choices', 'index2ans', 'labeled_final_options', 'labeled_final_correct_option', 'label_of_final_correct_option']
    labels = config['labels']
    
    for row in data:
        options = json.loads(row['final_options'])
        correct_opt = row['final_correct_option']
        
        # print(options)

        options.sort()
        config['rng'].shuffle(options)
        
        all_choices = labels[:len(options)]
        index2ans = {}
        labeled_final_options = []
        labeled_correct = None
        
        for i, opt in enumerate(options):
            label = all_choices[i]
            index2ans[label] = opt
            labeled_final_options.append(f"({label}) {opt}")
            if opt == correct_opt:
                labeled_correct = label
                
        row['all_choices'] = json.dumps(all_choices)
        row['index2ans'] = json.dumps(index2ans)
        row['labeled_final_options'] = json.dumps(labeled_final_options)
        row['labeled_final_correct_option'] = f"({labeled_correct}) {correct_opt}"
        row['label_of_final_correct_option'] = labeled_correct

        row['item_id'] = str(deterministic_uuid(row))

    save_intermediate(data, "06_benchmark_with_labeled_sorted_final_options.tsv", out_fields)
    print_checkpoint(6, "Labels & Sorting Options", "06_benchmark_with_labeled_sorted_final_options.tsv")
    return data, out_fields

def step_7_final_save(data, config, fields):
    out_path = config['cmdline_args']['output']
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t')
        writer.writeheader()
        writer.writerows(data)
    print(f"\nStep 7 [Final Save] complete. File saved to: {out_path}")

from collections import Counter

def print_formatted_statistics(data, fields, filters=None):
    """
    Prints distribution stats with optional filtering.
    
    :param filters: dict where keys are field names and values are 
                    either a single allowed value or a list/set of values.
    """
    # 1. Apply filtering logic
    filtered_data = data
    if filters:
        filtered_data = [
            row for row in data 
            if all(
                row.get(f) == val if not isinstance(val, (list, tuple, set)) 
                else row.get(f) in val 
                for f, val in filters.items()
            )
        ]
    
    total_items = len(filtered_data)
    if total_items == 0:
        print("No items found matching the filter criteria.")
        return

    print(f"\n{'='*55}")
    print(f"{'FIELD DISTRIBUTION STATISTICS':^55}")
    if filters:
        print(f"{f'Filtered by: {filters}':^55}")
    print(f"{'='*55}")
    print(f"Total Items in Subset: {total_items}\n")

    for field in fields:
        print(f"--- Field: {field} ---")
        counts = Counter(str(row.get(field, "N/A")) for row in filtered_data)
        
        max_key_len = max((len(k) for k in counts.keys()), default=0)
        
        for value, count in counts.most_common():
            percent = (count / total_items) * 100
            print(f"{value:<{max_key_len}} : {count:>6} items ({percent:>6.2f}%)")
        print() 
    
    print(f"{'='*55}")

def step_1_8_remove_items_with_ground_truth_0(data, config, fields):
    """Removes a given percentage of items where ground truth is 0."""
    percentage_to_remove = config.get('percentage_gt_zero_to_remove', 0.0)

    if percentage_to_remove > 0:
        # First decide how many items to remove
        # then, randomly select the indiced of items to be removed
        # and then remove the items based on the selected indices
        gt_zero_indices = [i for i, row in enumerate(data) if str(row.get('ground_truth')) == '0']
        num_to_remove = round(len(gt_zero_indices) * percentage_to_remove)
        indices_to_remove = set(config['rng'].choice(gt_zero_indices, num_to_remove, replace=False))
        out_data = [row for i, row in enumerate(data) if i not in indices_to_remove]
    else:
        out_data = data

    save_intermediate(out_data, "01_8_benchmark_no_gt_zero.tsv", fields)
    print_checkpoint(1.8, f"Remove some ({percentage_to_remove*100:.2f}%) of GT=0 items", "01_8_benchmark_no_gt_zero.tsv")
    return out_data, fields

def main():
    parser = argparse.ArgumentParser(description="Benchmark Generator Pipeline")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--benchmark_file", help="Path to benchmark to be generated (overrides config)")
    parser.add_argument("--submodalities", nargs='+', help="Override submodalities filter in config")
    parser.add_argument("--questions_per_subcategory_count", type=int, help="Override questions per subcategory count for subsampling")
    parser.add_argument("--seed", type=int, help="Override random seed for reproducibility")
    parser.add_argument("--allowed_metaq_ids", nargs='+', help="Override allowed metaq ids in config")
    parser.add_argument("--use_all_inds", default=False, action="store_true", help="Override `use_all_inds` setting from config.")
    parser.add_argument("--path_to_pregenerated_full_benchmark_file", default=None, help="Potentially existing file with a pre-generated full benchmark file.")
    parser.add_argument("--use_pregenerated_benchmark_file", default=False, action="store_true", help="Use the file specified above.")
    

    args = parser.parse_args()

    # Step 0 loading
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)

    if args.benchmark_file:
        config['cmdline_args']['output'] = args.benchmark_file
    if args.submodalities:
        config['submodalities'] = args.submodalities
    if args.questions_per_subcategory_count is not None:
        config['questions_per_subcategory_count'] = args.questions_per_subcategory_count
    if args.seed is not None:
        config['seed'] = args.seed
    if args.allowed_metaq_ids is not None:
        config['allowed_metaq_ids'] = args.allowed_metaq_ids
    if args.use_all_inds:
        config['use_all_inds'] = True

    global INTERMEDIATE_DIR
    INTERMEDIATE_DIR = "logs/intermediate_benchmarks/" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        
    # random.seed(config.get('seed', 42))
    # np.random.seed(config.get('seed', 42))

    # For reproducibility, create a numpy random generator and save it to config to be used in random sampling, shuffling and decisions
    rng = np.random.default_rng(config.get('seed', 42)) # to use for seed choice generate: rng.choice(list) / tested
    config['rng'] = rng
    
    os.makedirs(INTERMEDIATE_DIR, exist_ok=True)

        # 2. Save modified config to log directory
    with open(os.path.join(INTERMEDIATE_DIR, "config_snapshot.yaml"), 'w') as f:
        yaml.dump(config, f)


    # Pipeline Execution
    print("--- Starting Pipeline ---")

    # is it strange that the AnswerQG is instantiated but not used after that?
    # NO! It creates the whole ontology that is then used in the step 0 for question instantiation, and also the methods that are used for ground truth and distractor extraction in step 1.5 are methods of this class, so it needs to be instantiated before step 0 and step 1.5
    AnswerQuestionGenerator = ground_truth_and_distractor_pool_extractions.AnswerDistractorExtractors(config)
    ontology = AnswerQuestionGenerator.ontology

    # TODO: if the args.path_to_pregenerated_full_benchmark_file file exists and if we should use it, load it here and let the fields be the fields in the tsv
    if (
        args.use_pregenerated_benchmark_file
        and args.path_to_pregenerated_full_benchmark_file is not None
        and os.path.exists(args.path_to_pregenerated_full_benchmark_file)
    ):
        print(f"--- Loading pre-generated full benchmark from: {args.path_to_pregenerated_full_benchmark_file} ---")
        with open(args.path_to_pregenerated_full_benchmark_file, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            fields = reader.fieldnames
            data = [row for row in reader]
        print(f"Loaded {len(data)} rows with fields: {fields}")
    else:
        # 1. Load raw meta-questions
        raw_meta, meta_fields = step_0_minus_2_load_meta(config)
        
        # 2. Filter out meta questions based on config (e.g., by allowed meta-question ids)
        filtered_meta, meta_fields = step_0_minus_1_filter_meta(raw_meta, config, meta_fields)

        # 3. Instantiate questions from meta-questions by replacing wildcards with values from the ontology, and save the instantiated question text in a new column `question`.
        data, fields = step_0_instantiate_questions(filtered_meta, config, ontology)
        
        # 4. Generate the product of meta-questions and pieces, and compute the ground truth and distractor pool for each question-piece pair using the methods specified in the meta-questions file.
        data, fields = step_1_generate_product(data, config, fields)

        
        # 6. For each question-piece pair, extract the ground truth answer and distractor pool using the specified method, and save them in new columns `ground_truth` and `distractor_pool`. The distractor pool should be saved as a JSON string (list of distractors).
        data, fields = step_1_5_extract_ground_truth_and_distractors(data, config, fields)

        
        # If a path for the pre-generated benchmark was specified but the file didn't exist yet,
        # save the freshly generated benchmark there for future reuse.
        if args.path_to_pregenerated_full_benchmark_file is not None:
            pregenerated_dir = os.path.dirname(args.path_to_pregenerated_full_benchmark_file)
            if pregenerated_dir:
                os.makedirs(pregenerated_dir, exist_ok=True)
            print(f"--- Saving generated full benchmark to: {args.path_to_pregenerated_full_benchmark_file} ---")
            with open(args.path_to_pregenerated_full_benchmark_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fields, delimiter='\t')
                writer.writeheader()
                writer.writerows(data)
            print(f"Saved {len(data)} rows.")



    # 7. Remove duplicates based on question text and piece path, to ensure that each question-piece pair is unique in the benchmark.
    # (duplicates are possible in case when we have "use_all_inds" set to true in config, then for the questions of type
    # "what is in the {order} {voice} note in the provided excerpt?" (e.g. "what is the 2nd soprano note"),
    # we regenerate the actual values (e.g. "2nd" and "soprano") for each question-piece pair during the
    # distractor-ground truth extraction, depending on the actual length of the piece
    data, fields = step_1_7_remove_duplicates(data, config, fields)


    data, fields = step_1_8_remove_items_with_ground_truth_0(data, config, fields)

    # 5. Subsample the benchmark to include a maximum of `questions_per_subcategory_count` items for each subcategory if instructed by the config (this is to control the size of the benchmark, and to ensure diversity across different subcategories). 
    data, fields = step_1_4_subsample(data, config, fields)    


    # 8. Apply a method as specified in the config to sort the distractor pool for each question-piece pair (with preliminary dummy implementation of the method that just shuffles the distractor pool, to be replaced later with a real implementation). This method should be applied to each question-piece pair in the benchmark generated in step 1, the distractors sorted should be added to a new column "sorted_distractors" and the output should be saved in an intermediate benchmark file named "benchmark_distractors_sorted.tsv".
    data, fields = step_2_sort_distractors(data, config, fields)
    
    # 9. Generate a product of the benchmark from the 2. step with the list of submodalities specified in the config
    #    (excluding submodalities that are not part of any modality that is supported for the given question, as
    #    specified in `modality_in_question` column in the meta-questions file), adding the submodality name as a new
    #    column "submodality", and the column "path_to_question_context_file", which would be the concatenation of the
    #    piece directory (column "path" from the pieces file, e.g. pieces-chorale-bricks.tsv) and the submodality name.
    # The same question-piece pair is used for all submodalities to allow comparsion
    data, fields = step_3_submodalities(data, config, fields)

    # 10. For each question-piece-submodality triplet, generate the final options to be included in the benchmark:
    #     - if NOTA is to be included, take it (the text specified in config) as one of the options,
    #     - take the ground truth as one of the options,
    #     - and take the desired number of remaining options from the sorted distractor pool, in order of difficulty
    #       (e.g., if the desired number of options is 5 and both NOTA and ground truth are included, take the top 3 most difficult distractors from the sorted distractor pool, and if NOTA is not included, take the top 4 most difficult distractors from the sorted distractor pool).
    #     - add the ground truth to a new column "final_correct_option"
    data, fields = step_4_final_options(data, config, fields)

    # 11. Add questions where ground-truth is excluded from the options (NOTA is correct answer) - only if the percentage of such desired questions is non-zero:
    data, fields = step_5_nota_correct(data, config, fields)
    
    # 12. Format the options and question.
    data, fields = step_6_formatting(data, config, fields)
    step_7_final_save(data, config, fields)

    # Final Statistics
    total_items = len(data)
    nota_correct_count = sum(1 for row in data if row.get('final_correct_option') == config.get('nota_text', 'None of the above'))
    nota_percent = (nota_correct_count / total_items * 100) if total_items > 0 else 0

    selected_fields = ["meta-question_id", "subcategory", "skill", "piece_id", "submodality", "specification"]

    # print("\n--- NOTA-incorrect items ---")
    print_formatted_statistics(data, selected_fields, filters={"is_nota_correct": 0})
    # print("--------------------------------")

    # print("\n--- NOTA-correct items ---")
    print_formatted_statistics(data, selected_fields, filters={"is_nota_correct": 1})
    # print("--------------------------------")


    # print("\n--- ALL DATA ---")
    print_formatted_statistics(data, selected_fields)
    # print("--------------------------------")

    print("\n--- Final Statistics ---")
    print(f"Total Benchmark Items : {total_items}")
    print(f"NOTA Correct Items    : {nota_correct_count} ({nota_percent:.2f}%)")
    print(f"Total Errors Recorded : {stats['errors']}")
    print("--------------------------------")


if __name__ == "__main__":
    main()