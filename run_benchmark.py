# Copyright (C) 2026  Tomáš Sourada, Katia Vendrame, Jan Hajič, jr.
#
# This file is part of the MusICA MetaBench source code, licensed under
# the GNU General Public License v3.0 or later (SPDX: GPL-3.0-or-later).
# See the LICENSE-SOURCE-CODE file in the repository root for the full
# license text, or <https://www.gnu.org/licenses/>.

"""
To run:
.venv/bin/python3 run_benchmark.py --config eval-config.yaml



Prompt used to generate the script, which tells precisely what the script does.

Generate the python script with functionality as described below, using the code snippets provided. When the snippets
need refactoring, do it to achieve better structure.
Also generate a sample config yaml file.

This script gets a config file and runs LLM(s) on the benchmark questions.

It should:
- load the config yaml file, specified by a cmdline arg:
    - list of models to be run
        - model = "openai/gpt-4.1-nano"
    - API endpoint to be used
        - url: str = "https://openrouter.ai/api/v1/chat/completions"
    - env var name with API KEY
    - system prompt
    - user prompt template
    - path to extraction methods file
    - name of the extraction method to be used  
    - dry_run: bool = False # if True, do not send any requests
    - user_prompt_template = "You are a specialist in the analysis and interpretation of musical materials. You are provided with a musical work as <FORMAT>. Analyze the material carefully. Then, given a question and a set of possible answers, choose the most appropriate option.
Question:
<QUESTION>
Options:
<OPTIONS_TEXT>

<POTENTIAL_TEXTFILE_PLACEHOLDER>

After any potential reasoning, end with your final answer in this format:
Final Answer: <answer>
where <answer> is the single correct letter choice <OPTION_LABELS>. Only include the letter."

    - musical_piece_format_info = {
        "audio": {"wav": "an audio recording (WAV format)"},
        "visual": {"png": "a rendered score (PNG format)",
                   "pdf": "a rendered score (PDF format)"},
        "symbolic": {"musicxml": "a musical score (MusicXML format)",
                     "midi": "a musical score (MIDI format represented as CSV)", 
                     "abc": "a musical score (ABC notation format)"
                     }
    }

    # for automatic logging to Google Sheets
    - log_to_google_sheet = True
    - sheet_id = "1cYg3U_MPDx1fzLNnWnR9Xg2epi2eaUA_4JF5Bo8Xbro"
    - sheet_name = "List 1"
    - credentials_location = "logs/protobenchmark-logging-aa9418338494.json"
- set the logdir, using the set_logdir method
- load the benchmark file (tsv), as specified in the config: config['cmdline_args']['output']
    - the relevant columns from the benchmark file are: 
        - item_id (unique)
        - question
        - labeled_final_options (e.g., ["(A) G4", "(B) F4", "(C) none of the other options is correct", "(D) B4", "(E) E4"])
        - label_of_final_correct_option: the label of the final correct option
        - path_to_question_context_file
        - submodality
        - modality
- print the stats of the file and of the other setup (number of items, questions to be asked)
- for every (model, benchmark-item) pair:
    - prepare the user prompt, using the template from config, the question and the labeled final options, prepare the
      context file (path_to_question_context_file)
    - run the request to the LLM API, using the code snippet from below (please note that the snippet needs to be
      modified, as it uses benchmarkItem and config dataclass that do not exist), and return the following:
        - price, time_taken, full_json_response, response (extracted from the json), full_prompt
    - run the extraction of the selected option from the model response, using the method specified in the config
      (provide a dummy implementation for this for now)
    - check whether the extracted answer is a correct answer
    - prepare a single-row log:
      full-original-row (whole benchmark row), plus: datetime  full_prompt parameters  model   full_json_response  extracted_response (only the
      response)  config_info label_of_answer answer  price   time_taken  correct?
    - log it to a tsv file for this run of the benchmark
    - if logging to google sheet is set up in config, log it using the append row to google sheet method
    - print a concise log to cmdline, in order for me to know what is happening
"""


import argparse
import csv
import datetime
import json
import os
import re
import sys
import time
import uuid
import random
import select
import shutil
from typing import Dict, Tuple
import numpy as np

import requests
import yaml

from utils import load_methods_module, append_to_google_sheet, encode_file_to_base64, upload_tsv_to_gsheet, create_gsheet_tabs
from eval import evaluate_results


# =========================================================================
# Utilities and Helper Functions
# =========================================================================

API_KEY = None

PROJECT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "benchmark-run")

def deterministic_uuid(data):
    """Generates a deterministic UUID based on the input data dictionary."""
    normalized = json.dumps(data, sort_keys=True)
    return uuid.uuid5(PROJECT_NAMESPACE, normalized)


def random_uuid():
    """Generates a random UUID."""
    return uuid.uuid4()


def set_logdir(config: dict) -> str:
    """Sets up a unique logging directory based on the run."""
    dt_string = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    base_log_dir = config.get("logdir", "logs")
    
    unique_logdir = os.path.join(base_log_dir, f"run_{dt_string}_{config.get('benchmark_run_uuid', '')}")
    os.makedirs(unique_logdir, exist_ok=True)
    return unique_logdir



# =========================================================================
# Core LLM Call & Payload Builder
# =========================================================================

def apply_prompt_caching(content: list, ttl: str = None, file_first: bool = False):
    """Adds a cache breakpoint to the user message content (question, then any attached file), in place."""
    cache_control = {"type": "ephemeral"}
    if ttl:
        cache_control["ttl"] = ttl

    question, *attachment = content
    if file_first and attachment:
        # Docs only describe breakpoints on text blocks, so a fixed one follows the file
        content[:] = [*attachment, {"type": "text", "text": "End of attached material.", "cache_control": cache_control}, question]
    else:
        question["cache_control"] = cache_control


def prepare_llm_payload(model: str, user_prompt: str, system_prompt: str, content_file: str, modality: str, submodality: str, no_content_file: bool = False, zdr: bool = True, inference_seed: int = None, prompt_caching: dict = None) -> Tuple[Dict, str]:
    """Generates the messages payload based on the modality and files."""
    messages = []
    plugins = None
    
    user_prompt_clean = user_prompt.replace("<POTENTIAL_TEXTFILE_PLACEHOLDER>", "").strip()

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if no_content_file:
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": user_prompt_clean}]
        })
    else:
        if modality == "visual" and submodality.endswith(".png"):
            base64_image = encode_file_to_base64(content_file)
            data_url = f"data:image/png;base64,{base64_image}"
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_clean},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            })
            
        elif modality == "visual" and submodality.endswith(".pdf"): 
            base64_pdf = encode_file_to_base64(content_file)
            data_url = f"data:application/pdf;base64,{base64_pdf}"
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_clean},
                    {"type": "file", "file": {"filename": "document.pdf", "file_data": data_url}},
                ]
            })
            plugins = [{"id": "file-parser", "pdf": {"engine": "native"}}]
            
        elif modality == "audio":
            base64_audio = encode_file_to_base64(content_file)
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_clean},
                    {"type": "input_audio", "input_audio": {"data": base64_audio, "format": "wav"}}
                ]
            })
            
        elif modality == "symbolic":
            try:
                with open(content_file, 'r', encoding="utf-8", errors="replace") as f:
                    file_content = f.read()
            except FileNotFoundError:
                file_content = "[FILE NOT FOUND]"
                
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_clean},
                    {"type": "text", "text": f"--- Attached Symbolic Data ---\n{file_content}"}
                ]
            })
            
        else:
            messages.append({
                "role": "user",
                "content": [{"type": "text", "text": user_prompt_clean}]
            }) 

    prompt_caching = prompt_caching or {}
    if prompt_caching.get("enabled", True):
        apply_prompt_caching(messages[-1]["content"], prompt_caching.get("ttl"), prompt_caching.get("file_first", False))

    payload = {
        "model": model,
        "messages": messages,
        "provider": { 
             "require_parameters": True,
             "zdr": zdr,
             "data_collection": "deny",
        }
    }
    if plugins:
        payload["plugins"] = plugins
    
    # Add seed if provided and not None
    if inference_seed is not None:
        payload["seed"] = int(inference_seed)

        
    return payload, user_prompt_clean


def ask_model(config: dict, payload: dict, original_user_prompt: str, dry_run: bool = False) -> Tuple[float, float, dict, str]:
    """Runs the API request and returns (price, time_taken, full_json_response, response_text)."""
    start_time = datetime.datetime.now()
    url = config['url']
    headers = {
        "Authorization": f"Bearer {os.environ.get(config['env_api_key_name'], '')}",
        "Content-Type": "application/json"
    }

    if dry_run:
        time_taken = (datetime.datetime.now() - start_time).total_seconds()
        dummy_json = {"choices": [{"message": {"content": "Dry run response. Final Answer: A"}}], "usage": {"cost": 0.0}}
        return 0.0, time_taken, dummy_json, dummy_json['choices'][0]['message']['content']

    max_waiting_time = config.get("max_waiting_time_per_request", 10)
    response_json = call_api_with_backoff(url, headers, payload, max_waiting_time=max_waiting_time, error_log_path=config.get('api_error_log'))
    
    # print(response_json)

    end_time = datetime.datetime.now()
    time_taken = (end_time - start_time).total_seconds()
    
    response_text = response_json.get('choices', [{}])[0].get('message', {}).get('content', 'ERROR')
    cost = float(response_json.get('usage', {}).get('cost', 0.0))
    
    return cost, time_taken, response_json, response_text


def format_api_error(response: requests.Response) -> str:
    """Returns the full API error (message, code, metadata), or the raw body if it is not JSON."""
    try:
        body = response.json()
    except ValueError:
        return response.text
    return json.dumps(body.get("error", body) if isinstance(body, dict) else body, ensure_ascii=False)


def report_api_error(message: str, log_path: str = None):
    """Prints an API error and appends it to the run's error log."""
    print(message)
    if log_path:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.datetime.now().isoformat()} {message}\n")


def call_api_with_backoff(url, headers, payload, max_waiting_time=300, error_log_path=None):
    """Calls an API with exponential backoff and jitter."""
    start_time = time.time()
    base_delay = 1  
    attempt = 0

    response = None
    model = payload.get('model')

    errors = []
    
    while time.time() - start_time < max_waiting_time:
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=max_waiting_time)
            # print(json.dumps(response.json(), indent=2))
            response.raise_for_status()
            response_json = response.json()
            # OpenRouter can report a failure in the body of an HTTP 200 response
            if "error" in response_json:
                report_api_error(f"API error for {model} (HTTP {response.status_code}): {format_api_error(response)}", error_log_path)
            return response_json
            
        except requests.exceptions.RequestException as e:
            # Rather wait for all errors, 429 is "too many requests"

            # if hasattr(e.response, 'status_code') and 400 <= e.response.status_code < 500:
            #     print(f"Fatal error: {e}. Not retrying.")
            #     return {"error": str(e)}

            error = str(e)
            if e.response is not None:
                error += f": {format_api_error(e.response)}"
            errors.append(error)
            report_api_error(f"Error encountered for {model}: {error}", error_log_path)
            
            delay = min(64, base_delay * (2 ** attempt))
            jitter = random.uniform(0, delay)
            
            remaining_time = max_waiting_time - (time.time() - start_time)
            if jitter > remaining_time:
                break
                
            print(f"Retrying in {jitter:.2f}s...")
            time.sleep(jitter)
            attempt += 1

    last_response = format_api_error(response) if response is not None else None
    return {"error": "Max waiting time exceeded.", "original_errors": errors, "last_response": last_response}


def build_item_request(config: dict, model: str, item: dict, seed: int, no_zdr_models: set) -> Tuple[Dict, str, str]:
    """Prepares the request for a (model, benchmark-item) pair. Returns (payload, final_prompt, content_file)."""
    # Prepare User Prompt
    options = json.loads(item['labeled_final_options'])
    labels = json.loads(item['all_choices'])
    options_text = "\n".join(options)

    fmt_info = config['musical_piece_format_info']
    modality = item.get('modality')
    submodality = item.get('submodality')
    format_desc = fmt_info.get(modality, {}).get(submodality, "a musical excerpt")

    print(f"Modality: {modality:>10} | Submodality: {submodality:>19} | Question: {item['question']}")
    print(f"Options: " + ", ".join(options))

    prompt = config['user_prompt_template']
    prompt = prompt.replace("<FORMAT>", format_desc)
    prompt = prompt.replace("<QUESTION>", item['question'])
    prompt = prompt.replace("<OPTIONS_TEXT>", options_text)
    prompt = prompt.replace("<OPTION_LABELS>", ', '.join(labels))

    # Build Payload
    content_file = item['path_to_question_context_file']
    text_only_baseline = config.get('text_only_baseline', False)

    white_noise_baseline = config.get('white_noise_baseline', False)
    if text_only_baseline and white_noise_baseline:
        raise ValueError("Both text_only_baseline and white_noise_baseline cannot be true at the same time. Please choose one baseline or neither.")

    if white_noise_baseline:
        print("White noise baseline is enabled. Replacing content file with white noise.")
        if submodality == "audio.mastermix.wav":
            content_file = "data/white_noise/audio.mastermix.wav"
        elif submodality == "visual.short.png":
            content_file = "data/white_noise/visual.short.png"
        elif submodality == "symbolic.musicxml":
            content_file = "data/white_noise/symbolic.musicxml"
        elif submodality == "symbolic.abc.txt":
            content_file = "data/white_noise/symbolic.abc.txt"
        else:
            raise ValueError(f"No white noise file available for submodality {submodality}. Please check the config or provide a white noise file for this submodality.")

    supported_aggregate_models = config.get("supported_aggregate_models", {})
    if model in supported_aggregate_models:
        print(f"Model {model} is an aggregate model. Using supported aggregate model {supported_aggregate_models[model]} for payload preparation.")
        model_name = supported_aggregate_models[model][modality]
    else:
        model_name = model

    print(f"Running model: #{model_name}#")

    payload, final_prompt = prepare_llm_payload(
        model=model_name, 
        user_prompt=prompt, 
        system_prompt=config['system_prompt'], 
        content_file=content_file, 
        modality=modality, 
        submodality=submodality,
        no_content_file=text_only_baseline,
        zdr=config['zdr'] and model_name not in no_zdr_models,
        inference_seed=seed,
        prompt_caching=config.get('prompt_caching')
    )

    return payload, final_prompt, content_file


def resolve_concrete_models(config: dict, items: list) -> list:
    """Returns the models actually sent to the API, expanding aggregates over the modalities present in items."""
    aggregates = config.get("supported_aggregate_models", {})
    modalities = {item.get('modality') for item in items}
    concrete = set()
    for model in config['models']:
        if model in aggregates:
            concrete.update(aggregates[model][modality] for modality in modalities)
        else:
            concrete.add(model)
    return sorted(concrete)


def check_zdr_endpoints(config: dict, models: list) -> set:
    """Verifies that every model has a ZDR endpoint. Returns the models for which ZDR gets switched off."""
    url = config['url']
    if not config.get('zdr', True):
        return set()
    if config.get('dry_run'):
        print("Dry run: skipping the check of ZDR endpoint availability.")
        return set()
    if "openrouter.ai" not in url:
        print(f"Skipping the check of ZDR endpoint availability, as {url} is not an OpenRouter URL.")
        return set()

    zdr_url = url.replace("/chat/completions", "/endpoints/zdr")
    headers = {"Authorization": f"Bearer {os.environ.get(config['env_api_key_name'], '')}"}
    try:
        response = requests.get(zdr_url, headers=headers, timeout=60)
        response.raise_for_status()
        available = {endpoint.get('model_id') for endpoint in response.json()['data']}
    except (requests.exceptions.RequestException, KeyError) as e:
        detail = format_api_error(e.response) if getattr(e, 'response', None) is not None else repr(e)
        raise ValueError(f"Could not get the list of ZDR endpoints from {zdr_url}, so ZDR availability cannot be verified: {detail}") from e

    missing = {model for model in models if model not in available}
    if missing and config.get('turn_zdr_off_if_no_zdr_endpoint_available', False):
        print(f"Warning: no ZDR endpoint available for {sorted(missing)}. Running these models with ZDR turned off.")
    elif missing:
        raise ValueError(
            f"No ZDR endpoint available for {sorted(missing)}. To run with ZDR turned off, use --disable_zdr or set "
            "'zdr: false' in the config, or set 'turn_zdr_off_if_no_zdr_endpoint_available: true' in the config to "
            "turn it off only for the models without a ZDR endpoint."
        )
    return missing


def cost_estimate_path(config: dict, model: str) -> str:
    """Returns the estimate file of a benchmark and model, or None if the estimates are not kept in files."""
    directory = config.get('cost_estimate', {}).get('dir', 'cost_estimates')
    if not directory:
        return None
    name = f"{os.path.splitext(config['benchmark_file'])[0]}__{model}"
    return os.path.join(directory, re.sub(r'[^\w.-]+', '_', name) + ".json")


def estimate_cost(config: dict, items: list, no_zdr_models: set) -> Tuple[float, bool]:
    """Extrapolates the cost of the full run from one item per (model, modality). Returns (total, complete).

    Samples saved in the estimate file of the model are reused, only the missing ones are run. The sample results are
    discarded, and the seed sequence of the full run is left untouched.
    """
    by_modality = {}
    for item in items:
        by_modality.setdefault(item.get('modality'), []).append(item)

    def context_size(item):
        path = item['path_to_question_context_file']
        return os.path.getsize(path) if os.path.exists(path) else 0

    # A sample reused under other settings can be far off, e.g. a text-only sample for a full run
    settings = {key: config.get(key) for key in ('prompt_caching', 'text_only_baseline', 'white_noise_baseline')}
    force_rerun = config.get('cost_estimate', {}).get('force_rerun_estimate', False)

    print("\n--- Cost Estimate ---")
    rows = []
    total = 0.0
    complete = True
    for model in config['models']:
        path = cost_estimate_path(config, model)
        samples = {}
        if path and os.path.exists(path) and not force_rerun:
            with open(path, encoding='utf-8') as f:
                samples = json.load(f)['samples']

        modality_estimates = {}
        for modality, group in by_modality.items():
            saved = samples.get(modality)
            if saved:
                print(f"\nReusing saved sample from {saved['date']} for model {model} | Modality: {modality} | {path}")
                if saved['settings'] != settings:
                    print(f"Warning: the saved sample used other settings: {saved['settings']}, now: {settings}. "
                          "Use --force_rerun_estimate to replace it.")
                cost = saved['cost']
            else:
                # Median context size, as the size of the context file drives the prompt cost
                sample = sorted(group, key=context_size)[len(group) // 2]
                print(f"\nSample for model {model} | Modality: {modality} | Item ID: {sample.get('item_id')}")
                payload, final_prompt, _ = build_item_request(config, model, sample, config.get('seed'), no_zdr_models)
                cost, _, full_json, _ = ask_model(config, payload, final_prompt, config['dry_run'])
                if full_json.get('usage', {}).get('cost') is None:
                    rows.append((model, modality, len(group), "no cost reported", "-"))
                    continue
                samples[modality] = {"item_id": sample.get('item_id'), "context_file": sample['path_to_question_context_file'],
                                     "cost": cost, "usage": full_json['usage'], "settings": settings,
                                     "date": datetime.datetime.now().isoformat(timespec='seconds')}

            total += cost * len(group)
            rows.append((model, modality, len(group), f"${cost:.6f}", f"${cost * len(group):.4f}"))
            modality_estimates[modality] = {"items": len(group), "sample_cost": cost, "estimated_cost": cost * len(group)}

        model_complete = len(modality_estimates) == len(by_modality)
        complete = complete and model_complete
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"benchmark_file": config['benchmark_file'], "model": model, "samples": samples, "estimate": {
                    "modalities": modality_estimates,
                    "items": sum(row["items"] for row in modality_estimates.values()),
                    "cost": sum(row["estimated_cost"] for row in modality_estimates.values()),
                    "complete": model_complete,
                }}, f, indent=2)
            print(f"Saved the cost estimate to {path}")

    print(f"\n{'Model':<45} {'Modality':<10} {'Items':>6} {'Sample cost':>17} {'Estimate':>12}")
    for model, modality, count, sample_cost, estimate in rows:
        print(f"{model:<45} {modality:<10} {count:>6} {sample_cost:>17} {estimate:>12}")
    print(f"\nEstimated total cost: ${total:.4f}" + ("" if complete else " (lower bound, some samples reported no cost)"))
    print("Response lengths vary, and samples are not representative of cache hits in the full run.")
    return total, complete


def wait_for_approval(timeout: float, on_timeout: str):
    """Waits for Enter. On timeout, or at once if stdin is closed (e.g. in sbatch), stops or continues as configured."""
    deadline = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    print(f"Press Enter to start the full run, Ctrl+C to abort. With no approval by {deadline:%H:%M:%S} ({timeout}s), "
          f"the on_timeout action applies: {on_timeout}.", flush=True)

    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if ready and sys.stdin.readline():
        return
    if on_timeout == "continue":
        print("No approval received, continuing as configured.")
        return
    sys.exit("No approval received, stopping the run. No full run was started.")


def sanitize_payload_for_logging(payload: dict) -> dict:
    """Removes base64 data streams from logs."""
    sanitized = json.loads(json.dumps(payload))
    for msg in sanitized.get('messages', []):
        for part in msg.get('content', []):
            if msg.get("role") == "user":
                if part.get('type') == 'image_url':
                    part['image_url']['url'] = '[BASE64_IMAGE_STRIPPED]'
                elif part.get('type') == 'input_audio':
                    part['input_audio']['data'] = '[BASE64_AUDIO_STRIPPED]'
                elif part.get('type') == 'file':
                    part['file']['file_data'] = '[BASE64_FILE_STRIPPED]'
                elif part.get('type') == 'text' and part.get('text').startswith("--- Attached Symbolic Data ---"):
                    # No stripping for symbolic notation as abc notation is short
                    #part['text'] = '[SYMBOLIC_FILE_STRIPPED]'
                    ...
    return sanitized

# =========================================================================
# Main Benchmark Loop
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Run LLM benchmark.")
    parser.add_argument("--config", required=True, help="Path to config yaml file")
    parser.add_argument("--models", nargs='+', help="Override models in config")
    parser.add_argument("--max_waiting_time_per_request", type=int, help="Override max_waiting_time_per_request in config")
    parser.add_argument("--api-key-env", help="Override env_api_key_name in config")
    parser.add_argument("--url", help="Override API endpoint URL in config")
    parser.add_argument("--benchmark_file", help="Path to benchmark to be generated (overrides config)")
    parser.add_argument("--sheet_name", help="Override Google Sheet name in config")
    parser.add_argument("--text_only_baseline", help="Override text_only_baseline flag in config", action='store_true')
    parser.add_argument("--white_noise_baseline", help="Override white_noise_baseline flag in config", action='store_true')
    parser.add_argument("--modalities", nargs='+', help="Override modalities filter in config")
    parser.add_argument("--run_id", help="Optional run ID to use in logs (overrides random UUID generation)")
    # New arg for GSheet generation tracking
    parser.add_argument("--generate_new_list_with_logs", default=False, action="store_true", 
                        help="Generate separate cont/final/res lists inside Google Sheets")
    parser.add_argument("--verbose", default=False, action="store_true", 
                        help="Print verbose logs")
    parser.add_argument("--extra-verbose", default=False, action="store_true", 
                        help="If true, print the verbose logs to stdout")
    parser.add_argument("--evaluation_output_file", type=str, help="overrides the config's path to evaluation output file")
    parser.add_argument("--dry_run", default=False, action="store_true", 
                        help="Dry run: do not send anything to LLMs")
    
    parser.add_argument("--cost_estimate", default=False, action="store_true",
                        help="Before the full run, run one item per modality and model, print the estimated cost and wait for approval (overrides config).")

    parser.add_argument("--force_rerun_estimate", default=False, action="store_true",
                        help="With the cost estimate on, rerun the samples even if an estimate file exists (overrides config).")

    parser.add_argument("--disable_zdr", default=False, action="store_true",
                        help="Disable ZDR in the payload, to allow running other audio models that do not support ZDR (overrides config).")


    cmdline_args = parser.parse_args()

    # 1. Load and Override Config
    with open(cmdline_args.config, 'r') as f:
        config = yaml.safe_load(f)

    if cmdline_args.models:
        config['models'] = cmdline_args.models
    if cmdline_args.api_key_env:
        config['env_api_key_name'] = cmdline_args.api_key_env
    if cmdline_args.url:
        config['url'] = cmdline_args.url
    if cmdline_args.benchmark_file:
        config['benchmark_file'] = cmdline_args.benchmark_file
    if cmdline_args.sheet_name:
        config['sheet_name'] = cmdline_args.sheet_name
    if cmdline_args.text_only_baseline:
        config['text_only_baseline'] = True
    if cmdline_args.white_noise_baseline:
        config['white_noise_baseline'] = True
    if cmdline_args.modalities:
        config['filters'] = config.get('filters', {})
        config['filters']['modality'] = cmdline_args.modalities
    if cmdline_args.verbose:
        config['verbose'] = True
    if cmdline_args.evaluation_output_file:
        config['evaluation_output_file'] = cmdline_args.evaluation_output_file
    if cmdline_args.dry_run:
        config['dry_run'] = True
    if cmdline_args.max_waiting_time_per_request:
        config['max_waiting_time_per_request'] = cmdline_args.max_waiting_time_per_request

    config['zdr'] = config.get('zdr', True) and not cmdline_args.disable_zdr

    if cmdline_args.cost_estimate:
        config.setdefault('cost_estimate', {})['enabled'] = True
    if cmdline_args.force_rerun_estimate:
        config.setdefault('cost_estimate', {})['force_rerun_estimate'] = True

    if cmdline_args.run_id:
        benchmark_run_uuid = cmdline_args.run_id
    else:
        benchmark_run_uuid = str(random_uuid())
        
    config["benchmark_run_uuid"] = benchmark_run_uuid

    rng = np.random.default_rng(config.get('seed', 42)) # to use for seed choice generate: rng.choice(list) / tested
    config['rng'] = rng

    logdir = set_logdir(config)
    config['api_error_log'] = os.path.join(logdir, "api_errors.log")
    
    # ---------------------------------------------------------------------------------
    # Generate Run-Specific Lists / Tabs into Google Sheets
    # ---------------------------------------------------------------------------------
    cont_list_name = fin_list_name = res_list_name = None
    if cmdline_args.generate_new_list_with_logs:
        # run_dt = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        run_dt = ""
        cont_list_name = f"{benchmark_run_uuid}_{run_dt}_cont"
        fin_list_name  = f"{benchmark_run_uuid}_{run_dt}_fin"
        res_list_name  = f"{benchmark_run_uuid}_{run_dt}_res"
        
        # Try to initialize the blank tabs 
        success = create_gsheet_tabs(config, [cont_list_name, fin_list_name, res_list_name])
        
        # If successfully created, override the single sheet_name target 
        # so utils.append_to_google_sheet directly appends there
        if success:
            config['sheet_name'] = cont_list_name

    # 2. Save modified config to log directory
    with open(os.path.join(logdir, "config_snapshot.yaml"), 'w') as f:
        yaml.dump(config, f)
        
    # 3. Copy benchmark file to log directory
    target_benchmark_file = config.get('benchmark_file')
    if target_benchmark_file and os.path.exists(target_benchmark_file):
        shutil.copy2(target_benchmark_file, os.path.join(logdir, os.path.basename(target_benchmark_file)))
    else:
        raise ValueError("Benchmark file must be specified and exist.")
         
    # Load extraction method
    methods_module = load_methods_module(config['path_to_extraction_file'])
    extraction_func = getattr(methods_module, config['extraction_method'])

    log_tsv_path = os.path.join(logdir, "logs.tsv")
    results_tsv_path = os.path.join(logdir, "results.tsv")

    # Check API key presence 
    api_key_name = config.get("env_api_key_name", "OPENROUTER_API_KEY")
    if not os.environ.get(api_key_name) and not config.get('dry_run'):
        # print(f"Warning: Environment variable {api_key_name} is missing!")
        raise ValueError(f"Environment variable {api_key_name} is required for API calls but not found. Please set it before running the benchmark.")

    # Read Benchmark TSV
    items = []
    with open(target_benchmark_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        headers = reader.fieldnames
        for row in reader:
            items.append(row)

    # Filter the benchmark items
    print(f"\n--- Data Loading & Filtering ---")
    print(f"Loaded initial benchmark with {len(items)} items.")

    filters = config.get("filters", {})
    if filters:
        for column, allowed_values in filters.items():
            if allowed_values: 
                temp_items = [i for i in items if i.get(column) in allowed_values]
                print(f"Filter applied: Column '{column}' {allowed_values} -> Kept {len(temp_items)}")
                items = temp_items

    if len(items) == 0:
        print("No items match the required filters. Exiting.")
        sys.exit(0)

    print(f"Models to evaluate: {len(config['models'])}")
    total_runs = len(items) * len(config['models'])
    print(f"Total question/model loops to perform: {total_runs}\n")

    no_zdr_models = check_zdr_endpoints(config, resolve_concrete_models(config, items))

    cost_estimate = config.get('cost_estimate', {})
    if cost_estimate.get('enabled', False):
        if config['dry_run']:
            print("Dry run: skipping the cost estimate.")
        else:
            estimate_cost(config, items, no_zdr_models)
            wait_for_approval(cost_estimate.get('approval_timeout_seconds', 120), cost_estimate.get('on_timeout', 'stop'))

    # Prepare the log TSV headers
    log_headers = headers + [
        "benchmark_run_uuid", "datetime", "full_prompt", "parameters" , "model", "full_json_response",
        "extracted_response", "config_info", "label_of_answer", 
        "price", "time_taken", "is_correct"
    ]

    with open(log_tsv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=log_headers, delimiter='\t')
        writer.writeheader()

    all_executed_logs = []
    run_count = 0

    for model in config['models']:
        for item in items:
            run_count += 1
            print(f"\n[{run_count}/{total_runs}] Running Model: {model} | Item ID: {item.get('item_id')}")

            if config.get('seed', None) is None:
                print("Warning: No seed provided for inference. The inference will be completely non-deterministic.")
                current_seed_for_inference = None
            else:
                current_seed_for_inference = config['rng'].integers(0, 1e9)
                print(f"Using seed {current_seed_for_inference} for inference.")

            payload, final_prompt, content_file = build_item_request(config, model, item, current_seed_for_inference, no_zdr_models)

            # Execute Request
            cost, time_taken, full_json, resp_text = ask_model(config, payload, final_prompt, config['dry_run'])

            verbose_logs_file = sys.stdout if cmdline_args.extra_verbose else sys.stderr
            if config["verbose"]:
                print("="*50, file=verbose_logs_file)
                print(f"Full response text: {resp_text}", file=verbose_logs_file)
                print("="*50, file=verbose_logs_file)

            # Extract Response and Check Correctness
            extracted_answer = extraction_func(response=resp_text, all_choices=json.loads(item['all_choices']), index2ans=json.loads(item['index2ans']))
            
            if config["verbose"]:
                print(f"Extracted answer: {extracted_answer}", file=verbose_logs_file)
                print("="*50, file=verbose_logs_file)

            correct_label = item.get('label_of_final_correct_option', '').strip()
            is_correct = (extracted_answer == correct_label) if extracted_answer else "EXTRACTION FAILED"

            # Logging Logic
            text_only_baseline = config.get('text_only_baseline', False)
            white_noise_baseline = config.get('white_noise_baseline', False)
            log_row = item.copy()
            model_str = "text-only-" + model if text_only_baseline else ("white-noise-" + model if white_noise_baseline else model)
            log_row.update({
                "benchmark_run_uuid": benchmark_run_uuid,
                "datetime": datetime.datetime.now().isoformat(),
                "full_prompt": final_prompt,
                "parameters": json.dumps(sanitize_payload_for_logging(payload=payload)),
                "model": model_str,
                "full_json_response": json.dumps(full_json),
                "extracted_response": resp_text,
                "config_info": json.dumps({"text-only-baseline": text_only_baseline, "dry_run": config['dry_run'], "url": config['url'], "seed": config['seed'], "white-noise-baseline": white_noise_baseline, "content_file_used": content_file, "prompt_caching": config.get('prompt_caching')}),                
                "label_of_answer": extracted_answer,
                "price": cost,
                "time_taken": time_taken,
                "is_correct": is_correct
            })

            # Save line into memory
            all_executed_logs.append(log_row)

            # 1. Log to local TSV
            with open(log_tsv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=log_headers, delimiter='\t')
                writer.writerow(log_row)

            # 2. Log to Google Sheets
            # Note: Because we overwrote config['sheet_name'], this goes into the `cont` list dynamically.
            if config.get('log_to_google_sheet'):
                row_list = [log_row.get(h, "") for h in log_headers]
                append_to_google_sheet(config, row_list, header=log_headers, force_header_print=config.get("force_header_print", False))
                # Enforce the header print only for the first item
                config["force_header_print"] = False

            # 3. Print concise log
            prompt_tokens_details = full_json.get('usage', {}).get('prompt_tokens_details') or {}
            cached_tokens, cache_write_tokens = prompt_tokens_details.get('cached_tokens'), prompt_tokens_details.get('cache_write_tokens')
            cache_info = f" | Cache read/write tokens: {cached_tokens or 0}/{cache_write_tokens or 0}" if cached_tokens or cache_write_tokens else ""
            print(f"  -> Extracted: {extracted_answer} | Expected: {correct_label} | Correct: {is_correct} | Time: {time_taken:.2f}s | Cost: ${cost:.6f}{cache_info}")

    # =====================================================================
    # Trigger final evaluation logic
    # =====================================================================
    evaluation_criteria = config.get("evaluation_criteria", [])
    output_tsvs = [results_tsv_path]
    results_path = config.get("evaluation_output_file", None)
    if results_path:
        output_tsvs += [results_path]

    evaluate_results(all_executed_logs, evaluation_criteria, output_tsvs=output_tsvs)

    # 4. Final Work - Copy TSVs to their respective Google Sheet tabs if flagged
    if cmdline_args.generate_new_list_with_logs:
        print("\nUploading final log and results data to respective Google Sheets lists...")
        upload_tsv_to_gsheet(config, tab_name=fin_list_name, tsv_file=log_tsv_path)
        upload_tsv_to_gsheet(config, tab_name=res_list_name, tsv_file=results_tsv_path)


if __name__ == "__main__":
    main()