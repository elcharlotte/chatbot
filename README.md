# Personality AI-Interview Study

Research codebase for a study that uses an LLM chatbot to conduct
personality interviews — based on the Trait Self-Descriptive Inventory
(TSDI), extended with the HEXACO Honesty-Humility dimension — and then
compares AI-derived personality ratings against external raters
("Fremdurteil") and participants' own self-reports.

The repo has two parts:

- **`streamlit/`** — the participant- and rater-facing web apps (data
  collection).
- **`analysis/`** — the offline pipeline that cleans the collected data,
  generates LLM-based personality ratings, and produces plots (data
  processing & analysis).

## Repository structure

```
.
├── streamlit/                  # Data collection apps (Streamlit)
│   ├── chatbot_uebung.py       # Main AI interview chatbot (4 conditions: structured/open × write/speech)
│   ├── chatbot_lawi.py         # Simplified/earlier variant of the interview chatbot (single condition)
│   ├── fremdurteil.py          # External-rater ("Fremdurteil") app: assigns and collects third-party ratings of interview transcripts
│   ├── requirements.txt        # Python dependencies for the Streamlit apps
│   └── .devcontainer/          # Codespaces/devcontainer config to run chatbot_lawi.py
│
├── analysis/                   # Offline data wrangling & LLM rating pipeline
│   ├── config.py                # Facet/item mappings, TSDI+HEXACO item texts & descriptions, model configs, LLM system-prompt templates, Pydantic response schemas
│   ├── data_wrangling.py        # Loads raw interviews/fremdurteil/coding-sheet/self-report data, cleans and merges them into one dataset
│   ├── llm_ratings_api.py       # Runs configured LLM(s) over interview transcripts to produce facet-/item-level personality ratings
│   ├── plots_rating.R           # R script for plotting/analyzing the resulting ratings
│   ├── requirements.txt         # Python dependencies for the analysis pipeline
│   └── utils/
│       ├── data_wrangling_utils.py   # Helpers: loading interview JSON files, ID handling, unpacking multi-value columns
│       └── llm_rating_utils.py       # Helpers: calling the LLM API, deciding what to rerate, computing facet scores from item scores
│
├── .gitignore
└── .vscode/
```

Data, results, figures, and other generated/sensitive artifacts
(`data/`, `figures/`, `meeting_slides/`, `results/`, `literature/`, `.env`)
are git-ignored and not part of this repo — they're expected to be
supplied locally, e.g. as described in `analysis/data_wrangling.py` and
`analysis/data/README.md` (if present).

## `streamlit/` — Data collection

Three Streamlit apps, deployed separately, used to run the study with
participants and external raters:

- **`chatbot_uebung.py`** — the main interview app. On first load, each
  participant is randomly assigned to one of four conditions (a
  structured vs. open interview style, crossed with a written vs. spoken
  response mode — currently only the write conditions are active).
  Guides participants through consent, a structured/open TSDI+HEXACO
  interview with an LLM (via the OpenAI API), and post-interview
  questionnaires, then uploads the transcript and metadata to a Nextcloud
  instance as JSON.
- **`chatbot_lawi.py`** — an earlier/simplified variant of the interview
  app with a single fixed condition; used for a course context ("LAWI").
  Included in the devcontainer for quick local exploration.
- **`fremdurteil.py`** — the external-rater app. Fetches interview
  transcripts from Nextcloud, assigns them to raters, and collects the
  raters' TSDI/HEXACO item ratings, uploading results back to Nextcloud.

### Running a Streamlit app locally

```bash
cd streamlit
pip install -r requirements.txt
streamlit run chatbot_uebung.py   # or chatbot_lawi.py / fremdurteil.py
```

Each app expects Streamlit secrets (OpenAI API key, Nextcloud
credentials/URLs, and for `fremdurteil.py` also folder names and an
allow-list) configured via `st.secrets` (typically `.streamlit/secrets.toml`,
not included in this repo).

## `analysis/` — Data wrangling & LLM ratings

The offline pipeline that turns raw study data into a merged,
analysis-ready dataset and LLM-generated personality ratings.

1. **`data_wrangling.py`** loads:
   - interview transcripts + metadata (from Nextcloud exports),
   - external-rater ("Fremdurteil") ratings,
   - a manually completed interview-quality coding sheet,
   - participants' self-report TSDI/HEXACO questionnaire responses,

   cleans each source (consent filtering, deduplicating/standardizing
   participant IDs, renaming columns to canonical facet/item IDs,
   unpacking multi-value columns), and merges everything into a single
   participant-level CSV.

2. **`llm_ratings_api.py`** loads that merged dataset and, for each
   configured LLM and each entry in the research plan (facet-level vs.
   item-level rating × normative-context variants, defined in
   `config.py`), sends every interview transcript to the model via the
   OpenAI-compatible chat API and saves the structured ratings to CSV.
   Supports skipping or selectively rerating specific model/plan
   combinations that already have saved results.

3. **`plots_rating.R`** consumes the resulting rating CSVs for
   visualization and further statistical analysis.

`config.py` is the shared source of truth for facet/item definitions,
German-language TSDI+HEXACO descriptions and item texts, model
configuration, the LLM system-prompt templates (one per rating level ×
normative-context combination), and the Pydantic schemas
(`ItemLevelRatings`, `FacetLevelRatings`) used to constrain/parse LLM
output.

### Running the analysis pipeline locally

```bash
cd analysis
pip install -r requirements.txt
python data_wrangling.py      # produces data/df_merged_cleaned.csv
python llm_ratings_api.py     # produces results/ratings/*.csv (interactive confirmation required)
```

Requires an `.env` file in `analysis/` (or exported environment variables)
with API keys matching the `key_name` fields configured in `config.MODELS`
(e.g. `OPENAI_KEY`), and Python ≥ 3.10.

Expected input files live under `analysis/data/` (git-ignored) — see
the top of `data_wrangling.py` for the exact filenames expected.

## Notes

- All participant-facing text, TSDI/HEXACO item wording, and system
  prompts are in German, matching the study population.
- Personally identifying information (matriculation numbers) is used
  internally to link data sources but is dropped from all cleaned/merged
  outputs.
- The two `requirements.txt` files are independent — `streamlit/` and
  `analysis/` are meant to be run as (and installed into) separate
  environments.
