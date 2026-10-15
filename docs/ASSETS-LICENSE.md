# Licensing of the demo's assets

The online demo in this directory shows items of the ChoraleBricks benchmark instance
(`benchmarks/qs_per_subcat_20/seed_52.tsv`).

| Asset | Source | Licence |
| :--- | :--- | :--- |
| `assets/<piece>/audio.m4a` | Master mixes of [ChoraleBricks](https://www.audiolabs-erlangen.de/resources/MIR/2025-ChoraleBricks), unmodified | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Score images | **Not stored here.** Loaded at view time from the ChoraleBricks website, whose sheet music is "published with the kind permission of the rights holder" | not redistributed |
| ABC notation, questions, options and ground truth in `items.json` | Derived from the ChoraleBricks MusicXML files | CC BY 4.0, see [LICENSE-DATA-CHORALEBRICKS](../LICENSE-DATA-CHORALEBRICKS) |
| Model answers and raw responses in `items.json` | Inference logs of the runs reported in the paper | Not separately licensed — provided as-is, like `results/` |
| `index.html`, `export_demo.py` | This repository | GPL-3.0-or-later, see [LICENSE-SOURCE-CODE](../LICENSE-SOURCE-CODE) |

Attribution for ChoraleBricks: Stefan Balke, Axel Berndt, and Meinard Müller. *ChoraleBricks:
A Modular Multitrack Dataset for Wind Music Research.* Transactions of the International
Society for Music Information Retrieval, 8(1): 39–54, 2025. doi:10.5334/tismir.252.
Dataset: doi:10.5281/zenodo.15081741.
