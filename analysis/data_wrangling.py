"""
data_wrangling.py — Data Loading, Cleaning & Merging Pipeline
=====================================================================

End-to-end pipeline that loads the raw study data sources, cleans and
harmonizes each one, and merges them into a single participant-level
dataset for analysis.

Data sources processed:
- Interviews (df_interviews): chatbot interview transcripts and metadata,
  built from raw interview files; includes AI-generated ad hoc facet
  assessments.
- Fremdurteil (df_fremdurteil): external-rater personality ratings of
  interviewees, incl. rater demographics, item-level TSDI ratings, and
  qualitative rater comments.
- Coding sheet (df_coding): manual coding of interview quality/completeness
  and adherence to structured/open interview protocols.
- Selbstbericht (df_selbstbericht): participants' own self-report TSDI/HEXACO
  questionnaire responses, linked via a separate matriculation-number file.

Pipeline steps:
1. Load: Read all raw data sources (interview files, fremdurteil ratings,
   coding sheet, self-report CSV, and matrikelnummer lookup) and optionally
   persist raw snapshots to CSV.
2. Clean: For each source — drop participants without research consent,
   disambiguate duplicate participant/rater IDs, remove sensitive data
   (matrikelnummer) rename/remap columns to canonical facet and item IDs
   (via MAPPING_FACETS_ABBR from config.py), reorder columns, fix known
   data-entry issues, and cast boolean flags to int. Cleaned frames are
   optionally saved to CSV.
3. Merge: Sample one fremdurteil rating per participant, prefix
   source-specific item/mean columns to avoid collisions, and left-merge
   interviews, fremdurteil, coding, and self-report data into a single
   wide dataframe keyed on participant_id, saved as the final merged
   output CSV.

Inputs:  DATA_DIR (interview_files.txt, forschungsdaten/, fremdurteil/,
         coding_sheet_interviews.xlsx, personality_final.csv,
         wilhelm_dia_uebung_26_t1_matrikelnummer_raw_2606181559.csv)
Outputs: df_interviews_cleaned.csv, df_fremdurteile_cleaned.csv,
         df_coding_cleaned.csv, df_selbstberichte_cleaned.csv,
         df_merged_cleaned.csv (see path constants below; raw snapshots
         are also written if SAVE_RAW_DF is True)

Run directly via `python data_wrangling.py`.
"""
import os
from pathlib import Path

import pandas as pd
import numpy as np

from utils import (
    build_dataframe,
    read_fremdurteil,
    differentiate_duplicate_ids,
    extract_filename_ids,
    transform_multi_column_values
)

from config import (
    MAPPING_FACETS_ABBR
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

### Input paths ###
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = ROOT_DIR / "data"

### Output paths ###
DF_INTERVIEWS_RAW_OUT_PATH = DATA_DIR / 'df_interviews_raw.csv'
DF_FREMDURTEILE_RAW_OUT_PATH = DATA_DIR / 'df_fremdurteile_raw.csv'

DF_INTERVIEWS_CLEANED_OUT_PATH = DATA_DIR / 'df_interviews_cleaned.csv'
DF_FREMDURTEILE_CLEANED_OUT_PATH = DATA_DIR / 'df_fremdurteile_cleaned.csv'
DF_CODING_CLEANED_OUT_PATH = DATA_DIR / 'df_coding_cleaned.csv'
DF_SELBST_CLEANED_OUT_PATH = DATA_DIR / 'df_selbstberichte_cleaned.csv'

DF_MERGED_OUT_PATH = DATA_DIR / 'df_merged_cleaned.csv'

### Controls ###
SAVE_RAW_DF = False
SAVE_CLEANED_DF = True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # ── Step 1: Load data ──────────────────────────────────────────────────
    print(f"[1/3] Loading data...")

    df_interviews, identifiers = build_dataframe(list_path=DATA_DIR / "interview_files.txt",
                                                       data_dir=DATA_DIR / "forschungsdaten")
    print(f"  Loaded {len(df_interviews)}/{len(identifiers)} interviews")

    df_fremdurteil, fremdurteil_counts = read_fremdurteil(list_path=DATA_DIR / "interview_files.txt",
                                                                data_dir=DATA_DIR / "fremdurteil")
    print(
        f"  Loaded {fremdurteil_counts['n_rated']} fremdurteil ratings ({fremdurteil_counts['n_missing']} interview(s) without rating; {fremdurteil_counts['n_multiple']} with multiple ratings)"
    )

    df_coding = pd.read_excel(DATA_DIR / "coding_sheet_interviews.xlsx")
    print(f"  Loaded coding file for {len(df_coding)} interviews")

    df_selbstbericht = pd.read_csv(DATA_DIR / "personality_final.csv", sep=";")
    print(f"  Loaded {len(df_selbstbericht)} selbstbericht ratings")

    selbstbericht_matr_nr = pd.read_csv(DATA_DIR / "wilhelm_dia_uebung_26_t1_matrikelnummer_raw_2606181559.csv", sep=";")

    # Save raw dfs
    if SAVE_RAW_DF:
        df_interviews.to_csv(DF_INTERVIEWS_RAW_OUT_PATH, index=False)
        print(f"  Saved raw interview data at {DF_INTERVIEWS_RAW_OUT_PATH}")
        
        df_fremdurteil.to_csv(DF_FREMDURTEILE_RAW_OUT_PATH, index=False)
        print(f"  Saved raw fremdurteil data at {DF_FREMDURTEILE_RAW_OUT_PATH}")


    # ── Step 2: Data cleaning ──────────────────────────────────────────────
    print(f"[2/3] Data cleaning...")
    
    ### df_interviews ###

    # drop all participants without research consent
    num_df_raw = len(df_interviews)
    df_interviews = df_interviews[df_interviews["research_consent"]]
    print(f"  Dropped {num_df_raw - len(df_interviews)} participants in df_interview due to missing research consent")

    # check for duplicate participant_ids, add _<count> to duplicates
    df_interviews = differentiate_duplicate_ids(df_interviews, participant_id_column="participant_id", identifier_column="matrikelnummer")

    # drop matrikelnummer
    # df_interviews = df_interviews.drop(columns="matrikelnummer")

    # calculate timing_duration_interview_seconds from timing_interview_last_interaction
    # if missing and possible
    start = pd.to_datetime(df_interviews["timing_interview_start_time"], format="%Y-%m-%d_%H:%M:%S", errors="coerce")
    last = pd.to_datetime(df_interviews["timing_interview_last_interaction"], format="%Y-%m-%d_%H:%M:%S", errors="coerce")

    calculated_seconds = (last - start).dt.total_seconds()

    df_interviews["timing_duration_interview_seconds"] = np.where(
        df_interviews["timing_duration_interview_seconds"].isna(),
        calculated_seconds,
        df_interviews["timing_duration_interview_seconds"]
    )

    # fix ai_assessment_Rücksichtnahme and drop ai_assessment_Rücksicht**s**nahme
    df_interviews["ai_assessment_Rücksichtnahme"] = df_interviews["ai_assessment_Rücksichtnahme"].fillna(
        df_interviews["ai_assessment_Rücksichtsnahme"]
    )

    df_interviews = df_interviews.drop(columns="ai_assessment_Rücksichtsnahme")

    # map ai_assessment column names to abbr.
    df_interviews.columns = [
        f"ai_assessment_{MAPPING_FACETS_ABBR[col.removeprefix('ai_assessment_')]}"
        if col.startswith("ai_assessment_")
        else col
        for col in df_interviews.columns
    ]

    # reorder columns
    cols = list(df_interviews.columns)
    front_cols = [
        "participant_id",
        "research_consent",
        "complete_session",
        "condition",
        "chat_text",
        "timing_duration_interview_seconds",
        "timing_duration_experiment_seconds"
    ]

    rest_cols = [c for c in cols if c not in front_cols]
    df_interviews = df_interviews[front_cols + rest_cols]

    # drop facet count variables
    df_interviews = df_interviews.loc[:, ~df_interviews.columns.str.startswith("count_facet")]

    # transform bool to int
    df_interviews["research_consent"] = df_interviews["research_consent"].astype(int)
    df_interviews["complete_session"] = df_interviews["complete_session"].astype(int)

    # check interview durations
    # df_interviews.loc[df_interviews["condition"] == ("structured-write" or "structured-speech"), "timing_duration_interview_seconds"].hist(bins=30)
    # df_interviews.loc[df_interviews["condition"] != ("structured-write" or "structured-speech"), "timing_duration_interview_seconds"].hist(bins=30)

    # df_interviews.loc[df_interviews["condition"] == ("structured-write" or "open-write"), "timing_duration_interview_seconds"].hist(bins=30)
    # df_interviews.loc[df_interviews["condition"] != ("structured-write" or "open-write"), "timing_duration_interview_seconds"].hist(bins=30)

    # df_interviews.loc[df_interviews["condition"] == "structured-write", "timing_duration_interview_seconds"].hist(bins=30)
    # df_interviews.loc[df_interviews["condition"] == "structured-speech", "timing_duration_interview_seconds"].hist(bins=30)
    # df_interviews.loc[df_interviews["condition"] == "open-write", "timing_duration_interview_seconds"].hist(bins=30)
    # df_interviews.loc[df_interviews["condition"] == "open-speech", "timing_duration_interview_seconds"].hist(bins=30)

    # df_interviews.loc[df_interviews["condition"] == "structured-write", "timing_duration_interview_seconds"].describe()
    # df_interviews.loc[df_interviews["condition"] == "structured-speech", "timing_duration_interview_seconds"].describe()
    # df_interviews.loc[df_interviews["condition"] == "open-write", "timing_duration_interview_seconds"].describe()
    # df_interviews.loc[df_interviews["condition"] == "open-speech", "timing_duration_interview_seconds"].describe()
    # no threshold for conscientious interview behavior detected
    
    ### df_fremdurteil ###

    # rename variables
    df_fremdurteil = df_fremdurteil.rename(columns={
        "Bearbeitung_Start": "timing_rating_start_time",
        "Bearbeitung_Ende": "timing_rating_end_time",
        "Bearbeitungsdauer_Sekunden": "timing_duration_rating_seconds",
        "Rater_VP_Code": "rater_id",
        "Rater_Matrikelnummer": "rater_matrikelnummer",
        "Rater_Alter": "rater_age",
        "Rater_Geschlecht": "rater_gender",
        "Forschungs_Consent": "research_consent",
        "Zugeordneter_Transkript_File": "interview_identifier",
        "Bewerteter_Target_VP_Code": "participant_id",
        "USER_Extraversion": "mean_extraversion",
        "USER_Vertraeglichkeit": "mean_agreeableness",
        "USER_Gewissenhaftigkeit": "mean_conscientiousness",
        "USER_Neurotizismus": "mean_neuroticism",
        "USER_Offenheit": "mean_openness",
        "Freitext_Anmerkungen": "rater_comments",

        "x42i_a_fr_1": "x42i29_a_fr066",
        "x42i_a_fr_2": "x42i14_a_fr084",
        "x42i_a_fr_3": "x42i43_a_fr220",

        "x42i_a_co_1": "x42i02_a_co080",
        "x42i_a_co_2": "x42i26_a_co207",
        "x42i_a_co_3": "x42i27_a_co209",

        "x42i_a_h_1": "x42i12_a_h064",
        "x42i_a_h_2": "x42i48_a_h068",
        "x42i_a_h_3": "x42i46_a_h213",

        "x42i_c_hw_1": "x42i05_c_hw126",
        "x42i_c_hw_2": "x42i30_c_hw137",
        "x42i_c_hw_3": "x42i44_c_hw167",

        "x42i_c_o_1": "x42i18_c_o153",
        "x42i_c_o_2": "x42i49_c_o157",
        "x42i_c_o_3": "x42i39_c_o162",

        "x42i_e_a_1": "x42i42_e_a002",
        "x42i_e_a_2": "x42i35_e_a004",
        "x42i_e_a_3": "x42i03_e_a009",

        "x42i_e_sb_1": "x42i23_e_sb010",
        "x42i_e_sb_2": "x42i10_e_sb014",
        "x42i_e_sb_3": "x42i22_e_sb026",

        "x42i_e_so_1": "x42i40_e_so007",
        "x42i_e_so_2": "x42i32_e_so012",
        "x42i_e_so_3": "x42i20_e_so028",

        "x42i_n_d_1": "x42i09_n_d039",
        "x42i_n_d_2": "x42i19_n_d054",
        "x42i_n_d_3": "x42i37_n_d055",

        "x42i_n_ir_1": "x42i11_n_ir034",
        "x42i_n_ir_2": "x42i06_n_ir058",
        "x42i_n_ir_3": "x42i07_n_ir070",

        "x42i_n_st_1": "x42i36_n_st037",
        "x42i_n_st_2": "x42i45_n_st040",
        "x42i_n_st_3": "x42i13_n_st043",

        "x42i_o_in_1": "x42i38_o_in094",
        "x42i_o_in_2": "x42i28_o_in106",
        "x42i_o_in_3": "x42i33_o_in118",

        "x42i_o_r_1": "x42i21_o_r100",
        "x42i_o_r_2": "x42i50_o_r117",
        "x42i_o_r_3": "x42i41_o_r120",

        "x42i_o_sc_1": "x42i01_o_sc116",
        "x42i_o_sc_2": "x42i16_o_sc103",
        "x42i_o_sc_3": "x42i25_o_sc114",

        "x42i_hh_si_1": "x42i47_hh_si001",
        "x42i_hh_si_2": "x42i15_hh_si005",
        "x42i_hh_si_3": "x42i04_hh_si009",

        "x42i_hh_fa_1": "x42i31_hh_fa006",
        "x42i_hh_fa_2": "x42i17_hh_fa010",
        "x42i_hh_fa_3": "x42i08_hh_fa002",

        "x42i_hh_mo_1": "x42i24_hh_mo016",
        "x42i_hh_mo_2": "x42i34_hh_mo004",
        "x42i_hh_mo_3": "x42i51_hh_mo008",
    })

    # drop participants without research consent
    num_df_raw = len(df_fremdurteil)
    df_fremdurteil = df_fremdurteil[df_fremdurteil["research_consent"].astype(bool)]
    print(f"  Dropped {num_df_raw - len(df_fremdurteil)} participants in df_fremdurteil due to missing research consent")

    # extract information from interview_identifier
    df_fremdurteil = extract_filename_ids(df_fremdurteil, filename_column="interview_identifier")

    # add unique num to participant and rater ids
    df_fremdurteil = differentiate_duplicate_ids(df_fremdurteil, participant_id_column="participant_id", identifier_column="student_id")
    df_fremdurteil = differentiate_duplicate_ids(df_fremdurteil, participant_id_column="rater_id", identifier_column="rater_matrikelnummer")

    # drop all columns with matrikelnummer
    df_fremdurteil = df_fremdurteil.drop(columns=[
        "rater_matrikelnummer",
        "student_id",
        "interview_identifier"
    ])

    # drop Zeitstempel (redundant with timing_rating_end_time) and AI_Extraversion, ... (variables contain no values (all missing data))
    df_fremdurteil = df_fremdurteil.drop(columns=[
        "Zeitstempel",
        "AI_Extraversion",
        "AI_Vertraeglichkeit",
        "AI_Gewissenhaftigkeit",
        "AI_Neurotizismus",
        "AI_Offenheit"
    ])

    # add uncompliant behavior according to rater comments
    df_fremdurteil["interviewee_not_conscientious"] = pd.NA

    cols = list(df_fremdurteil.columns)
    front_cols = [
        "participant_id",
        "rater_comments",
        "interviewee_not_conscientious"
    ]

    rest_cols = [c for c in cols if c not in front_cols]
    df_fremdurteil = df_fremdurteil[front_cols + rest_cols]

    df_fremdurteil.loc[df_fremdurteil["participant_id"] == "03AYRD23_58", "interviewee_not_conscientious"] = 1
    df_fremdurteil.loc[df_fremdurteil["participant_id"] == "05LDAS12_71", "interviewee_not_conscientious"] = 1
    df_fremdurteil.loc[df_fremdurteil["participant_id"] == "07RTAS23_56", "interviewee_not_conscientious"] = 1
    df_fremdurteil.loc[df_fremdurteil["participant_id"] == "08STAS12_58", "interviewee_not_conscientious"] = 1
    df_fremdurteil.loc[df_fremdurteil["participant_id"] == "07ESUD17_61", "interviewee_not_conscientious"] = 1

    # add condition
    df_fremdurteil = df_fremdurteil.merge(df_interviews[["participant_id", "condition"]], on="participant_id", how="left")

    # reorder columns
    cols = list(df_fremdurteil.columns)
    front_cols = [
        "participant_id",
        "condition",
        "research_consent",
        "complete_session",
        "timing_duration_rating_seconds",
        "rater_id",
        "rater_comments",
        "interviewee_not_conscientious",
        "mean_extraversion",
        "mean_agreeableness",
        "mean_conscientiousness",
        "mean_neuroticism",
        "mean_openness"
    ]

    rest_cols = [c for c in cols if c not in front_cols]
    df_fremdurteil = df_fremdurteil[front_cols + rest_cols]

    # transform bool to int
    df_fremdurteil["research_consent"] = df_fremdurteil["research_consent"].astype(int)
    df_fremdurteil["complete_session"] = df_fremdurteil["complete_session"].astype(int)

    # check rating durations
    # df_fremdurteil.loc[df_fremdurteil["condition"] == ("structured-write" or "structured-speech"), "timing_duration_rating_seconds"].hist(bins=100)
    # df_fremdurteil.loc[df_fremdurteil["condition"] != ("structured-write" or "structured-speech"), "timing_duration_rating_seconds"].hist(bins=30)

    # df_fremdurteil.loc[df_fremdurteil["condition"] == ("structured-write" or "open-write"), "timing_duration_rating_seconds"].hist(bins=100)
    # df_fremdurteil.loc[df_fremdurteil["condition"] != ("structured-write" or "open-write"), "timing_duration_rating_seconds"].hist(bins=30)

    # df_fremdurteil.loc[df_fremdurteil["condition"] == "structured-write", "timing_duration_rating_seconds"].hist(bins=100)
    # df_fremdurteil.loc[df_fremdurteil["condition"] == "structured-speech", "timing_duration_rating_seconds"].hist(bins=30)
    # df_fremdurteil.loc[df_fremdurteil["condition"] == "open-write", "timing_duration_rating_seconds"].hist(bins=30)
    # df_fremdurteil.loc[df_fremdurteil["condition"] == "open-speech", "timing_duration_rating_seconds"].hist(bins=30)

    # df_fremdurteil.loc[df_fremdurteil["condition"] == "structured-write", "timing_duration_rating_seconds"].describe()
    # df_fremdurteil.loc[df_fremdurteil["condition"] == "structured-speech", "timing_duration_rating_seconds"].describe()
    # df_fremdurteil.loc[df_fremdurteil["condition"] == "open-write", "timing_duration_rating_seconds"].describe()
    # df_fremdurteil.loc[df_fremdurteil["condition"] == "open-speech", "timing_duration_rating_seconds"].describe()
    # no threshold for conscientious rating behavior detected

    ### Coding sheet ###

    # rename columns
    df_coding = df_coding.rename(columns={
        'Bedingung': 'condition',
        'Vollständigkeit Freitext': 'completeness_text',
        'Vollständigkeit: Dimensionen': 'completeness_dimensions',
        'Vollständigkeit: fehlende Dimensionen': 'completeness_missing_dimensions',
        'Vollständigkeit: Facetten': 'completeness_facets',
        'Vollständigkeit: fehlende Facetten': 'completeness_missing_facets',
        'Vollständigkeit: Items': 'completeness_items',
        'Facetten hinzugefügt?': 'completeness_added_facets',
        'Bei Abbruch: wo hat es abgebrochen, was fehlte? Freitext': 'completeness_missing_constructs_text',
        'Structured: sequenzielle Abfolge\n(= Ist der Bot strikt die einzelnen Items durchgegangen, ohne zu springen?)': 'structured_seq_order',
        'Structured: Ein-Fragen-Regel\n(=Hat der Bot pro Nachricht wirklich immer nur eine Frage gestellt?)': 'structured_one_question_rule',
        'Structured: Phrasen Vermeidung\n(= Hat der Bot verbotene Phrasen genutzt? (z.B. „Wie sehen Sie das bei sich?“, „Vielen Dank“, „Interessant“, „Das tut mir leid“))': 'structured_phrase_avoidance',
        'Structured: Umgang mit Störungen \n(= Wenn der User Gegenfragen gestellt oder Unverständnis geäußert hat: Ist der Bot höflich geblieben und hat die Frage wiederholt?)': 'structured_disruption_handling',
        'Structured: Antwort Detailgrad\n(=wie detailliert antwortet die Person auf die strukturierten Fragen?)': 'structured_answer_lvl_detail',
        'Structured: Anmerkungen Freitext\n(= werden exogene Faktoren benannt, die das Verhalten stark beeinbflussen, z.B. Krankheiten, aktuelle Lebenskrise, extremes Stressumfeld?)': 'structured_comments',
        'Open: Reihenfolge der Dimensionen\n(=hat der Bot die 6 Faktoren in der richtigen Reihenfolge (E, N, C, A, O, HH) abgefragt?)': 'open_seq_dimensions',
        'Open: Ablauf\n(= Hat der Bot pro Dimension die Kette (Beschreibung -> Globaler Vergleich -> Begründung-> Übergang Facette -> Facetten-Vergleich -> Alltag -> Vertiefung) eingehalten?': 'open_seq_within_dimensions',
        'Open: FragenMax\n(=Wurden pro Facette maximal 4 Fragen (inkl. der fixen Fragen) gestellt? Oder hat sich der Bot in einer Facette festgebissen?)': 'open_questions_max',
        'Open: Assessment\n(=Hat der Bot fälschlicherweise nach Lösungen, Tipps, Coaching-Strategien oder Bewältigungsmethoden gefragt? (Das ist strikt verboten))': 'open_coaching_therapy',
        'Open: Adaptivität\n(=Reagiert der Bot in den freien Fragen sinnvoll auf das, was der User zuvor erzählt hat (z.B. Nachhaken bei Widersprüchen)?)': 'open_lvl_adaptivity',
        'Open: Ausnahmen\n(=Wenn der User eine Eigenschaft als extrem beschrieben hat: Hat der Bot nach Ausnahmesituationen gefragt?)': 'open_ask_exceptions',
        'Open: Sättigung\n(=Hat der Bot gemerkt, wenn eine Facette bereits "ausgemessen" war, und elegant übergeleitet?)': 'open_facet_saturation',
        'Open: Liefert der Teilnehmer in Schritt 6a/6b echte, plastische Alltagssituationen oder flüchtet er sich in Floskeln?': 'open_participant_examples_lvl_detail',
        'Open: Widerspricht sich der User im Laufe des offenen Gesprächs selbst?\nFreitext': 'open_participant_contradiction_oneself',
        'Open: Feedback/Evaluation \n(= die KI bewertet die Antworten der Person)': 'open_bot_comments_answers'
    })

    # omit whitespace in values
    df_coding = df_coding.apply(lambda col: col.str.strip() if col.dtype == "object" else col)

    # extract ids from filename_interview
    df_coding = extract_filename_ids(df_coding, filename_column="filename_interview")

    # map facet abbreviations
    df_coding = differentiate_duplicate_ids(df_coding, participant_id_column="participant_id", identifier_column="student_id")

    # unpack multi-value columns
    df_coding = transform_multi_column_values(df_coding, column="completeness_missing_dimensions", id_column="participant_id")

    df_coding = transform_multi_column_values(df_coding, column="completeness_missing_facets", id_column="participant_id", abbriviation_mapping=MAPPING_FACETS_ABBR)

    # add interview_time and research consent
    df_coding = df_coding.merge(
        df_interviews[["participant_id", "research_consent", "timing_duration_interview_seconds"]],
        on="participant_id",
        how="left"
    )

    # reorder columns
    cols = list(df_coding.columns)
    front_cols = [
        "participant_id",
        "research_consent",
        "complete_session",
        "condition",
        "timing_duration_interview_seconds",
        "completeness_dimensions",
        "completeness_missing_dimensions",
        "completeness_missing_dimensions_count",
        "completeness_facets",
        "completeness_missing_facets",
        "completeness_missing_facets_count",
        "completeness_items",
        "completeness_added_facets"
    ]

    rest_cols = [c for c in cols if c not in front_cols]
    df_coding = df_coding[front_cols + rest_cols]

    # drop sensitive columns
    df_coding = df_coding.drop(columns=["filename_interview", "student_id"])

    # drop participants that aren't in df_interviews
    df_coding = df_coding[df_coding["research_consent"] == 1]

    # transform bool to int
    df_coding["research_consent"] = df_coding["research_consent"].astype(int)
    df_coding["complete_session"] = df_coding["complete_session"].astype(int)

    ### Selbstbericht ###
    
    # select columns
    df_selbstbericht = df_selbstbericht[
        ["subject", "vpcode", "einwilligung"] +
        df_selbstbericht.filter(regex=r"^x42").columns.tolist() +
        df_selbstbericht.filter(regex=r"^hex.*\d$").columns.tolist()
    ]

    # merge matrikelnummern
    selbstbericht_matr_nr = selbstbericht_matr_nr[selbstbericht_matr_nr["trialcode"] == "VPcode_text"]
    df_selbstbericht = df_selbstbericht.merge(selbstbericht_matr_nr[["subject", "response"]], on="subject")
    df_selbstbericht["response"] = df_selbstbericht["response"].astype(int).astype(str)

    # merge participant_ids from df_interviews
    df_selbstbericht = df_selbstbericht.merge(df_interviews[["matrikelnummer", "participant_id"]], how="left", left_on="response", right_on="matrikelnummer")

    # Overwrite df_selbstbericht participant_id with df_interviews participant_id
    # if they differ
    parts = df_selbstbericht["vpcode"].str.extract(r"^(\d+)([A-Za-z]+)(\d+)$")
    df_selbstbericht["vpcode"] = (
        parts[0].str.zfill(2) +
        parts[1].str.upper() +
        parts[2].str.zfill(2)
    )

    df_selbstbericht["participant_id"] = df_selbstbericht["participant_id"].str[:-3]

    df_selbstbericht["vpcode"] = np.where(
        (df_selbstbericht["vpcode"] != df_selbstbericht["participant_id"]) & df_selbstbericht["participant_id"].notna(),
        df_selbstbericht["participant_id"],
        df_selbstbericht["vpcode"]        
    )

    # drop merged participant_id and student_id
    df_selbstbericht = df_selbstbericht.drop(columns=[
        "participant_id", "matrikelnummer"
    ])

    # rename variables
    df_selbstbericht = df_selbstbericht.rename(columns={
        "response": "matrikelnummer",
        "vpcode": "participant_id",
        "einwilligung": "research_consent"
    })

    # drop participants without research consent
    num_df_raw = len(df_selbstbericht)
    df_selbstbericht = df_selbstbericht[df_selbstbericht["research_consent"].astype(bool)]
    print(f"  Dropped {num_df_raw - len(df_selbstbericht)} participants in df_selbstbericht due to missing research consent")

    # add unique num to participant and rater ids
    df_selbstbericht = differentiate_duplicate_ids(df_selbstbericht, participant_id_column="participant_id", identifier_column="matrikelnummer")

    # drop subject and student_id
    df_selbstbericht = df_selbstbericht.drop(columns=[
        "subject",
        "matrikelnummer"
    ])

    # reorder columns
    cols = list(df_selbstbericht.columns)
    front_cols = [
        "participant_id",
        "research_consent"
    ]

    tsdi_items = df_selbstbericht.filter(regex=r"^x42").columns.sort_values(key=lambda col: col.str.split("_").str[1:]).to_list()
    hex_items = df_selbstbericht.filter(regex=r"^hex").columns.sort_values().to_list()

    rest_cols = [c for c in cols if c not in front_cols + tsdi_items + hex_items]
    df_selbstbericht = df_selbstbericht[front_cols + tsdi_items + hex_items + rest_cols]

    # transform bool to int
    df_selbstbericht["research_consent"] = df_selbstbericht["research_consent"].astype(int)

    ### Save cleaned data ###

    # Drop student_id from df_interviews
    df_interviews = df_interviews.drop(columns="matrikelnummer")

    if SAVE_CLEANED_DF:
        df_interviews.to_csv(DF_INTERVIEWS_CLEANED_OUT_PATH, index=False)
        print(f"  Saved cleaned interview data at {DF_INTERVIEWS_CLEANED_OUT_PATH}")
        
        df_fremdurteil.to_csv(DF_FREMDURTEILE_CLEANED_OUT_PATH, index=False)
        print(f"  Saved cleaned fremdurteil data at {DF_FREMDURTEILE_CLEANED_OUT_PATH}")

        df_coding.to_csv(DF_CODING_CLEANED_OUT_PATH, index=False)
        print(f"  Saved cleaned coding data at {DF_CODING_CLEANED_OUT_PATH}")

        df_selbstbericht.to_csv(DF_SELBST_CLEANED_OUT_PATH, index=False)
        print(f"  Saved cleaned selbstbericht data at {DF_SELBST_CLEANED_OUT_PATH}")


    # ── Step 3: Merge data ─────────────────────────────────────────────────
    print(f"[3/3] Merging cleaned data...")

    # sample one rating per participant from df_fremdurteil
    df_fremdurteil = (
        df_fremdurteil.groupby("participant_id", group_keys=False)
        .sample(n=1, random_state=42)
    )

    # drop duplicate columns in df_fremdurteil, df_coding and df_selbstbericht
    df_fremdurteil = df_fremdurteil.drop(columns={"complete_session", "research_consent", "condition"})
    df_coding = df_coding.drop(columns={"complete_session", "condition", "research_consent", "timing_duration_interview_seconds"})
    df_selbstbericht = df_selbstbericht.drop(columns={"research_consent"})

    # Add prefix to certain columns to make them unequivocal
    mask = df_fremdurteil.columns.str.startswith(("x42", "mean"))
    df_fremdurteil.columns = df_fremdurteil.columns.where(~mask, "fremd_" + df_fremdurteil.columns)

    mask = df_selbstbericht.columns.str.startswith(("x42", "hex"))
    df_selbstbericht.columns = df_selbstbericht.columns.where(~mask, "selbst_" + df_selbstbericht.columns)

    # merge dfs on participant_id; drop all participants who were not present in df_interviews
    df_merged = df_interviews.merge(df_fremdurteil, on="participant_id", how="left")
    df_merged = df_merged.merge(df_coding, on="participant_id", how="left")
    df_merged = df_merged.merge(df_selbstbericht, on="participant_id", how="left")

    ### Save merged data ###
    df_merged.to_csv(DF_MERGED_OUT_PATH, index=False)
    print(f"  Saved merged data frame at {DF_MERGED_OUT_PATH}")


if __name__ == "__main__":
    main()
