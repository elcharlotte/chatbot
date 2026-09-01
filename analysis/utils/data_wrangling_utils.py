"""
data_wrangling_utils.py — Helpers for Loading & Reshaping Study Data
=======================================================================

Utility functions used by the data-wrangling pipeline (data_wrangling.py)
to load raw interview/fremdurteil files from disk and reshape messy,
multi-valued or nested columns into clean, analysis-ready DataFrame columns.

Function groups:
- Loading interviews: `read_identifiers`, `load_interview`, `process_chat`,
  `flatten_dict`, and `build_dataframe` read the per-participant interview
  JSON files listed in interview_files.txt, extract the chat transcript
  and per-facet message counts, flatten nested metadata fields, and
  assemble everything into a single interviews DataFrame.
- Loading external ratings: `read_fremdurteil` locates and concatenates all
  external-rater ("Fremdurteil") CSV files matching the study's interview
  identifiers, reporting how many identifiers had zero, one, or multiple
  matching rating files.
- ID handling: `extract_filename_ids` parses participant/student IDs (and a
  session-completeness flag) out of interview filenames;
  `differentiate_duplicate_ids` appends a deterministic, identifier-derived
  numeric suffix to every value in an ID column so that IDs are unique
  and reproducible across runs (despite the name, it is applied to all
  rows, not only duplicated ones).
- Multi-value columns: `unpack_column` explodes a delimited string column
  (optionally expanding abbreviations first) into one row per value;
  `count_missing_constructs` and `join_unpacked_column` aggregate an
  unpacked column back down to per-identifier counts or lists;
  `transform_multi_column_values` combines all three to turn a raw
  semicolon-separated string column into a column of lists plus a count
  column, in a single call.

Run directly (`python data_wrangling_utils.py`) to execute a small smoke
test of the filename-parsing and multi-value-column functions using
inline dummy data.
"""

import json
from pathlib import Path

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def build_dataframe(list_path: Path,
                    data_dir: Path) -> tuple[pd.DataFrame, list[str]]:
    """
    Utilize read_identifiers() and load_interview() to read all interview
    data and build data frame.

    Parameters
    ----------
    list_path : pathlib.Path
        Path to file with all identifiers, i.e., interview_files.txt.
    data_dir : pathlib.Path
        Path to directory with all interview data.

    Returns
    -------
    tuple[pd.DataFrame, list[str]]
        - pd.DataFrame df: Build data frame.
        - list[str] identifiers: list of all identifiers.
    """

    identifiers = read_identifiers(list_path)
 
    rows = []
    errors = []
    for identifier in identifiers:
        try:
            rows.append(load_interview(identifier, data_dir))
        except FileNotFoundError as e:
            errors.append(str(e))
 
    if errors:
        print(f"  [Warning] {len(errors)} file(s) could not be loaded:")
        for e in errors:
            print(f"    - {e}")
 
    # Collect the set of all facet numbers seen across all interviews, so
    # every row gets the same set of facet count columns (NA if a
    # participant never had an assistant message for that facet).
    all_facets = sorted({facet for row in rows for facet in row["_facet_counts"]},
                         key=lambda x: (str(type(x)), x))
 
    for row in rows:
        facet_counts = row.pop("_facet_counts")
        for facet in all_facets:
            row[f"count_facet_{facet}"] = facet_counts.get(facet, np.nan)
 
    df = pd.DataFrame(rows)

    return df, identifiers


def read_fremdurteil(list_path: Path,
                      data_dir: Path) -> tuple[pd.DataFrame, dict]:
    """
    Read all fremdurteil CSVs whose file name ends with an identifier
    listed in interview_files.txt.
 
    Each CSV has one header row and one data row (semicolon-separated).
    File names look like '<prefix>_<identifier>.csv' - the identifier is
    only the suffix, with a varying prefix. A single identifier
    can match zero, one, or multiple files (e.g. multiple raters
    rating the same target participant); all matches found are read and
    included.

    Parameters
    ----------
    list_path : pathlib.Path
        Path to file with all identifiers, i.e., interview_files.txt.
    data_dir : pathlib.Path
        Path to directory with all fremdurteil data.

    Returns
    -------
    tuple[pd.DataFrame, dict]
    - pd.DataFrame df: all matched CSVs concatenated into one DataFrame.
    - dict counts: a dict with
        - "n_rated": number of unique identifiers with >=1 rating file
        - "n_missing": number of unique identifiers with 0 rating files
        - "n_multiple": number of unique identifiers with >1 rating files
    """
    identifiers = read_identifiers(list_path)
 
    dfs = []
    missing = []
    multiple = []
    n_matches_per_identifier: dict = {}
 
    for identifier in identifiers:
        matches = sorted(data_dir.glob(f"*{identifier}.csv"))
        n_matches_per_identifier[identifier] = len(matches)
 
        if len(matches) == 0:
            missing.append(identifier)
            continue
        if len(matches) > 1:
            multiple.append((len(matches), identifier))
 
        for csv_path in matches:
            dfs.append(pd.read_csv(csv_path, sep=";", na_values="Keine Angabe"))
 
    if missing:
        print(f"  [Warning] {len(missing)} interview(s) had no fremdurteil file:")
        for m in missing:
            print(f"    - {m}")
    if multiple:
        print(f"  [Note] {len(multiple)} interview(s) had multiple fremdurteil files:")
        for m in multiple:
            print(f"    - {m[0]} ratings for {m[1]}")
 
    counts = {
        "n_rated": sum(1 for n in n_matches_per_identifier.values() if n >= 1),
        "n_missing": sum(1 for n in n_matches_per_identifier.values() if n == 0),
        "n_multiple": sum(1 for n in n_matches_per_identifier.values() if n > 1),
    }
 
    df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    return df, counts


def extract_filename_ids(df: pd.DataFrame,
                         filename_column: str,
                         pattern: str = r"^interview_(?P<participant_ids>.+?)_(?P<student_ids>[^_]+)(?P<preliminary>_preliminary)?\.json$",
                         participant_id_column: str = "participant_id",
                         student_id_column: str = "student_id",
                         complete_session_column: str = "complete_session") -> pd.DataFrame:
    """
    Parse `column` (format: "interview_<interview_code>_<VP_code>.json", with
    an optional "_preliminary" marker before ".json"), into three new columns:
    `participant_id`, `student_id`, and `complete_session` (bool), appended to a
    copy of df.

    Parameters
    ----------
    df : pd.DataFrame
        A pandas DataFrame to be processed.
    filename_column : str
        Name of filename column.
    pattern : str
        Pattern of filename column. Defaults to
        'interview_<participant_ids>_<student_ids><_preliminary.json/.json>'.
    participant_id_column : str
        Name of generated participant_id column. Defaults to `participant_id`.
    student_id_column : str
        Name of generated student_id column. Defaults to `student_id`.
    complete_session_column : str
        Name of generated complete_session column. Defaults to `complete_session`.

    Returns
    -------
    pd.DataFrame
        Copy of input pd.DataFrame with generated columns appended.
    """
    df = df.copy()
    extracted = df[filename_column].str.extract(pattern)
    df[participant_id_column] = extracted["participant_ids"]
    df[student_id_column] = extracted["student_ids"]
    df[complete_session_column] = extracted["preliminary"].isna()

    n_unmatched = extracted["participant_ids"].isna().sum()
    if n_unmatched:
        print(f"  [!] Warning: {n_unmatched} value(s) in '{filename_column}' didn't match the expected filename pattern")

    return df


def differentiate_duplicate_ids(df: pd.DataFrame,
                                participant_id_column: str,
                                identifier_column: str) -> pd.DataFrame:
    """
    Standardize participant_ids and append a deterministic numeric suffix
    to every row.

    Standardization consists of two steps applied to `participant_id_column`:
    1. Upper-casing all letters.
    2. Zero-padding every contiguous run of digits to a minimum width of
       two, e.g. "7aras08" -> "07ARAS08" and "7aras8" -> "07ARAS08".
       This normalizes IDs that differ only in whether a single-digit
       number was zero-padded in the source data.

    After standardization, a suffix is appended: the cross sum (sum of
    digits) of 15 pseudo-random digits, generated from a seeded RNG whose
    seed is derived from the unambiguous `identifier_column` value (e.g.
    student_id) - so the same identifier always produces the same suffix,
    and different participant_ids sharing the same underlying identifier
    collapse onto the same suffixed ID. This effectively guarantees
    globally unique, reproducible participant IDs without needing to
    explicitly detect which rows are duplicates.

    Parameters
    ----------
    df : pd.DataFrame
        A pandas DataFrame to be processed. Modified in place.
    participant_id_column : str
        Name of participant_id column. Selected participant_id column will be overwritten
        with standardized, suffixed values.
    identifier_column : str
        Name of the identifier column (e.g. student_id) used to derive the suffix.

    Returns
    -------
    pd.DataFrame
        The input pd.DataFrame (same object, mutated), with participant_ids
        standardized (upper-cased, digits zero-padded to 2) and expanded by suffix.
    """
    import random
    import re

    def pad_digits(value: str) -> str:
        return re.sub(r"\d+", lambda m: m.group(0).zfill(2), value)

    def suffix_from_identifier(value) -> str:
        try:
            rng = random.Random(int(value))
        except ValueError:
            rng = random.Random(int.from_bytes(value.encode("ascii"), "big"))

        digits = [rng.randint(0, 9) for _ in range(15)]

        return str(sum(digits))

    df[participant_id_column] = (
        df[participant_id_column].astype(str).str.upper().apply(pad_digits)
        + "_" + df[identifier_column].apply(suffix_from_identifier)
    )

    return df


def unpack_column(df: pd.DataFrame,
                  column: str,
                  id_column: str,
                  sep: str = ";",
                  abbriviation_mapping: dict[str, str | list[str]] = None
                  ) -> pd.DataFrame:
    """
    'Unpack' a str column that contains multiple values per cell separated by `sep`.

    Returns a new DataFrame where each individual value gets its own row,
    with the identifier column preserved/repeated. Leading/trailing whitespace
    around each value is stripped, and empty values are dropped.

    If sep is set to None, separation step is skipped. The function can handle
    a column of valid list elements that way.

    If abbriciation_mapping is provided, abbriviations get mapped before values
    get separated into individual rows.

    Parameters
    ----------
    df : pd.DataFrame
        A pandas DataFrame to be processed.
    column : str
        Column to be unpacked.
    id_column : str
        Column with identifiers. Used to assign unpacked values to participants/conditions.
    sep : str
        Used separator of values within `column`. Defaults to ';'. If set to None,
        separation step is skipped.
    abbriviation_mapping : dict[str, str | list[str]]
        Dict mapping from abbriviation to list of strings or string; optional.        

    Returns
    -------
    pd.DataFrame
        pd.DataFrame with two columns: identifier and unpacked values.
    """
    temp = df[[id_column, column]].copy()

    # if sep is provided, split on separator
    if sep:
        temp[column] = temp[column].astype(str).str.split(sep)

    # explode turns each list element into its own row
    temp = temp.explode(column)

    # clean whitespace and empty entries
    temp[column] = temp[column].str.strip()
    temp = temp[~temp[column].isin([""])]
    temp[column] = temp[column].replace(
        ["nan", "none", "None", "NaN", "<NA>"],
        None
    )

    # if abbriviation_mapping is provided, map values and explode again
    if abbriviation_mapping:
        temp[column] = temp[column].apply(
            lambda v: abbriviation_mapping[v] if v in abbriviation_mapping else [v]
        )
        temp = temp.explode(column)

    return temp


def transform_multi_column_values(df: pd.DataFrame,
                                column: str,
                                id_column: str,
                                sep: str = ";",
                                abbriviation_mapping: dict[str, str | list[str]] = None,
                                count_values: bool = True) -> pd.DataFrame:
    """
    Transforms a str column that contains multiple values per cell separated by `sep`
    into a column of lists with the values.

    Returns the input DataFrame with column transformed to a column of lists. Leading/
    trailing whitespace around each value is stripped, and empty values are dropped.

    If sep is set to None, separation step is skipped. The function can handle
    a column of valid list elements that way.

    If abbriciation_mapping is provided, abbriviations get mapped before values
    get separated into individual rows.

    If count_values is set to True, an addidional column is appended with the number
    of values in column.

    Parameters
    ----------
    df : pd.DataFrame
        A pandas DataFrame to be processed.
    column : str
        Column to be unpacked.
    id_column : str
        Column with identifiers. Used to assign unpacked values to participants/conditions.
    sep : str
        Used separator of values within `column`. Defaults to ';'. If set to None,
        separation step is skipped.
    abbriviation_mapping : dict[str, str | list[str]]
        Dict mapping from abbriviation to list of strings or string; optional. 
    count_values : bool
        Whether column with number of values within `column` should be added to the 
        DataFrame. Defaults to True.

    Returns
    -------
    pd.DataFrame
        Input pd.DataFrame with manipulated `column` (and additional column <column>_count).
    """
    df = df.copy()

    # unpack column
    unpacked_temp = unpack_column(df=df, column=column, id_column=id_column, sep=sep, abbriviation_mapping=abbriviation_mapping)

    # rejoin unpacked column and overwrite column
    joined_temp = join_unpacked_column(unpacked_temp)
    df[column] = joined_temp[column]

    # if count_values, add column with counts
    if count_values:
        counts_temp = count_missing_constructs(unpacked_temp)
        df[f"{column}_count"] = counts_temp[column]

    return df


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def read_identifiers(list_path: Path) -> pd.Series:
    """
    Read the list of identifiers from interview_files.txt and strip '.json'.
    
    Parameters
    ----------
    list_path : pathlib.Path
        pathlib Path to txt file with identifiers.
    
    Returns
    -------
    pd.Series
        Series of identifier strings, named after the source column.
    """
    df_list = pd.read_csv(list_path, sep=r"\s+", engine="python")
 
    id_col = df_list.columns[0]
    identifiers = df_list[id_col].astype(str).str.strip('"')
    identifiers = identifiers.str.replace(r"\.json$", "", regex=True)
    identifiers.name = id_col.strip('"')

    return identifiers


def process_chat(chat_entries: list[dict]) -> tuple[str, dict]:
    """
    Process the chat turns of one interview.

    Parameters
    ----------
    chat_entries : list[dict]
        JSON type dict in the form of '{role: ..., content: ...}, {...}'.
 
    Returns
    -------
    tuple[str, dict]
        - str chat_text: turns concatenated as "<role>: <content>\n", skipping
        system turns. 'aktuelle_facette' is stripped from `chat_text`.
        - dict facet_counts: a dict mapping each facet number ("aktuelle_facette")
        seen on an assistant turn to the number of assistant messages with
        that facet number.
    """
    lines = []
    facet_counts: dict = {}
    for turn in chat_entries or []:
        role = turn.get("role", "")
        if role == "system":
            continue
        content = turn.get("content", "")
 
        # content may be: a plain string, a JSON-encoded string holding a
        # dict, or (defensively) an already-parsed dict.
        parsed = None
        if isinstance(content, dict):
            parsed = content
        elif isinstance(content, str):
            stripped = content.strip()
            if stripped.startswith("{"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    print(f"  [Warning] Chat message parsing failed in interview")
                    parsed = None
 
        if isinstance(parsed, dict):
            facet = parsed.get("aktuelle_facette")
            if facet is not None:
                facet_counts[facet] = facet_counts.get(facet, 0) + 1
            content = parsed.get("interviewer_text", "")
            if content is None:
                print(f"  [Warning] Empty message")

        if isinstance(content, str):
            # Replace literal newlines with a space and collapse any
            # resulting repeated whitespace, then trim the ends.
            content = " ".join(content.split())
 
        lines.append(f"{role}: {content}")
    
    return "\n".join(lines), facet_counts


def flatten_dict(d: dict,
                 parent_key: str = "",
                 sep: str = "_") -> dict:
    """
    Recursively unpack nested dicts into separate columns.
    E.g. {"timing": {"start": ..., "end": ...}} becomes
    {"timing_start": ..., "timing_end": ...}. Scalars and lists are kept
    as-is.

    Parameters
    ----------
    d : dict
        Dict to unpack.
    parent_key : str
        Parent key of dict to unpack, e.g., 'timing' in the case of a dict
        {"timing": {"start": ..., ...}}. Defaults to "".
    sep : str
        Separator used to join parent key with key. Defaults to '_'.
    
    Returns
    -------
    dict
        Flattened dict.
    """
    items = {}
    for key, value in d.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            items.update(flatten_dict(value, new_key, sep=sep))
        else:
            items[new_key] = value
    
    return items


def load_interview(identifier: str,
                   data_dir: Path) -> dict:
    """
    Load a single participant's JSON file and flatten it into one row.
    
    Parameters
    ----------
    identifier : str
        Identifier of interview. Files to read have to be named as <identifier>.json.

    data_dir : pathlib.Path
        pathlib Path to directory with interviews.

    Returns
    -------
    dict
        Dict with all information from interview file. Additionaly, fields
        `complete_session`, `timing_interview_last_interaction` and `_facet_counts`
        get generated.
    """
    json_path = data_dir / f"{identifier}.json"
    if not json_path.exists():
        raise FileNotFoundError(f"No JSON file found for identifier '{identifier}' at {json_path}")
 
    with open(json_path, "r", encoding="utf-8") as f:
        record = json.load(f)
 
    fields = {key: value for key, value in record.items() if key != "chat"}
    row = flatten_dict(fields)

    chat_entries = record.get("chat", [])
    chat_text, facet_counts = process_chat(chat_entries)
    row["chat_text"] = chat_text
    row["complete_session"] = not json_path.name.endswith("_preliminary.json")
    row["timing_interview_last_interaction"] = (
        chat_entries[-1].get("timestamp") if chat_entries else None
    )    
    row["_facet_counts"] = facet_counts

    return row


def count_missing_constructs(unpacked_column: pd.DataFrame) -> pd.DataFrame:
    """
    Count the number of elements per identifier. Takes the output of unpack_column()
    as input.

    Parameters
    ----------
    unpacked_column : pd.DataFrame
        Output of unpack_column().

    Returns
    -------
    pd.DataFrame
        pd.DataFrame with two columns: passed identifier and count of missing constructs.
    """
    temp = unpacked_column.copy()
    temp = temp.groupby(temp.columns[0], as_index=False, sort=False)[temp.columns[1]].count()

    return temp


def join_unpacked_column(unpacked_column: pd.DataFrame) -> pd.DataFrame:
    """
    Join the output of unpack_columns() to lists within identifiers. Keeps None values
    unlisted.

    Parameters
    ----------
    unpacked_column : pd.DataFrame
        Output of unpack_column().
    
    Returns
    -------
    pd.DataFrame
        pd.DataFrame with two columns: passed identifier and lists of missing constructs.
    """
    temp = unpacked_column.copy()
    temp = temp.groupby(temp.columns[0], as_index=False, sort=False)[temp.columns[1]].apply(
        lambda values: None if len(values) == 1 and pd.isna(values.iloc[0]) else list(values)
    )

    return temp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # extract_filename_ids
    test_df = pd.DataFrame({"filename_interview": ["interview_ABCD123_741852.json", "interview_DEFG123_963852_preliminary.json", "interview_ABCD123_741853.json"]})
    test_df = extract_filename_ids(df=test_df,filename_column="filename_interview")

    # differentiate_duplicate_ids
    test_df = differentiate_duplicate_ids(test_df, "participant_id", "student_id")

    # unpack_column
    test_df["missing_facets"] = [
        "Depression; Aufrichtigkeit; alle C; alle A; ",
        None,
        "keine Angabe "
    ]
    temp = unpack_column(test_df, column="missing_facets", id_column="participant_id")

    # unpack_column
    abbr_mapping = {"alle C": ["Bescheidenheit", "Fleiß"]}
    temp = unpack_column(test_df, column="missing_facets", id_column="participant_id", abbriviation_mapping=abbr_mapping)

    # count_missing_constructs
    missing_constructs_count = count_missing_constructs(temp)

    # join_unpacked_column
    temp = join_unpacked_column(temp)
    test_df = transform_multi_column_values(test_df, column="missing_facets", id_column="participant_id", abbriviation_mapping=abbr_mapping)
    print(type(test_df["missing_facets"].iloc[0]))