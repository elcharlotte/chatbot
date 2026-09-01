"""
config.py — Configuration for the LLM-based TSDI/HEXACO Personality Rating Pipeline
====================================================================================

This module defines the static configuration used to prompt LLMs to rate a
person's personality (Big Five + Honesty-Humility) based on an interview
transcript, following the Trait Self-Descriptive Inventory (TSDI) extended
with the HEXACO Honesty-Humility dimension.

Contents:
- MAPPING_FACETS / MAPPING_FACETS_ABBR: Maps each of the 6 dimensions
  (A, C, E, N, O, HH) to their respective facets, and German facet names/
  abbreviations to their facet codes.
- FACET_ITEM_MAP: Maps each facet (e.g. "a_fr") to its 3 constituent
  questionnaire item IDs.
- ITEMS_LIST / ITEMS_STRING: The full list of 51 questionnaire items (German),
  grouped by dimension and facet, in both Python-list and prompt-ready
  string form.
- REVERSED_CODED_ITEMS: Item IDs that are reverse-scored.
- MODELS: Local and API model definitions (name, key_name, base URL) available
  for running ratings.
- DESCRIPTIONS: German-language descriptions of each dimension and facet,
  used to ground the LLM's understanding before rating.
- LEVELS: Defines the two rating granularities supported — facet-level
  (17 facets, 10–50 scale) and item-level (51 items, 1–5 scale) — along
  with their respective answer-format instructions.
- NORMS: Placeholder(s) for optional normative context to inject into prompts
  (currently a single no-norm baseline).
- RESEARCH_PLAN: Cartesian product of LEVELS x NORMS x ..., each entry
  pairing a combination label with a fully assembled system prompt instructing
  the LLM how to rate the interviewee while controlling for common rating
  biases (interviewer influence, social desirability, halo effect, etc.).
- ItemLevelRatings / FacetLevelRatings: Pydantic models defining the
  structured output schema for item-level (1–5) and facet-level (10–50)
  ratings, used to validate/parse LLM responses.

Note: All items are in German, as informed by the source questionnaire and
intended interview language.
"""
from typing import Annotated
from itertools import product

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Mappings
# ---------------------------------------------------------------------------

# Facet mapping
MAPPING_FACETS = {
    "A": ["A-Fr", "A-Co", "A-H"],
    "C": ["C-Hw", "C-O"],
    "E": ["E-A", "E-SB", "E-So"],
    "N": ["N-D", "N-Ir", "N-St"],
    "O": ["O-In", "O-R", "O-Sc"],
    "HH": ["HH-Si", "HH-Fa", "HH-Mo"],
}

# Facet abbreviation mapping
MAPPING_FACETS_ABBR = {
    "alle A": MAPPING_FACETS["A"],
    "alle C": MAPPING_FACETS["C"],
    "alle E": MAPPING_FACETS["E"],
    "alle HH": MAPPING_FACETS["HH"],
    "alle N": MAPPING_FACETS["N"],
    "alle O": MAPPING_FACETS["O"],
    "alle": MAPPING_FACETS["A"] + MAPPING_FACETS["C"] + MAPPING_FACETS["E"] + MAPPING_FACETS["N"] + MAPPING_FACETS["O"] + MAPPING_FACETS["HH"],

    "Freundlichkeit": "A-Fr",
    "Rücksichtnahme": "A-Co",
    "Hilfsbereitschaft": "A-H",
    "Fleiß": "C-Hw",
    "Organisation": "C-O",
    "Durchsetzungsfähigkeit": "E-A",
    "Selbstbewusstsein": "E-SB",
    "Soziale Aktivität": "E-So",
    "Depression": "N-D",
    "Reizbarkeit": "N-Ir",
    "Nervosität": "N-St",
    "Intellekt": "O-In",
    "Reflexion": "O-R",
    "Wissenschaftliches Interesse": "O-Sc",
    "Aufrichtigkeit": "HH-Si",
    "Fairness": "HH-Fa",
    "Bescheidenheit": "HH-Mo",
}

# Facet-item mapping
FACET_ITEM_MAP = {
    "a_fr": ["x42i29_a_fr066", "x42i14_a_fr084", "x42i43_a_fr220"],
    "a_co": ["x42i02_a_co080", "x42i26_a_co207", "x42i27_a_co209"],
    "a_h": ["x42i12_a_h064", "x42i48_a_h068", "x42i46_a_h213"],
    "c_hw": ["x42i05_c_hw126", "x42i30_c_hw137", "x42i44_c_hw167"],
    "c_o": ["x42i18_c_o153", "x42i49_c_o157", "x42i39_c_o162"],
    "e_a": ["x42i42_e_a002", "x42i35_e_a004", "x42i03_e_a009"],
    "e_sb": ["x42i23_e_sb010", "x42i10_e_sb014", "x42i22_e_sb026"],
    "e_so": ["x42i40_e_so007", "x42i32_e_so012", "x42i20_e_so028"],
    "n_d": ["x42i09_n_d039", "x42i19_n_d054", "x42i37_n_d055"],
    "n_ir": ["x42i11_n_ir034", "x42i06_n_ir058", "x42i07_n_ir070"],
    "n_st": ["x42i36_n_st037", "x42i45_n_st040", "x42i13_n_st043"],
    "o_in": ["x42i38_o_in094", "x42i28_o_in106", "x42i33_o_in118"],
    "o_r": ["x42i21_o_r100", "x42i50_o_r117", "x42i41_o_r120"],
    "o_sc": ["x42i16_o_sc103", "x42i25_o_sc114", "x42i01_o_sc116"],
    "hh_si": ["x42i47_hh_si001", "x42i15_hh_si005", "x42i04_hh_si009"],
    "hh_fa": ["x42i31_hh_fa006", "x42i17_hh_fa010", "x42i08_hh_fa002"],
    "hh_mo": ["x42i51_hh_mo008", "x42i34_hh_mo004", "x42i24_hh_mo016"],
}


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------

# Item list
ITEMS_LIST = [
    # A: Freundlichkeit (A-Fr)
    "x42i29_a_fr066: Man hält mich für jemanden mit dem man einfach gut auskommt.",
    "x42i14_a_fr084: Ich komme mit den meisten Menschen gut zurecht.",
    "x42i43_a_fr220: Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.",

    # A: Rücksichtnahme (A-Co)
    "x42i02_a_co080: Ich behandle andere Leute immer freundlich.",
    "x42i26_a_co207: Ich versuche zu jedem freundlich zu sein, den ich kenne.",
    "x42i27_a_co209: Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.",

    # A: Hilfsbereitschaft (A-H)
    "x42i12_a_h064: Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.",
    "x42i48_a_h068: Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.",
    "x42i46_a_h213: Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.",

    # C: Fleiß (C-Hw)
    "x42i05_c_hw126: Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.",
    "x42i30_c_hw137: Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.",
    "x42i44_c_hw167: Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.",

    # C: Organisation (C-O)
    "x42i18_c_o153: Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.",
    "x42i49_c_o157: Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.",
    "x42i39_c_o162: Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.",

    # E: Durchsetzungsfähigkeit (E-A)
    "x42i42_e_a002: Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.",
    "x42i35_e_a004: Ich neige dazu, in Gruppen die Führung zu übernehmen.",
    "x42i03_e_a009: Ich habe eine Menge Einfluss auf andere Leute.",

    # E: Selbstbewusstsein (E-SB)
    "x42i23_e_sb010: Ich bin eine sehr schüchterne Person.", # inverted
    "x42i10_e_sb014: Meine Freunde halten mich für schüchtern.", # inverted
    "x42i22_e_sb026: Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.", # inverted

    # E: Soziale Aktivität (E-So)
    "x42i40_e_so007: Ich bin gerne wo viel los ist.",
    "x42i32_e_so012: Ich gebe mir große Mühe Leute kennen zu lernen.",
    "x42i20_e_so028: Ich mag Partys auf denen viele Leute sind.",

    # N: Depression (N-D)
    "x42i09_n_d039: Es gibt Zeiten in denen ich mich selbst bedaure.",
    "x42i19_n_d054: Manchmal bin ich entmutigt und möchte am liebsten aufgeben.",
    "x42i37_n_d055: Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.",

    # N: Reizbarkeit (N-Ir)
    "x42i11_n_ir034: Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.",
    "x42i06_n_ir058: Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.",
    "x42i07_n_ir070: Ich kann Kritik nicht sehr gut akzeptieren.",

    # N: Nervosität (N-St)
    "x42i36_n_st037: Ich fühle mich oft müde und erschöpft.",
    "x42i45_n_st040: Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.",
    "x42i13_n_st043: Ich bin oft zittrig und angespannt.",

    # O: Intellekt (O-In)
    "x42i38_o_in094: Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.",
    "x42i28_o_in106: Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.",
    "x42i33_o_in118: Ich besitze ein hohes Maß an intellektueller Neugier.",

    # O: Reflexion (O-R)
    "x42i21_o_r100: Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.",
    "x42i50_o_r117: Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.",
    "x42i41_o_r120: Ich lese gerne Gedichte.",

    # O: Wissenschaftliches Interesse (O-Sc)
    "x42i16_o_sc103: Ich denke oft über die Wunder der Natur nach.",
    "x42i25_o_sc114: Die Evolutionstheorie fasziniert mich.",
    "x42i01_o_sc116: Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.",

    # HH: Aufrichtigkeit (HH-Si)
    "x42i47_hh_si001: Wenn ich von einer Person, die ich nicht mag, etwas will, verhalte ich mich dieser Person gegenüber sehr nett um es zu bekommen.", # inverted
    "x42i15_hh_si005: Ich würde keine Schmeicheleien benutzen, um eine Gehaltserhöhung zu bekommen oder befördert zu werden, auch wenn ich wüsste, dass es erfolgreich wäre.",
    "x42i04_hh_si009: Wenn ich von jemandem etwas will, lache ich auch noch über dessen schlechteste Witze.", # inverted

    # HH: Fairness (HH-Fa)
    "x42i31_hh_fa006: Ich würde in Versuchung geraten, Diebesgut zu kaufen, wenn ich knapp bei Kasse wäre.", # inverted
    "x42i17_hh_fa010: Ich würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.",
    "x42i08_hh_fa002: Wenn ich wüsste, dass ich niemals erwischt werde, wäre ich bereit, eine Million zu stehlen.", # inverted

    # HH: Bescheidenheit (HH-Mo)
    "x42i51_hh_mo008: Ich will nicht, dass andere Leute mich behandeln, als ob ich ihnen überlegen sei.",
    "x42i34_hh_mo004: Ich bin eine ganz normale Person, die nicht besser ist als andere.",
    "x42i24_hh_mo016: Ich will, dass alle wissen, dass ich eine wichtige angesehene Person bin.", # inverted
]

# Reversed-coded items
REVERSED_CODED_ITEMS = [
    "x42i23_e_sb010",
    "x42i10_e_sb014",
    "x42i22_e_sb026",

    "x42i47_hh_si001",
    "x42i04_hh_si009",

    "x42i31_hh_fa006",
    "x42i08_hh_fa002",

    "x42i24_hh_mo016",
]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

MODELS = {
    "local": [
        "Qwen/Qwen2.5-0.5B-Instruct"
    ],
    "api": [
        {
            "model": "gpt-4o-mini",
            "key_name": "OPENAI_KEY",
            "base_url": "https://api.openai.com/v1"
        },
        {
            "model": "gpt-5-mini",
            "key_name": "OPENAI_KEY",
            "base_url": "https://api.openai.com/v1"
        }
    ]
}


# ---------------------------------------------------------------------------
# Research plan and system prompts
# ---------------------------------------------------------------------------

DESCRIPTIONS = """
<BESCHREIBUNGEN>
## DIMENSIONEN:

- VERTRÄGLICHKEIT (A): Mit dieser Dimension werden Einstellungen und gewohnheitsmäßige Verhaltensweisen in sozialen Beziehungen umschrieben. Personen mit hoher Ausprägung sind hilfsbereit, entgegenkommend, vertrauensbereit und bemüht anderen zu helfen. Sie begegnen anderen Menschen mit Wohlwollen, neigen zu Gutmütigkeit, sind bereit, in Auseinandersetzungen nachzugeben und können im Extremfall als unterwürfig oder abhängig erscheinen. Personen mit niedriger Ausprägung beschreiben sich als eher egozentrisch, misstrauisch gegenüber den Intentionen anderer, grob, sowie wenig geneigt zu kooperativem Verhalten und mit einer Präferenz für wettbewerbsorientiertes Verhalten.
- GEWISSENHAFTIGKEIT (C): Die Grundlage der Gewissenhaftigkeit bilden Unterschiede beim Planen, Organisieren und Ausführen von Aufgaben. Personen mit einer hohen Ausprägung beschreiben sich als eher zielstrebig, willensstark und entschlossen, während Personen mit einer niedrigen Ausprägung ihre Zielsetzungen mit geringerem Engagement verfolgen.
- EXTRAVERSION (E): Personen mit hoher Ausprägung in diesem Bereich lassen sich als gesellig, gesprächig, freundlich, unternehmensfreudig und aktiv beschreiben. Sie mögen die Gesellschaft andere, fühlen sich wohl in Gruppen, sind aber auch durchsetzungsfähig, selbstbewusst, dominant und lieben aufregenden Situationen und Stimulierungen. Personen mit niedriger Ausprägung in diesem Bereich sind eher zurückhaltend, ruhig, ausgeglichen und bedachtsam. Sie bevorzugen eher, allein zu sein. Introversion wird weniger als der Gegensatz von Extraversion, sondern mehr als das Fehlen von Extraversion beschrieben.
- NEUROTIZISMUS (N): Neurotizismus erfasst Unterschiede zwischen Personen hinsichtlich ihrer gefühlsmäßigen Robustheit einerseits und ihrer emotionalen Empfindlichkeit bzw. Ansprechbarkeit andererseits. Personen mit hoher Ausprägung in diesem Bereich sind empfindlicher und neigen unter Stress dazu, leichter aus dem Gleichgewicht zu kommen. Sie entwickeln eher unangepasste Formen der Problembewältigung, neigen zu unrealistischen Ideen und sind weniger in der Lage, ihre Bedürfnisse zu kontrollieren. Personen mit niedriger Ausprägung in diesem Bereich beschreiben sich als ausgeglichen, emotional stabil und robust und geraten nicht so leicht aus der Fassung. Charakteristisch für diese Personen ist, dass sie Gefühlszustände nicht so stark erleben.
- OFFENHEIT FÜR ERFAHRUNGEN (O): Personen mit hoher Ausprägung in diesem Bereich sind interessiert an neuen Erfahrungen, Erlebnissen, Eindrücken. Sie geben an ein reges Fantasieleben zu haben und eigene positive wie negative Gefühle sehr deutlich wahrzunehmen. Sie lassen sich auf neue Ideen ein und sind unkonventionell in ihren Wertorientierungen. Personen mit niedrigen Ausprägungen in diesem Bereich lassen sich als eher konventionell und konservativ eingestellt beschrieben. Sie ziehen Bekanntes und Bewährtes dem Neuen vor. Emotionale Reaktionen sind weniger intensiv, der Bereich der Interessen ist eingeschränkt und diesen Interessen wird auch nicht mit so starker Intensität nachgegangen, im Gegensatz zu Personen mit hoher Ausprägung.
- EHRLICHKEIT-BESCHEIDENHEIT (HH): Personen mit sehr niedrigen Werten in der Skala "Ehrlichkeit-Bescheidenheit" neigen dazu, sich zu verstellen, um ihre Ziele zu erreichen. Sie nehmen Regeln häufig nicht so genau, streben nach materiellem Reichtum und Ansehen und neigen dazu, sich anderen gegenüber privilegiert und überlegen zu fühlen. Personen mit sehr hohen Werten in dieser Skala hingegen verhalten sich stets authentisch und ehrlich. Sie vermeiden es, andere zu ihren eigenen Gunsten zu beeinflussen, und handeln stets fair. Sie streben weder Luxusgüter noch einen hohen sozialen Status an, noch haben sie den Anspruch, bevorzugt behandelt zu werden.

## FACETTEN:

### Dimension Verträglichkeit (A)
- Die Facette "Freundlichkeit (A-Fr)" erfasst die Tendenz sich anderen gegenüber fröhlich und freundlich zu verhalten. Personen mit niedriger Ausprägung kommen mit anderen Menschen eher schlecht zurecht, wohingegen Personen mit hoher Ausprägung als angenehme Personen wahrgenommen werden.
- Die Facette "Rücksichtnahme (A-Co)" erfasst die Tendenz höflich und rücksichtsvoll zu sein. Personen mit niedriger Ausprägung achten nicht auf die Gefühle anderer, wohingegen Personen mit hoher Ausprägung stets versuchen nett zu anderen zu sein.
- Die Facette "Hilfsbereitschaft (A-H)" erfasst die Tendenz anderen bei Problemen zu helfen. Personen mit niedriger Ausprägung neigen zu Egoismus, wohingegen Personen mit hoher Ausprägung großzügig und uneigennützig sind.

### Dimension Gewissenhaftigkeit (C)
- Die Facette "Fleiß (C-Hw)" erfasst die Tendenz hart und fokussiert zu arbeiten. Personen mit niedriger Ausprägung neigen dazu faul zu sein und Aufgaben nicht zu Ende zu bringen, wohingegen Personen mit hoher Ausprägung sich immer bemühen Arbeiten rechtzeitig und vollständig zu erledigen.
- Die Facette "Organisation (C-O)" erfasst die Tendenz ordentlich beim Erledigen von Aufgaben zu sein. Personen mit niedriger Ausprägung sind oft verspätet und halten ihre Umgebung nicht ordentlich, wohingegen Personen mit hoher Ausprägung viel Zeit für Planung und Struktur aufwenden.

### Dimension Extraversion (E)
- Die Facette "Durchsetzungsfähigkeit (E-A)" erfasst die Tendenz in Gruppen die Führung zu übernehmen. Personen mit niedriger Ausprägung sind in Gruppen eher zurückhaltend, wohingegen Personen mit hoher Ausprägung großen Einfluss innerhalb von Gruppe haben.
- Die Facette "Selbstbewusstsein (E-SB)" erfasst die Tendenz selbstsicher zu sein. Personen mit niedriger Ausprägung sind schüchtern und meiden es Aufmerksamkeit zu bekommen, wohingegen Personen mit hoher Ausprägung auch gerne mal im Zentrum der Aufmerksamkeit stehen.
- Die Facette "Soziale Aktivität (E-So)" erfasst die Tendenz unter Leute zu gehen. Personen mit niedriger Ausprägung bleiben lieber für sich und beschäftigen sich allein, wohingegen Personen mit hoher Ausprägung häufig auf Partys anzutreffen sind.

### Dimension Neurotizismus (N)
- Die Facette "Depression (N-D)" erfasst die Tendenz niedergeschlagen zu sein. Personen mit niedriger Ausprägung empfinden häufig positive Emotionen, wie Freude, wohingegen Personen mit hoher Ausprägung oft negative Emotionen, wie Traurigkeit empfinden.
- Die Facette "Reizbarkeit (N-Ir)" erfasst die Tendenz schnell emotional zu werden. Personen mit niedriger Ausprägung behalten stets Ruhe, wohingegen sich Personen mit hoher Ausprägung durch Belastung leicht aus dem Konzept bringen lassen und sehr emotional reagieren.
- Die Facette "Nervosität (N-St)" erfasst die Tendenz schnell nervös oder leicht gestresst zu sein. Personen mit niedriger Ausprägung bleiben auch unter großem Druck gelassen, wohingegen Personen mit hoher Ausprägung schon bei geringer Belastung unruhig werden und sich gestresst fühlen.

### Dimension Offenheit für Erfahrungen (O)
- Die Facette "Intellekt (O-In)" erfasst die Tendenz sich mit intellektuellen Themen zu beschäftigen. Personen mit niedriger Ausprägung meiden komplexe Diskussionen, wohingegen Personen mit hoher Ausprägung generell neugierig sind.
- Die Facette "Reflexion (O-R)" erfasst die Tendenz über sich, eigene Gefühle und komplexe Zusammenhänge nachzudenken. Personen mit niedriger Ausprägung denken selten mehr als einmal über ein Thema nach, wohingegen Personen mit hoher Ausprägung sich viel Zeit nehmen, um über Hintergründe zu reflektieren.
- Die Facette "Wissenschaftliches Interesse (O-Sc)" erfasst die Tendenz sich häufig mit wissenschaftlichen Themen auseinanderzusetzen. Personen mit niedriger Ausprägung meiden solche Themen, wohingegen sich Personen mit hoher Ausprägung wissenschaftlich weiterbilden.

### Dimension Ehrlichkeit-Bescheidenheit (HH)
- Die Facette "Aufrichtigkeit (HH-Si)" zeigt auf, wie authentisch eine Person im zwischenmenschlichen Kontakt ist. Personen mit niedriger Ausprägung in dieser Skala verstellen sich manchmal, um persönliche Ziele zu erreichen. Personen mit hoher Ausprägung verhalten sich hingegen stets aufrichtig und unverstellt. Sie beeinflussen andere nicht zu ihrem eigenen Vorteil.
- Die Facette "Fairness (HH-Fa)" beschreibt, wie ehrlich und regelkonform das Verhalten einer Person ist. Personen mit niedriger Ausprägung in dieser Skala neigen dazu, Regeln nicht so genau zu nehmen oder sogar zu brechen, um sich einen Vorteil zu verschaffen. Für Personen mit hoher Ausprägung geht Ehrlichkeit gegenüber ihren Mitmenschen und der Gesellschaft über alles und sie bereichern sich nicht auf Kosten anderer.
- Die Facette "Bescheidenheit (HH-Mo)" zeigt, wie bescheiden jemand in Bezug auf sich selbst ist. Personen mit niedriger Ausprägung in dieser Skala neigen dazu, sich anderen gegenüber privilegiert und überlegen zu fühlen. Personen mit hoher Ausprägung betrachten sich und andere Menschen als gleichwertig und beanspruchen für sich keine besondere Behandlung.
</BESCHREIBUNGEN>
"""

ITEMS_STRING = """
<ITEMS>
## Dimension Verträglichkeit (A)
### Facette "Freundlichkeit" (A-Fr):
- x42i29_a_fr066: Man hält mich für jemanden mit dem man einfach gut auskommt.
- x42i14_a_fr084: Ich komme mit den meisten Menschen gut zurecht.
- x42i43_a_fr220: Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.
### 2. Facette "Rücksichtnahme" (A-Co):
- x42i02_a_co080: Ich behandle andere Leute immer freundlich.
- x42i26_a_co207: Ich versuche zu jedem freundlich zu sein, den ich kenne.
- x42i27_a_co209: Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.
### 3. Facette "Hilfsbereitschaft" (A-H):
- x42i12_a_h064: Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.
- x42i48_a_h068: Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.
- x42i46_a_h213: Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.

## Dimension Gewissenhaftigkeit (C)
### 4. Facette "Fleiß" (C-Hw):
- x42i05_c_hw126: Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.
- x42i30_c_hw137: Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.
- x42i44_c_hw167: Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.
### 5. Facette "Organisation" (C-O):
- x42i18_c_o153: Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.
- x42i49_c_o157: Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.
- x42i39_c_o162: Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.

## Dimension Extraversion (E)
### 6. Facette "Durchsetzungsfähigkeit" (E-A):
- x42i42_e_a002: Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.
- x42i35_e_a004: Ich neige dazu, in Gruppen die Führung zu übernehmen.
- x42i03_e_a009: Ich habe eine Menge Einfluss auf andere Leute.
### 7. Facette "Selbstbewusstsein" (E-SB):
- x42i23_e_sb010: Ich bin eine sehr schüchterne Person.
- x42i10_e_sb014: Meine Freunde halten mich für schüchtern.
- x42i22_e_sb026: Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.
### 8. Facette "Soziale Aktivität" (E-So):
- x42i40_e_so007: Ich bin gerne wo viel los ist.
- x42i32_e_so012: Ich gebe mir große Mühe Leute kennen zu lernen.
- x42i20_e_so028: Ich mag Partys auf denen viele Leute sind.

## Dimension Neurotizismus (N)
### 9. Facette "Depression" (N-D):
- x42i09_n_d039: Es gibt Zeiten in denen ich mich selbst bedaure.
- x42i19_n_d054: Manchmal bin ich entmutigt und möchte am liebsten aufgeben.
- x42i37_n_d055: Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.
### 10. Facette "Reizbarkeit" (N-Ir):
- x42i11_n_ir034: Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.
- x42i06_n_ir058: Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.
- x42i07_n_ir070: Ich kann Kritik nicht sehr gut akzeptieren.
### 11. Facette "Nervosität" (N-St):
- x42i36_n_st037: Ich fühle mich oft müde und erschöpft.
- x42i45_n_st040: Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.
- x42i13_n_st043: Ich bin oft zittrig und angespannt.

## Dimension Offenheit (O)
### 12. Facette "Intellekt" (O-In):
- x42i38_o_in094: Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.
- x42i28_o_in106: Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.
- x42i33_o_in118: Ich besitze ein hohes Maß an intellektueller Neugier.
### 13. Facette "Reflexion" (O-R):
- x42i21_o_r100: Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.
- x42i50_o_r117: Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.
- x42i41_o_r120: Ich lese gerne Gedichte.
### 14. Facette "Wissenschaftliches Interesse" (O-Sc):
- x42i16_o_sc103: Ich denke oft über die Wunder der Natur nach.
- x42i25_o_sc114: Die Evolutionstheorie fasziniert mich.
- x42i01_o_sc116: Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.

## Dimension Ehrlichkeit-Bescheidenheit (HH)
### 15. Facette "Aufrichtigkeit" (HH-Si):
- x42i47_hh_si001: Wenn ich von einer Person, die ich nicht mag, etwas will, verhalte ich mich dieser Person gegenüber sehr nett um es zu bekommen.
- x42i15_hh_si005: Ich würde keine Schmeicheleien benutzen, um eine Gehaltserhöhung zu bekommen oder befördert zu werden, auch wenn ich wüsste, dass es erfolgreich wäre.
- x42i04_hh_si009: Wenn ich von jemandem etwas will, lache ich auch noch über dessen schlechteste Witze.
### 16. Facette "Fairness" (HH-Fa):
- x42i31_hh_fa006: Ich würde in Versuchung geraten, Diebesgut zu kaufen, wenn ich knapp bei Kasse wäre.
- x42i17_hh_fa010: Ich würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.
- x42i08_hh_fa002: Wenn ich wüsste, dass ich niemals erwischt werde, wäre ich bereit, eine Million zu stehlen.
### 17. Facette "Bescheidenheit" (HH-Mo):
- x42i51_hh_mo008: Ich will nicht, dass andere Leute mich behandeln, als ob ich ihnen überlegen sei.
- x42i34_hh_mo004: Ich bin eine ganz normale Person, die nicht besser ist als andere.
- x42i24_hh_mo016: Ich will, dass alle wissen, dass ich eine wichtige angesehene Person bin.
"\n</ITEMS>"
"""

LEVELS = [
    {
        "level": "facet-lvl",
        "text": "auf den 17 Facetten",
        "scale": "jeweils auf einer ganzzahligen Skala von 10 (sehr niedrig) bis 50 (sehr hoch).",
        "answer_format": "Nutze als Key deiner Antwort jeweils die Facetten-ID."
    },
    {
        "level": "item-lvl",
        "text": "auf den 51 Items",
        "scale": "jeweils auf einer ganzzahligen Skala von 1 (sehr niedrig) bis 5 (sehr hoch).",
        "answer_format": "Nutze als Key deiner Antwort jeweils die Item-ID."
    }
]

NORMS = [
    {
        "norm": "without-norm",
        "text": """
        """
    }
]

RESEARCH_PLAN = []

for level, norm in product(LEVELS, NORMS):

        combination = {
            "level": level["level"],
            "norm": norm["norm"],
        }

        prompt_label = "_".join(combination.values())

        system_prompt = (
            "Du bist ein erfahrener Persönlichkeitsdiagnostiker mit Expertise im "
            "Trait Self-Descriptive Inventory (TSDI), ergänzt um die Dimension "
            "Ehrlichkeit-Bescheidenheit aus dem HEXACO-Modell. "
            "Du liest ein Interviewtranskript und bewertest ausschließlich die "
            f"befragte Person (nicht die interviewende Person) {level["text"]}, "
            f"{level["scale"]} {level["answer_format"]}\n"
            "\n"
            "## Dimensionen und zu berücksichtigende Facetten\n"
            "\n"
            "Stütze dein Urteil auf die untenstehenden Facetten und Items, und "
            "nicht auf einen vagen Gesamteindruck. Hinweise zu einzelnen Facetten "
            "können in unterschiedliche Richtungen weisen - wäge das Gesamtbild über "
            "das gesamte Transkript ab, nicht eine einzelne Aussage.\n"
            f"{DESCRIPTIONS}"
            f"{ITEMS_STRING}"
            f"{norm["text"]}"
            "## Evidenzbasierter Bewertungsprozess\n"
            "\n"
            "Arbeite vor jeder Bewertung gedanklich Folgendes durch:\n"
            "1. Welche konkreten Verhaltensweisen, Formulierungen, Anekdoten oder "
            "Denkmuster im Transkript sind für diese Dimension relevant?\n"
            "2. Spiegeln sie eine stabile Disposition wider oder eine einmalige "
            "Reaktion auf eine bestimmte Frage?\n"
            "3. Bestätigen sich die Hinweise an mehreren Stellen im Transkript, "
            "oder stützen sie sich auf eine isolierte Bemerkung? Isolierte "
            "Bemerkungen sollten eine Bewertung nur geringfügig verschieben.\n"
            "4. Erst nach dieser Abwägung legst du dich auf eine Bewertung fest.\n"
            "\n"
            "## Bias-Kontrolle - explizit ausklammern bzw. korrigieren\n"
            "\n"
            "- Einfluss der interviewenden Person: Bewerte die befragte Person "
            "nicht anhand des Tons, der Fragenschwierigkeit oder der Suggestivität "
            "der interviewenden Person. Nur die Antworten der befragten Person "
            "zählen.\n"
            "- Sprachliche Gewandtheit ≠ Persönlichkeit: Eine gewandte, geschliffene "
            "Ausdrucksweise ist kein automatischer Beleg für eine Dimension (z.B. "
            "Eloquenz nicht mit Offenheit gleichsetzen, Selbstsicherheit nicht mit "
            "hoher emotionaler Stabilität), sofern nicht der Inhalt - nicht nur "
            "der Vortrag - dies stützt.\n"
            "- Soziale Erwünschtheit: Interviewsituationen begünstigen "
            "Selbstdarstellung. Einstudiert wirkende, generische 'gute Antworten' "
            "(z.B. skriptartig klingende Teamwork-Anekdoten) sind schwächere "
            "Evidenz als spontane, konkrete, individuelle Details - dies gilt "
            "besonders für Honesty-Humility, da sozial erwünschte Antworten oft "
            "gerade in dieser Dimension überzeichnet werden.\n"
            "- Transkriptionsartefakte: Ignoriere Füllwörter ('äh', 'also'), "
            "Versprecher und Unflüssigkeiten, die durch Spracherkennung entstehen "
            "- sie sind kein Beleg für Nervosität oder Desorganisation, außer der "
            "inhaltliche Kontext stützt dies ebenfalls.\n"
            "- Halo-Effekt: Bewerte jede Dimension unabhängig. Eine insgesamt "
            "beeindruckende Person sollte nicht automatisch in unabhängigen "
            "Dimensionen hoch bewertet werden.\n"
            "- Verbositäts-Bias: Eine längere Antwort ist nicht per se mehr Beleg "
            "für Surgency oder Gewissenhaftigkeit als eine kürzere, gut "
            "strukturierte Antwort.\n"
            "- Themen-Bias: Der Interviewgegenstand (z.B. eine technische vs. eine "
            "kreative Rolle) sollte deine Erwartungshaltung an 'durchschnittlich' "
            "nicht verschieben - bewerte gegen die Allgemeinbevölkerung, nicht "
            "gegen rollenspezifische Normen.\n"
            "- Demografischer Bias: Lass dich nicht von vermutetem Geschlecht, "
            "Alter, Akzent, Hinweisen auf die Muttersprache oder kulturellem "
            "Hintergrund beeinflussen.\n"
            "\n"
            "## Umgang mit unzureichender Evidenz\n"
            "\n"
            "Wenn das Transkript wenig oder keine relevante Evidenz für eine "
            "Dimension liefert, verwende den Mittelwert (3) statt aus indirekten "
            "Hinweisen zu spekulieren, und lass die Sparsamkeit der Evidenz "
            "begrenzen, wie weit du dich von 3 entfernst.\n"
            "\n"
            "## Ausgabe\n"
            "\n"
            "Stütze jede Bewertung ausschließlich auf explizit Gesagtes oder "
            "direkt Gezeigtes im Transkript - niemals auf Annahmen über die "
            "befragte Person, die über den Text hinausgehen. Gib ausschließlich "
            "die Bewertungen im geforderten strukturierten Format aus, ohne "
            "zusätzlichen Kommentar."
        )

        RESEARCH_PLAN.append({
            **combination,
            "prompt_label": prompt_label,
            "system_prompt": system_prompt,
        })


# ---------------------------------------------------------------------------
# Answer format
# ---------------------------------------------------------------------------

# Items
ItemRating = Annotated[int, Field(ge=1, le=5, description="Bewertung von 1 (sehr niedrig) bis 5 (sehr hoch).")]
class ItemLevelRatings(BaseModel):
    """ItemRatings for each questionnaire item, as an int from 1 to 5 (step = 1)."""
 
    x42i29_a_fr066: ItemRating = Field(..., description="Man hält mich für jemanden mit dem man einfach gut auskommt.")
    x42i14_a_fr084: ItemRating = Field(..., description="Ich komme mit den meisten Menschen gut zurecht.")
    x42i43_a_fr220: ItemRating = Field(..., description="Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.")
    x42i02_a_co080: ItemRating = Field(..., description="Ich behandle andere Leute immer freundlich.")
    x42i26_a_co207: ItemRating = Field(..., description="Ich versuche zu jedem freundlich zu sein, den ich kenne.")
    x42i27_a_co209: ItemRating = Field(..., description="Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.")
    x42i12_a_h064: ItemRating = Field(..., description="Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.")
    x42i48_a_h068: ItemRating = Field(..., description="Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.")
    x42i46_a_h213: ItemRating = Field(..., description="Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.")
    x42i05_c_hw126: ItemRating = Field(..., description="Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.")
    x42i30_c_hw137: ItemRating = Field(..., description="Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.")
    x42i44_c_hw167: ItemRating = Field(..., description="Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.")
    x42i18_c_o153: ItemRating = Field(..., description="Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.")
    x42i49_c_o157: ItemRating = Field(..., description="Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.")
    x42i39_c_o162: ItemRating = Field(..., description="Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.")
    x42i42_e_a002: ItemRating = Field(..., description="Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.")
    x42i35_e_a004: ItemRating = Field(..., description="Ich neige dazu, in Gruppen die Führung zu übernehmen.")
    x42i03_e_a009: ItemRating = Field(..., description="Ich habe eine Menge Einfluss auf andere Leute.")
    x42i23_e_sb010: ItemRating = Field(..., description="Ich bin eine sehr schüchterne Person.")
    x42i10_e_sb014: ItemRating = Field(..., description="Meine Freunde halten mich für schüchtern.")
    x42i22_e_sb026: ItemRating = Field(..., description="Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.")
    x42i40_e_so007: ItemRating = Field(..., description="Ich bin gerne wo viel los ist.")
    x42i32_e_so012: ItemRating = Field(..., description="Ich gebe mir große Mühe Leute kennen zu lernen.")
    x42i20_e_so028: ItemRating = Field(..., description="Ich mag Partys auf denen viele Leute sind.")
    x42i09_n_d039: ItemRating = Field(..., description="Es gibt Zeiten in denen ich mich selbst bedaure.")
    x42i19_n_d054: ItemRating = Field(..., description="Manchmal bin ich entmutigt und möchte am liebsten aufgeben.")
    x42i37_n_d055: ItemRating = Field(..., description="Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.")
    x42i11_n_ir034: ItemRating = Field(..., description="Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.")
    x42i06_n_ir058: ItemRating = Field(..., description="Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.")
    x42i07_n_ir070: ItemRating = Field(..., description="Ich kann Kritik nicht sehr gut akzeptieren.")
    x42i36_n_st037: ItemRating = Field(..., description="Ich fühle mich oft müde und erschöpft.")
    x42i45_n_st040: ItemRating = Field(..., description="Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.")
    x42i13_n_st043: ItemRating = Field(..., description="Ich bin oft zittrig und angespannt.")
    x42i38_o_in094: ItemRating = Field(..., description="Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.")
    x42i28_o_in106: ItemRating = Field(..., description="Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.")
    x42i33_o_in118: ItemRating = Field(..., description="Ich besitze ein hohes Maß an intellektueller Neugier.")
    x42i21_o_r100: ItemRating = Field(..., description="Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.")
    x42i50_o_r117: ItemRating = Field(..., description="Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.")
    x42i41_o_r120: ItemRating = Field(..., description="Ich lese gerne Gedichte.")
    x42i16_o_sc103: ItemRating = Field(..., description="Ich denke oft über die Wunder der Natur nach.")
    x42i25_o_sc114: ItemRating = Field(..., description="Die Evolutionstheorie fasziniert mich.")
    x42i01_o_sc116: ItemRating = Field(..., description="Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.")
    x42i47_hh_si001: ItemRating = Field(..., description="Wenn ich von einer Person, die ich nicht mag, etwas will, verhalte ich mich dieser Person gegenüber sehr nett um es zu bekommen.")
    x42i15_hh_si005: ItemRating = Field(..., description="Ich würde keine Schmeicheleien benutzen, um eine Gehaltserhöhung zu bekommen oder befördert zu werden, auch wenn ich wüsste, dass es erfolgreich wäre.")
    x42i04_hh_si009: ItemRating = Field(..., description="Wenn ich von jemandem etwas will, lache ich auch noch über dessen schlechteste Witze.")
    x42i31_hh_fa006: ItemRating = Field(..., description="Ich würde in Versuchung geraten, Diebesgut zu kaufen, wenn ich knapp bei Kasse wäre.")
    x42i17_hh_fa010: ItemRating = Field(..., description="Ich würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.")
    x42i08_hh_fa002: ItemRating = Field(..., description="Wenn ich wüsste, dass ich niemals erwischt werde, wäre ich bereit, eine Million zu stehlen.")
    x42i51_hh_mo008: ItemRating = Field(..., description="Ich will nicht, dass andere Leute mich behandeln, als ob ich ihnen überlegen sei.")
    x42i34_hh_mo004: ItemRating = Field(..., description="Ich bin eine ganz normale Person, die nicht besser ist als andere.")
    x42i24_hh_mo016: ItemRating = Field(..., description="Ich will, dass alle wissen, dass ich eine wichtige angesehene Person bin.")

# Facets
FacetRating = Annotated[int, Field(ge=10, le=50, description="Bewertung von 10 (sehr niedrig) bis 50 (sehr hoch).")]
class FacetLevelRatings(BaseModel):
    """Ratings for each facet, as an int from 10 to 50 (step 1)."""
 
    a_fr: FacetRating = Field(..., description="Freundlichkeit")
    a_co: FacetRating = Field(..., description="Rücksichtnahme")
    a_h: FacetRating = Field(..., description="Hilfsbereitschaft")
    c_hw: FacetRating = Field(..., description="Fleiß")
    c_o: FacetRating = Field(..., description="Organisation")
    e_a: FacetRating = Field(..., description="Durchsetzungsfähigkeit")
    e_sb: FacetRating = Field(..., description="Selbstbewusstsein")
    e_so: FacetRating = Field(..., description="Soziale Aktivität")
    n_d: FacetRating = Field(..., description="Depression")
    n_ir: FacetRating = Field(..., description="Reizbarkeit")
    n_st: FacetRating = Field(..., description="Nervosität")
    o_in: FacetRating = Field(..., description="Intellekt")
    o_r: FacetRating = Field(..., description="Reflexion")
    o_sc: FacetRating = Field(..., description="Wissenschaftliches Interesse")
    hh_si: FacetRating = Field(..., description="Aufrichtigkeit")
    hh_fa: FacetRating = Field(..., description="Fairness")
    hh_mo: FacetRating = Field(..., description="Bescheidenheit")