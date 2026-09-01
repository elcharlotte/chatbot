"""
llm_rating_utils.py — LLM Rating & Facet-Scoring Helpers
============================================================

Utility functions used by the rating pipeline to (a) send interview
transcripts to an OpenAI-compatible chat API (llm_ratings_api.py) or
(b) to load large language models on the local machine or a HPC cluster
(llm_ratings_local.py) for structured personality ratings, decide which
existing ratings need to be redone, and derive facet-level scores from
item-level ratings.

Function groups:
- Generic: `should_rerate` decides, for a given model/research-plan
  combination, whether an existing rating file should be regenerated based
  on the `rerate` selector(s) passed to the pipeline.
- Rating via API: `rate_chat_api` sends a single system/user prompt pair to
  an OpenAI-compatible `/chat/completions` endpoint and parses the response
  into a given Pydantic schema; `rate_df_api` applies `rate_chat_api` to
  every row of a DataFrame (one interview/text per row) and collects the
  results into a single DataFrame.
- Local rating: reserved for future functions that rate text using a
  locally hosted model instead of an API (see config.MODELS["local"]);
  not yet implemented.
- Result analysis: `calculate_facet_scores` aggregates item-level ratings
  into facet-level scores (per config.FACET_ITEM_MAP), applying reverse
  scoring where needed.

Run directly (`python llm_rating_utils.py`) to execute a small smoke test:
rates a handful of example poems via the OpenAI API and aggregates the
resulting item ratings into a single "artistic_ability" facet score.
Requires an OPENAI_KEY in the environment/.env file.
"""

import os

import pandas as pd
from pydantic import BaseModel
from openai import OpenAI
from tqdm import tqdm


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

# Generic -------------------------------------------------------------------
def should_rerate(
        model: dict,
        plan: dict,
        rerate: None | str | list[str]
    ) -> bool:
    """
    Determine whether a model/research-plan combination should be rerated.

    Parameters
    ----------
    model : dict
        Model configuration containing at least the key ``"model"``.

    plan : dict
        Research-plan configuration. Any research-plan fields can be used as
        selectors, e.g. ``"level"``, ``"norm"``, or future fields such as
        ``"valence"``. The plan must also contain ``"prompt_label"``.

    rerate : None | "all" | list[str]
        Specifies which existing results should be rerated:

        - ``None``:
            Do not explicitly rerate anything. Existing results are skipped.

        - ``"all"``:
            Rerate all model/research-plan combinations.

        - ``list[str]`` list of strings:
            Rerate any combination matching at least one selector in the list.
            A selector can be:

            1. A model name, e.g. ``"gpt-5-mini"``
               → rerate all research plans for that model.

            2. Any value of a research-plan field, e.g. ``"facet-lvl"``
               or ``"without-norm"``

            3. An exact research-plan combination, e.g.
               ``"facet-lvl_without-norm"``
               → rerate that specific research plan for all models.

            Note: Multiple selectors use OR logic. For example:

                ["gpt-5-mini", "facet-lvl_without-norm"]

            rerates all research plans for ``gpt-5-mini`` AND the
            ``facet-lvl_without-norm`` plan for all other models.

    Returns
    -------
    bool
        ``True`` if the given model/research-plan combination should be
        rerated, otherwise ``False``.
    """

    # Explicitly rerate everything
    if rerate == "all":
        return True

    # No explicit rerating requested
    if rerate is None:
        return False

    # Model name is one possible selector
    selectors = {model["model"]}

    # All values in the research plan are possible selectors.
    # This automatically supports future fields such as "valence".
    for key, value in plan.items():
        if key == "system_prompt":
            continue

    if isinstance(value, str):
        selectors.add(value)

    return any(selector in selectors for selector in rerate)


# Rating via API ------------------------------------------------------------
def rate_chat_api(
    system_prompt: str,
    user_prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    response_format: type[BaseModel],
) -> dict:
    """
    Call an OpenAI-compatible chat API and return the structured response as
    a dictionary.

    Parameters
    ----------
    system_prompt : str
        System/developer instruction for the model.
    user_prompt : str
        User prompt to send to the model.
    model : str
        Model identifier, e.g. "gpt-5", "claude-sonnet-4-6".
    base_url : str
        Base URL of the OpenAI-compatible API.
    api_key : str
        API key for the provider.
    response_format : type[BaseModel]
        Pydantic model class describing the expected output.

    Returns
    -------
    dict
        A dictionary containing the parsed response.

    Raises
    ------
    ValueError
        If the model refuses the request or returns no parsed response.
    """
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=response_format,
    )

    message = completion.choices[0].message

    if message.parsed is not None:
        return message.parsed.model_dump()

    if message.refusal is not None:
        raise ValueError(f"Model refused the request: {message.refusal}")

    raise ValueError("Model returned no parsed response.")


def rate_df_api(
    df: pd.DataFrame,
    chat_column: str,
    identifier_column: str,
    system_prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    response_format: type[BaseModel],
    label: str
) -> pd.DataFrame:
    """
    Rate DataFrame with chat column through OpenAI-compatible chat API and
    return the structured responses as a pandas DataFrame.

    Calls `rate_chat_api` once per row (sequentially, not in parallel) and
    shows a tqdm progress bar while doing so.

    Parameters
    ----------
    df : pd.DataFrame
        A pandas DataFrame.
    chat_column : str
        Name of the column containing the text to be rated.
    identifier_column : str
        Name of the column containing the participant identifiers.
    system_prompt : str
        System/developer instruction for the model.
    model : str
        Model identifier, e.g. "gpt-5", "claude-sonnet-4-6".
    base_url : str
        Base URL of the OpenAI-compatible API.
    api_key : str
        API key for the provider.
    response_format : type[BaseModel]
        Pydantic model class describing the expected output.
    label : str
        Label of model + system prompt, stored in a "label" column of the
        returned DataFrame to identify which model/prompt produced each row.

    Returns
    -------
    pd.DataFrame
        A DataFrame with one row per input row, containing "label", the
        identifier column, and one column per field of `response_format`.
    """
    results = []

    for _,row in tqdm(df.iterrows(), desc="    Rating chats"):
        rating = rate_chat_api(system_prompt=system_prompt,
                               user_prompt=row[chat_column],
                               model=model,
                               base_url=base_url,
                               api_key=api_key,
                               response_format=response_format)

        result = {
            "label": label,
            f"{identifier_column}": row[identifier_column],
            **rating,
        }

        results.append(result)

    return pd.DataFrame(results)


# Local rating --------------------------------------------------------------
# Reserved for future functions that rate text using a locally hosted model
# (see config.MODELS["local"]) instead of an API. Not yet implemented.


# Result analysis -----------------------------------------------------------
def calculate_facet_scores(
    df: pd.DataFrame,
    facet_item_map: dict[str, list[str]],
    reverse_coded_items: list[str] | set[str] | None = None,
) -> pd.DataFrame:
    """
    Derive facet ratings from item ratings for one or more respondents.

    Each facet is measured by a fixed set of items (see config.FACET_ITEM_MAP).
    For every facet, this averages that facet's item columns and rounds to
    one decimal place.

    Items listed in `reverse_coded_items` are reverse-scored before
    averaging: on a 1-5 scale, a value v is mapped to 6 - v. Reverse-scored
    items get added to the DataFrame with the suffix '_reversed'.

    Parameters
    ----------
    df : pd.DataFrame
        A pandas DataFrame with the item ratings, named after its item
        key. Values are expected to be integers from 1 to 5. `df` must
        contain every item column referenced in `facet_item_map`.

    facet_item_map : dict[str, list[str]]
        Mapping from facet code (e.g. "a_fr") to the list of item column
        names that make up that facet.

    reverse_coded_items : list[str] | set[str] | None, default None
        Item keys that are reverse-worded relative to their facet and
        should be reverse-scored (6 - value) before averaging.
        Defaults to no reversal when not provided. Reverse-scored items
        get added to the DataFrame with the suffix '_reversed'.

    Returns
    -------
    pd.DataFrame
        Input pandas DataFrame with added facets and reverse-scored
        items if provided.

    Raises
    ------
    KeyError
        If one or more item columns referenced in `facet_item_map` are
        missing from `df`.
    """
    required_items = {key for keys in facet_item_map.values() for key in keys}
    missing = sorted(required_items - set(df.columns))
    if missing:
        raise KeyError(f"Missing expected item column(s) in DataFrame: {missing}")
 
    working_df = df.copy()

    if reverse_coded_items:
        working_df[reverse_coded_items] = 6 - working_df[reverse_coded_items]
        reversed_items = working_df[reverse_coded_items].add_suffix("_reversed")  
 
    facet_scores = {
        facet_code: working_df[item_keys].mean(axis=1).round(1)
        for facet_code, item_keys in facet_item_map.items()
    }
    facet_scores = pd.DataFrame(facet_scores)  

    # Merge dfs
    df = pd.concat([df, facet_scores], axis=1)

    # Reorder cols
    cols = list(df.columns)
    end_cols = [item for sublist in facet_item_map.values() for item in sublist]
    rest_cols = [c for c in cols if c not in end_cols]
    df = df[rest_cols + end_cols]

    if reverse_coded_items:
        df = pd.concat([df, reversed_items], axis=1)

    return df


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Imports necessary for testing
    from typing import Annotated
    from pydantic import BaseModel, Field
    from dotenv import load_dotenv

    # Load key
    load_dotenv()
    OPENAI_KEY = os.environ["OPENAI_KEY"]

    # Generate testing data
    test_df = pd.DataFrame({
        "participant_id": ["123", "456", "789", "147", "258"],
        "poem": [
            """
            Morning light spills gold,
            A sparrow wakes the quiet street,
            Day begins to bloom.
            """,
            """
            Rain taps softly on the glass,
            Streetlights shimmer in the grey,
            Night hums low and warm.
            """,
            """
            An old tree holds the moon,
            Its branches whisper to the wind,
            Winter waits below.
            """,
            """
            old home
            the light we'd leave
            on, off.
            """,
            """
            beam by beam
            the old barn taken down
            to sky
            """
        ]
    })

    system_prompt = """
        You are a poetry evaluator. Rate the poem on imagery, rhythm, and originality.
        Use a scale from 1 to 5, where 1 is very poor and 5 is excellent.
        """

    Rating = Annotated[
        int,
        Field(ge=1, le=5, description="Rating from 1 (very poor) to 5 (excellent).",
        ),
    ]

    class PoemRating(BaseModel):
        imagery: Rating = Field(...,
            description="How vivid, evocative, and effective the poem's imagery is."
        )

        rhythm: Rating = Field(...,
            description="How natural, consistent, and pleasing the poem's rhythm and flow are."
        )

        originality: Rating = Field(...,
            description="How distinctive, creative, and original the poem's ideas and expression are."
        )

    test_rating = rate_df_api(
        df=test_df,
        chat_column="poem",
        identifier_column="participant_id",
        system_prompt=system_prompt,
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
        api_key=OPENAI_KEY,
        response_format=PoemRating,
        label="test_rating"
    )

    facet_item_map = {
        "artistic_ability": ["imagery", "rhythm", "originality"]
    }

    reverse_coded_items = ["imagery"]

    test_rating = calculate_facet_scores(test_rating, facet_item_map, reverse_coded_items)
    test_rating["condition"] = ["high", "low", "high", "high", "low"]