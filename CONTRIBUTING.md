# Contributing to MusICA MetaBench

This pipeline generates multiple-choice music-perception benchmarks from music *you* provide.
The two things most worth contributing are therefore **a new question template** (a new thing to
ask about a piece) and **a new dataset** (new music to ask about). Both are documented below,
with a complete worked example for the first.

Contributions of any size are welcome, including bug reports about ground-truth extraction going
wrong on your music — that is genuinely useful information, since extraction has only been
validated on two corpora.

**Before you start, please read the honest status in the [README](README.md#current-status).**
The pipeline is verified on ChoraleBricks and ChoralSynth; a new corpus should be expected to
need some adaptation of the extraction functions.

## Contents

1. [Adding a question template](#adding-a-question-template)
2. [Worked example: `get_nth_note`](#worked-example-get_nth_note)
3. [Designing questions that travel across modalities](#designing-questions-that-travel-across-modalities)
4. [Adding a dataset](#adding-a-dataset)
5. [Adding a new format or submodality](#adding-a-new-format-or-submodality)
6. [Where contributions go](#where-contributions-go)

---

## Adding a question template

A question template ("meta-question") is one row in [meta-questions.tsv](meta-questions.tsv) plus
one Python method. Everything else — instantiating the wildcards, pairing the template with every
piece, building the option list, inserting *none of the above*, subsampling, cross-modal
expansion, inference and scoring — is inherited from the pipeline.

There are currently **11 templates**, covering pitch (4), rhythm (4) and harmony (3).

### 1. Write the extraction method

Add a method to the `AnswerDistractorExtractors` class in
[src/ground_truth_and_distractor_pool_extractions.py](src/ground_truth_and_distractor_pool_extractions.py).
The contract is:

```python
def my_extractor(self, path: str, values: dict) -> tuple[str, list[str], dict]:
    ...
    return ground_truth, distractor_pool, values
```

| Element | Meaning |
| :--- | :--- |
| `path` | The **directory** of one piece, e.g. `data/chorale-bricks/Jan_DuGrosserSchmerzensmann`. Call `get_musicxml_file_path(path)` from [utils.py](utils.py) to get `symbolic.musicxml` inside it. Ground truth is always extracted from the symbolic score, never from the audio or the image. |
| `values` | The wildcard binding for this question, e.g. `{"target_index": 1, "voice": "S"}`. Keys come from the template's `question_keys` column. |
| return 1 — `ground_truth` | The correct answer, as the string that will be shown to the model (e.g. `"B"`, `"E flat"`, `"perfect fifth"`). Map raw `music21` values through the ontology dictionaries (`self.dict_note_ontology`, `self.dict_interval_ontology`, …) so the wording matches the rest of the benchmark. |
| return 2 — `distractor_pool` | Candidate wrong answers. See below. |
| return 3 — `values` | The **same dict, possibly modified**. This is how an extractor reports a wildcard value it chose itself rather than received — see `use_all_inds` below. The caller re-renders the question text from it, so if you do not modify it, return it unchanged. |

Two things worth knowing before you write one:

- **Returning three values is mandatory**, even though several existing docstrings in that file
  claim a return type of `str` or a 2-tuple. Those docstrings are stale; the wrapper
  `extract_answer_and_distractors` unpacks three.
- **You do not have to exclude the ground truth from the distractor pool.** The wrapper removes
  it defensively. Doing it yourself anyway is harmless.

#### Distractors

Distractors are drawn **from the piece itself** wherever possible — for a pitch question, the
other note names that actually occur in the score; for an interval question, the other intervals
present. This makes the wrong answers plausible for that specific piece rather than generically
plausible.

Setting `random_distractors: true` in the config switches every extractor to sampling from the
ontology instead. The default is `false`.

The pipeline then sorts the pool (`sorting_method` in the config; currently `dummy_shuffle`, which
just shuffles) and takes the top `num_options - 1` entries. If a piece yields fewer than
`min_num_distractors` (default 4), the question is dropped for that piece. Roughly
`nota_correct_percentage` (default 20 %) of the generated items have *none of the other options is
correct* as the correct answer, to probe over-confidence.

#### Self-chosen wildcard values (`use_all_inds`)

The `target_index` wildcard has only four values in [ontology.yaml](ontology.yaml) — `first`,
`second`, `third`, `last`. With `use_all_inds: true` (the default in
[benchmark-generation-config-chorale-bricks.yaml](benchmark-generation-config-chorale-bricks.yaml)) it is replaced by a
`VirtualIndexList` that produces ordinals up to `max_target_index` on demand, and extractors pick
an index themselves:

```python
if self.use_all_inds:
    note_index = int(self.rng.choice(range(len(notes) - 1)))
    values['target_index'] = str(note_index)   # reported back through the third return value
else:
    note_index = self.ontology['target_index'][values.get('target_index')]
```

The wrapper then turns `"21"` back into the word `"21st"` before rendering the question text.
**Always use `self.rng`**, never `random`, so that a seed reproduces a benchmark instance.

If a question cannot be built for a piece — voice missing, index out of range, no notes — raise.
The generator catches the exception, counts it, and moves on to the next piece.

### 2. Register the template

Add a row to [meta-questions.tsv](meta-questions.tsv). It is a tab-separated file, so no field may
contain a tab.

| Column | What to put in it |
| :--- | :--- |
| `meta-question_id` | Next free integer. |
| `perception` | `perception`. |
| `category` | `pitch`, `rhythm` or `harmony` — or a new one. |
| `rel/abs` | `relative` or `absolute`. See [the modality section](#designing-questions-that-travel-across-modalities); this is not bookkeeping, it predicts which modalities can answer your question. |
| `specification`, `subcategory` | Grouping used for balancing and for the per-category plots. `questions_per_subcategory_count` is *per subcategory*, so adding a template to an existing subcategory splits that budget rather than enlarging it. |
| `simul/seq` | Simultaneous or sequential; may be left empty. |
| `skill` | Free-text label for the skill, e.g. `interval statistics`. |
| `text_with_wildcards` | The question, with wildcards in braces: `What is the pitch name of the {target_index} {voice} note in the provided excerpt?` |
| `question_keys` | JSON list of the wildcard names, e.g. `["target_index", "voice"]`. These must exist in the ontology. |
| `method_for_ground_truth_extraction` | **The exact method name** you added to `AnswerDistractorExtractors`. It is resolved by `getattr`; a typo is a hard error at generation time. |
| `requires` | Currently **not read by any code**. Only one row sets it (`symbolic.musicxml`). Leave it empty. |
| `ontology_key` | The ontology dictionary the answer is drawn from (`pitch`, `interval`, `rhythm`, …), or empty for the harmony templates. |

That is the whole registration step — there is no plugin registry and no separate manifest.

### 3. Check the ontology

The ontology is **hybrid**. [ontology.yaml](ontology.yaml) supplies the small hand-written
dictionaries — `target_index`, `voice`, `accidental`, `quantity`, `modality`, `function` — as
lists of single-entry `symbol: word` mappings:

```yaml
voice:
  - S: "soprano"
  - A: "alto"
  - T: "tenor"
  - B: "bass"
```

The larger musical dictionaries — `interval`, `pitch`, `rhythm`, `time_signature`, `tonality`,
`chords`, `rhythm_proportion` — are **generated from `music21`** in
`AnswerDistractorExtractors.__init__` whenever the key is absent from the YAML, using
`music_ontology_settings.harmonic_system` (default `tonal`). Adding a key to the YAML overrides
the generated one.

So if your template needs values the ontology lacks: add the key to `ontology.yaml` by hand for a
small closed set, or write a `build_*_ontology` method alongside the existing ones for something
systematic. Note that non-tonal systems are not implemented — `harmonic_system` accepts the value
but only `tonal` is built out.

### 4. Test it cheaply before spending money

Generate a tiny benchmark restricted to your template alone:

```bash
.venv/bin/python generate_benchmark.py \
    --config benchmark-generation-config-chorale-bricks.yaml \
    --benchmark_file /tmp/smoke.tsv \
    --allowed_metaq_ids 12 \
    --questions_per_subcategory_count 2
```

`--allowed_metaq_ids` (or `allowed_metaq_ids` in the config) is the filter that keeps this from
running your whole corpus. Generation makes **no API calls** and costs nothing — only
`run_benchmark.py` spends money — so iterate here freely.

Every pipeline step also writes a numbered intermediate TSV to
`logs/intermediate_benchmarks/<timestamp>/`, from `00_minus_2_raw_meta.tsv` through
`02_benchmark_distractors_sorted.tsv` and on. When ground truth comes out wrong, those files tell
you which step it went wrong at.

Read the generated items by eye before running any model. Ground-truth extraction that is subtly
wrong looks exactly like a model that is bad at music.

---

## Worked example: `get_nth_note`

Meta-question 1, the simplest template in the repo, end to end.

### The row in `meta-questions.tsv`

| Column | Value |
| :--- | :--- |
| `meta-question_id` | `1` |
| `category` / `subcategory` | `pitch` / `pitch-recognition` |
| `rel/abs` | `absolute` |
| `skill` | `pitch recognition` |
| `text_with_wildcards` | `What is the pitch name of the {target_index} {voice} note in the provided excerpt?` |
| `question_keys` | `["target_index", "voice"]` |
| `method_for_ground_truth_extraction` | `get_nth_note` |
| `ontology_key` | `pitch` |

### The method

Abridged from
[src/ground_truth_and_distractor_pool_extractions.py](src/ground_truth_and_distractor_pool_extractions.py);
the full version adds the error handling described above.

```python
def get_nth_note(self, path: str, values: dict):
    musicxml_path = get_musicxml_file_path(path)          # <piece dir>/symbolic.musicxml
    score = converter.parse(musicxml_path)                # music21

    part_index = self.voice_mapping[values.get('voice')]  # 'S' | 'A' | 'T' | 'B'
    target_part = score.parts[part_index]
    notes = list(target_part.flatten().getElementsByClass(note.Note))

    if self.use_all_inds:                                 # pick an index, report it back
        note_index = int(self.rng.choice(range(len(notes) - 1)))
        values['target_index'] = str(note_index)
    else:
        note_index = self.ontology['target_index'][values.get('target_index')]

    target_note = notes[note_index]

    if not self.random_distractors:
        for vv in self.voice_mapping:                     # note names from the whole piece
            notes += list(score.parts[self.voice_mapping[vv]]
                          .flatten().getElementsByClass(note.Note))
        possible = {n.name for n in notes if n.name != target_note.name}
        distractor_pool = [self.dict_note_ontology[s] for s in possible]
    else:
        distractor_pool = []

    return self.dict_note_ontology[target_note.name], distractor_pool, values
```

Two things this shows that the prose above only asserts: the distractor pool is built from note
names occurring **in that piece**, and `values` is mutated and returned so the question text can
be re-rendered with the index the method chose.

Note also that `voice_mapping` here is hard-coded to a four-part `S/A/T/B` score. That assumption
is exactly what had to be generalised for ChoralSynth — see [Adding a dataset](#adding-a-dataset).

### A generated item

Taken verbatim from [benchmarks/qs_per_subcat_20/seed_52.tsv](benchmarks/qs_per_subcat_20/seed_52.tsv),
the instance used in the paper:

```
item_id                       aad610c3-284b-5347-a9c8-840f216394c9
piece_id                      Jan_DuGrosserSchmerzensmann
values                        {"target_index": "21st", "voice": "tenor"}
question                      What is the pitch name of the 21st tenor note in the provided excerpt?
ground_truth                  B
distractor_pool               ["A", "C", "C sharp", "D", "D sharp", "E", "F sharp", "G"]
sorted_distractors            ["C sharp", "E", "A", "F sharp", "G", "D sharp", "D", "C"]
modality                      audio
submodality                   audio.mastermix.wav
path_to_question_context_file data/chorale-bricks/Jan_DuGrosserSchmerzensmann/audio.mastermix.wav
labeled_final_options         ["(A) A", "(B) C sharp", "(C) none of the other options is correct",
                               "(D) E", "(E) B"]
label_of_final_correct_option E
```

The same question is also emitted for the `visual.short.png` and `symbolic.abc.txt` submodalities
of the same piece — that cross-modal expansion is what the pipeline is for, and it is why an
*absolute* pitch question is a deliberately awkward example, which the next section is about.

---

## Designing questions that travel across modalities

The pipeline asks the same question of audio, a score image and symbolic notation. Whether that is
*fair* depends entirely on how the question is phrased, and this is the most interesting open
design problem in the project. Of the 11 current templates, 6 are relative and 5 absolute.

**Relative questions travel.** Intervals, duration ratios and Roman-numeral progressions are
answerable from a recording, from a score image and from ABC alike. Templates 3, 4, 7, 8, 9 and 11
are of this kind.

**Absolute questions favour notation.**

- *Pitch names* (`C#`, `G`, `B♭`) from a recording require perfect pitch. A competent musician
  without it cannot answer at all — not "answers less accurately", but *cannot attempt it*.
- *Notated durations* (`whole`, `eighth`, `sixteenth`) are a property of the score, not of the
  sound. The same performance renotated at half the note values is acoustically identical, so the
  question has no determinate answer from audio.

The proportion templates (7 and 8) are the deliberate modality-fair counterparts of the
notated-duration ones (5 and 6): a 2:1 ratio survives renotation, an "eighth note" does not.

**Voice-indexed questions load the audio modality asymmetrically.** Anything phrased "in the alto
line" requires source separation from a mixed recording before the question can even be attempted,
whereas in a score image or in ABC the voice is simply labelled. Eight of the eleven templates
(1–8) take a `voice` wildcard, so this is not a corner case — it is a known, unresolved bias, discussed in
the paper.

**Making a template fully modality-neutral is an open problem, and contributions are very
welcome.** If you have a template that measures the same skill in all three modalities without an
asymmetry of this kind, it is exactly what the project needs.

---

## Adding a dataset

### Requirements

- **Tonal repertoire.** Non-tonal music needs the question templates and the ontology generation
  adjusted.
- **One or more monophonic voices** (choral, wind, string). Polyphonic instruments such as piano
  need adjustments to the extraction methods.
- **Piece-aligned modalities** — the same piece, in the same key, represented simultaneously as
  audio, score image and symbolic file.
- **MusicXML for every piece.** `symbolic.musicxml` is required; it is where all ground truth
  comes from. Other symbolic formats (MIDI, ABC, LilyPond, Humdrum) may work but are **unverified**
  and will likely need adjustments.

### Layout

Put each piece in its own directory:

```
data/<dataset>/<piece_id>/
    symbolic.musicxml       # required — ground truth is extracted from this
    audio.mastermix.wav     # audio submodality
    visual.short.png        # image submodality
    symbolic.abc.txt        # symbolic submodality as presented to the model
```

The three non-MusicXML filenames are the **submodality names** configured in the
generation config (e.g. [benchmark-generation-config-chorale-bricks.yaml](benchmark-generation-config-chorale-bricks.yaml)); the convention is
`<modality><anything>.<extension>`. Then run

```bash
bash generate_pieces_list.sh <dataset>
```

to regenerate `pieces-<dataset>.tsv` (e.g. [pieces-chorale-bricks.tsv](pieces-chorale-bricks.tsv)), which the generator reads.
For a new dataset, also add a `benchmark-generation-config-<dataset>.yaml` whose `cmdline_args.pieces` points to it.

### Synthesising the modalities you do not have

- **Score image:** [src/conversions/musicxml2pdf.py](src/conversions/musicxml2pdf.py) renders via
  **MuseScore** (the executable path is resolved in `get_musescore_path`; on Linux it defaults to
  `mscore3` on the `PATH`), then [src/conversions/pdf2png.sh](src/conversions/pdf2png.sh)
  rasterises with `pdftoppm`. Rendering needs display access — use `ssh -X` / `ssh -Y` if remote.
- **Symbolic:** [src/conversions/musicxml2abc.py](src/conversions/musicxml2abc.py) converts
  MusicXML to ABC using the `abc_xml_converter` library.

For ChoraleBricks, [prepare_data.sh](prepare_data.sh) does all of this, including downloading the
source material.

### Known pitfalls

These are all things that have actually gone wrong, and all worth checking on a new corpus:

- **Long pieces produce unreadable score images.** Concatenating a rendered score into a single
  image can span several pages and become effectively illegible. This measurably depressed
  image-modality scores on ChoralSynth. Check what your `visual.*.png` actually looks like at the
  size a model receives it.
- **Voice labels may be unidentifiable from a mixed recording.** A part named `Bassus Ch1-F4`
  cannot be picked out of a mastermix, which makes every voice-indexed question unanswerable in
  the audio condition — see the modality section above.
- **Spot-check ground truth before a full run.** Extraction has only been validated on
  ChoraleBricks and ChoralSynth. Generate a handful of items and verify them against the score by
  hand. This is the single highest-value thing you can do with a new dataset.
- **Cost.** Benchmark *generation* is free, but inference is not. Around **300 items are enough to
  detect a 6 pp difference between models** — see
  [aggregate_results_for_determining_benchmark_size.py](aggregate_results_for_determining_benchmark_size.py)
  and the size-calibration analysis in the paper. There is no reason to generate and run a
  12 000-item benchmark, and it is easy to do by accident.

### What adapting to a second dataset actually took

ChoralSynth is the one worked precedent, and it is honest to say what it cost. The work lives on
the `dataset-choralsynth` branch (**not merged into `main`**) and included:

- addressing voices **by number** instead of the hard-coded `S`/`A`/`T`/`B` mapping;
- extracting part names from the score, behind a `use_xml_part_names` setting;
- a check that each voice is monophonic, skipping voices that are not;
- skipping questions when the piece does not have the expected number of voices;
- enharmonic tonality names, and a guard returning `None` when extracted ground truth is absent
  from the ontology;
- handling larger pieces in data preparation, and changes to the MusicXML-to-PDF conversion.

Expect a comparable amount of work for a third corpus. If you do it, a PR reporting what broke is
valuable even if you do not fix all of it.

---

## Adding a new format or submodality

To compare, say, rendered vs. scanned vs. handwritten score images, or to add MIDI:

1. Add the new extension and its description to `musical_piece_format_info` in
   [run_benchmark.py](run_benchmark.py) or in your config file. Audio must be `WAV`, images `PNG`
   or `PDF`, and symbolic formats must be textual — MIDI has to be converted to something like CSV
   before it can be fed to a model. Submodality names must follow
   `<modality><anything>.<extension>`.
2. Add the submodality to `submodalities` in the generation configs
   (`benchmark-generation-config-*.yaml`) so the generator emits
   items for it.

---

## Where contributions go

- **Open a pull request against `main`** in this repository, or open an issue first if you would
  like to discuss the design — especially for a new template, where the modality question above is
  usually worth talking through.
- **This is a small research project.** Review may take weeks. That is not disinterest; there is
  no full-time maintainer.
- **Day-to-day development currently happens in a private repository** and changes are ported
  across to this one. Consolidating into this repository is planned, but until it happens your PR
  may be merged here and replayed there, and you may see commits arrive in batches rather than
  continuously. We would rather say so than imply a responsiveness the project does not have yet.

By contributing you agree that your contribution is licensed under the same terms as the part of
the repository it touches — **GPL-3.0-or-later** for code, and the relevant data license for
dataset-derived material. See the [License section of the README](README.md#license).
