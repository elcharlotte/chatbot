"""
llm_ratings_api.py — API LLM-Based Personality Rating Runner
==========================================================

Runs the configured LLM(s) over interview transcripts to produce
personality ratings (per RESEARCH_PLAN in config.py), with support
for skipping/rerating existing results.

Workflow:
1. Load: Read the merged, cleaned dataset (df_merged_cleaned.csv) produced
   by the data-wrangling pipeline, and load API keys (from .env) for each
   configured model.
2. Check: Print a summary of interview text lengths (chars/~tokens),
   configured models, the research plan (all combinations to run), and
   any ratings that already exist in results/ratings/. Prompts the user
   for interactive confirmation before proceeding.
3. Rate: For each model x research-plan combination, skip if a rating
   file already exists (unless should_rerate() says otherwise), otherwise
   call the API (via rate_df_api) with the appropriate structured-output
   schema (FacetLevelRatings or ItemLevelRatings) and the plan's system
   prompt. Facet-level scores are rescaled from a 10–50 to a 1–5 scale
   before saving. Each result is written to its own CSV under
   results/ratings/, named `<model>_<level>_<norm>_<...>.csv`.

Inputs:  data/df_merged_cleaned.csv, config.RESEARCH_PLAN, config.MODELS,
         .env (API keys referenced by config.MODELS' key_name fields)
Outputs: results/ratings/<model>_<prompt_label>.csv (one file per
         model/plan combination)

Run directly via `python llm_ratings_api.py`. Requires interactive
confirmation (y/n) before making the API calls.
"""
import os
import re
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from utils import (
    should_rerate,
    rate_df_api
)

from config import (
    RESEARCH_PLAN,
    MODELS,
    FACET_ITEM_MAP,
    FacetLevelRatings,
    ItemLevelRatings,
)
MODELS = MODELS["api"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

### Input paths ###
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = ROOT_DIR / "data"

### Output paths ###
RESULTS_DIR = ROOT_DIR / "results"
RATINGS_DIR = RESULTS_DIR / "ratings"

### Import API keys ###
key_names = set([model["key_name"] for model in MODELS])
load_dotenv()

API_KEYS = {}
for key_name in key_names:
    API_KEYS[key_name] = os.environ[key_name]

### Controls ###
MODEL_RERATE = None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # ── Step 1: Load data ──────────────────────────────────────────────────
    print(f"[1/3] Loading data...")

    df = pd.read_csv(DATA_DIR / "df_merged_cleaned.csv")
    print(f"  Loaded {len(df)} rows x {len(df.columns)} columns")

    # ── Step 2: Check data ─────────────────────────────────────────────────
    print(f"[2/3] Checking data...")
    print_len = 50

    # Interviews summary
    len_summary = df["chat_text"].str.len().describe().round(2).to_frame(name="chars")
    len_summary = len_summary.drop(index=["count"])
    len_summary["~ tokens"] = (len_summary["chars"]/3).round(2)

    print(f"\n  {'── Interviews summary ':─<{print_len}}")
    for line in len_summary.to_string().splitlines():
        print(f"  {line}")
    print(f"  {'':─<{print_len}}")

    # Models
    print(f"\n  {'── Models ':─<{print_len}}")
    for model in MODELS:
        print(f"  {model["model"]}, {model["base_url"]}")
    print(f"  {'':─<{print_len}}")

    # Research plan
    print(f"\n  {'── Research plan ':─<{print_len}}")
    for plan in RESEARCH_PLAN:
        print(f"  {plan['combination']}")
    print(f"  {'':─<{print_len}}")

    # Existing ratings
    existing_ratings = pd.DataFrame(
        [re.split(r"[_.]", file.name) for file in RATINGS_DIR.iterdir() if file.is_file()],
        columns=["model", "level", "norm_input", "type"]
    )

    print(f"\n  {'── Existing ratings ':─<{print_len}}")
    for line in existing_ratings.to_string().splitlines():
        print(f"  {line}")
    print(f"  {'':─<{print_len}}")

    print()

    while True:
        answer = input("  Do you want to proceed to rating? (y/n) ").strip().lower()

        if answer == "y":
            break
        elif answer == "n":
            print("  [NOTE] Aborted.")
            raise SystemExit
        else:
            print("  [WARNING] Invalid input. Please enter 'y' or 'n'.")

    # ── Step 3: Rate interviews ────────────────────────────────────────────
    print(f"[3/3] Rating interviews...")

    results = {}

    for model in MODELS:
        for plan in RESEARCH_PLAN:

            label = f"{model['model'].split('/')[-1]}_{plan['prompt_label']}"
            save_path = RATINGS_DIR / f"{label}.csv"

            # Determine whether this particular combination should be rerated
            rerate = should_rerate(model, plan, MODEL_RERATE)
            
            if save_path.exists() and not rerate:
                print(f"    [Note] Ratings for {model['model']} already exist - skipped")
                continue

            
            print(f"  Rating [{model['model']}, {plan['plompt_label']}]...")

            if plan["level"] == "facet-lvl":
                response_format = FacetLevelRatings
            elif plan["level"] == "item-lvl":
                response_format = ItemLevelRatings
            else:
                raise ValueError(f"Unknown rating level: {plan['level']}")

            rating_df = rate_df_api(
                df=df,
                chat_column="chat_text",
                identifier_column="participant_id",
                system_prompt=plan["system_prompt"],
                model=model["model"],
                base_url=model["base_url"],
                api_key=API_KEYS[model["key_name"]],
                response_format=response_format,
                label=model["model"] + "_" + plan["prompt_label"]
            )

            results[label] = {
                "df": rating_df,
                "model": model,
                "plan": plan,
                "save_path": save_path
            }

    # Save results
    for label, result in results.items():

        rating_df = result["df"]
        model = result["model"]
        plan = result["plan"]
        save_path = result["save_path"]

        # Format facet scores
        if plan["level"] == "facet-lvl":
            # Transform ratings to scale from 1 to 5
            facet_columns = list(FACET_ITEM_MAP.keys())
            rating_df[facet_columns] = rating_df[facet_columns] / 10

        save_path.parent.mkdir(parents=True, exist_ok=True)
        rating_df.to_csv(save_path, index=False)
        print(f"    Saved [{model['model']}, {plan['prompt_label']}] to {save_path}")