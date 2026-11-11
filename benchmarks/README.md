# Benchmark instances — licensing

The benchmark instances in this directory are **derived data**: each one is built
from the contents of an underlying source dataset, and therefore inherits that
dataset's license. There are two source datasets, with two different licenses, so
**not all files here share the same license**.

| Files | Source dataset | License |
| :--- | :--- | :--- |
| `choralsynth.*.tsv` (e.g. `choralsynth.size20.seed_52.tsv`) | [ChoralSynth](../README.md#license) | **CC BY-SA 4.0** — see [`../LICENSE-DATA-CHORALSYNTH`](../LICENSE-DATA-CHORALSYNTH) |
| All other instances (`pre-generated_full_benchmark.tsv`, `A-pre-generated_full_benchmark.tsv`, `qs_per_subcat_20/seed_*.tsv`, …) | ChoraleBricks | **CC BY 4.0** — see [`../LICENSE-DATA-CHORALEBRICKS`](../LICENSE-DATA-CHORALEBRICKS) |

## Why two licenses

- **ChoraleBricks** is licensed **CC BY 4.0**, so instances derived from it remain
  CC BY 4.0 (attribution to ChoraleBricks required).
- **ChoralSynth** is licensed **CC BY-SA 4.0**. The **ShareAlike** term is
  contagious: any material derived from ChoralSynth — including these benchmark
  instances — must stay under CC BY-SA 4.0, with attribution to ChoralSynth. It
  cannot be relicensed under the authors' CC BY 4.0.

## Naming convention

ChoralSynth-derived instances are prefixed with `choralsynth` (the list of
ChoralSynth pieces is `pieces-choral-synth.tsv`). Every other
instance in this directory is derived from ChoraleBricks. If you generate new
instances, the result inherits the license of whichever source dataset it was
built from.

When in doubt, treat any `choralsynth*` file as **CC BY-SA 4.0**.
