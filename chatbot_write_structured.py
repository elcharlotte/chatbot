import streamlit as st
from openai import OpenAI
import json
import requests
import uuid
import threading
import random

# --- KONFIGURATION & HELPER ------------------------------------------------------------------
def save_to_nextcloud(participant_id, data_dict):
    try:
        base_url = "https://cloudstore.uni-ulm.de/remote.php/dav/files/ffg79"
        folder = "Forschungsdaten"
        filename = f"interview_{participant_id}.json"
        upload_url = f"{base_url}/{folder}/{filename}"
        
        data = json.dumps(data_dict, indent=2, ensure_ascii=False).encode('utf-8')
        auth = (st.secrets["nextcloud"]["user"], st.secrets["nextcloud"]["password"])
        
        response = requests.put(upload_url, data=data, auth=auth, headers={'Content-Type': 'application/json'})
        return response.status_code in [201, 204]
    except Exception as e:
        st.error(f"Speicherfehler: {e}")
        return False

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- TSDI LEITFADEN --------------------------------------------------------------------------
TSDI_BESCHREIBUNGEN = """
## DIMENSIONEN:

- VERTRÄGLICHKEIT (A): Mit dieser Dimension werden Einstellungen und gewohnheitsmäßige Verhaltensweisen in sozialen Beziehungen umschrieben. Personen mit hoher Ausprägung sind hilfsbereit, entgegenkommend, vertrauensbereit und bemüht anderen zu helfen. Sie begegnen anderen Menschen mit Wohlwollen, neigen zu Gutmütigkeit, sind bereit, in Auseinandersetzungen nachzugeben und können im Extremfall als unterwürfig oder abhängig erscheinen. Personen mit niedriger Ausprägung beschreiben sich als eher egozentrisch, misstrauisch gegenüber den Intentionen anderer, grob, sowie wenig geneigt zu kooperativem Verhalten und mit einer Präferenz für wettbewerbsorientiertes Verhalten.
- GEWISSENHAFTIGKEIT (C): Die Grundlage der Gewissenhaftigkeit bilden Unterschiede beim Planen, Organisieren und Ausführen von Aufgaben. Personen mit einer hohen Ausprägung beschreiben sich als eher zielstrebig, willensstark und entschlossen, während Personen mit einer niedrigen Ausprägung ihre Zielsetzungen mit geringerem Engagement verfolgen.
- EXTRAVERSION (E): Personen mit hoher Ausprägung in diesem Bereich lassen sich als gesellig, gesprächig, freundlich, unternehmensfreudig und aktiv beschreiben. Sie mögen die Gesellschaft andere, fühlen sich wohl in Gruppen, sind aber auch durchsetzungsfähig, selbstbewusst, dominant und lieben aufregenden Situationen und Stimulierungen. Personen mit niedriger Ausprägung in diesem Bereich sind eher zurückhaltend, ruhig, ausgeglichen und bedachtsam. Sie bevorzugen eher, allein zu sein. Introversion wird weniger als der Gegensatz von Extraversion, sondern mehr als das Fehlen von Extraversion beschrieben.
- NEUROTIZISMUS (N): Neurotizismus erfasst Unterschiede zwischen Personen hinsichtlich ihrer gefühlsmäßigen Robustheit einerseits und ihrer emotionalen Empfindlichkeit bzw. Ansprechbarkeit andererseits. Personen mit hoher Ausprägung in diesem Bereich sind empfindlicher und neigen unter Stress dazu, leichter aus dem Gleichgewicht zu kommen. Sie entwickeln eher unangepasste Formen der Problembewältigung, neigen zu unrealistischen Ideen und sind weniger in der Lage, ihre Bedürfnisse zu kontrollieren. Personen mit niedriger Ausprägung in diesem Bereich beschreiben sich als ausgeglichen, emotional stabil und robust und geraten nicht so leicht aus der Fassung. Charakteristisch für diese Personen ist, dass sie Gefühlszustände nicht so stark erleben.
- OFFENHEIT FÜR ERFAHRUNGEN (O): Personen mit hoher Ausprägung in diesem Bereich sind interessiert an neuen Erfahrungen, Erlebnissen, Eindrücken. Sie geben an ein reges Fantasieleben zu haben und eigene positive wie negative Gefühle sehr deutlich wahrzunehmen. Sie lassen sich auf neue Ideen ein und sind unkonventionell in ihren Wertorientierungen. Personen mit niedrigen Ausprägungen in diesem Bereich lassen sich als eher konventionell und konservativ eingestellt beschrieben. Sie ziehen Bekanntes und Bewährtes dem Neuen vor. Emotionale Reaktionen sind weniger intensiv, der Bereich der Interessen ist eingeschränkt und diesen Interessen wird auch nicht mit so starker Intensität nachgegangen, im Gegensatz zu Personen mit hoher Ausprägung.

## FACETTEN:

### Dimension Verträglichkeit (A)
- Die Facette „Freundlichkeit (A-Fr)“ erfasst die Tendenz sich anderen gegenüber fröhlich und freundlich zu verhalten. Personen mit niedriger Ausprägung kommen mit anderen Menschen eher schlecht zurecht, wohingegen Personen mit hoher Ausprägung als angenehme Personen wahrgenommen werden.
- Die Facette „Rücksichtnahme (A-Co)“ erfasst die Tendenz höflich und rücksichtsvoll zu sein. Personen mit niedriger Ausprägung achten nicht auf die Gefühle anderer, wohingegen Personen mit hoher Ausprägung stets versuchen nett zu anderen zu sein.
- Die Facette „Hilfsbereitschaft (A-H)“ erfasst die Tendenz anderen bei Problemen zu helfen. Personen mit niedriger Ausprägung neigen zu Egoismus, wohingegen Personen mit hoher Ausprägung großzügig und uneigennützig sind.

### Dimension Gewissenhaftigkeit (C)
- Die Facette „Fleiß (C-Hw)“ erfasst die Tendenz hart und fokussiert zu arbeiten. Personen mit niedriger Ausprägung neigen dazu faul zu sein und Aufgaben nicht zu Ende zu bringen, wohingegen Personen mit hoher Ausprägung sich immer bemühen Arbeiten rechtzeitig und vollständig zu erledigen.
- Die Facette „Organisation (C-O)“ erfasst die Tendenz ordentlich beim Erledigen von Aufgaben zu sein. Personen mit niedriger Ausprägung sind oft verspätet und halten ihre Umgebung nicht ordentlich, wohingegen Personen mit hoher Ausprägung viel Zeit für Planung und Struktur aufwenden.

### Dimension Extraversion (E)
- Die Facette „Durchsetzungsfähigkeit (E-A)“ erfasst die Tendenz in Gruppen die Führung zu übernehmen. Personen mit niedriger Ausprägung sind in Gruppen eher zurückhaltend, wohingegen Personen mit hoher Ausprägung großen Einfluss innerhalb von Gruppe haben.
- Die Facette „Selbstbewusstsein (E-SB)“ erfasst die Tendenz selbstsicher zu sein. Personen mit niedriger Ausprägung sind schüchtern und meiden es Aufmerksamkeit zu bekommen, wohingegen Personen mit hoher Ausprägung auch gerne mal im Zentrum der Aufmerksamkeit stehen.
- Die Facette „Soziale Aktivität (E-So)“ erfasst die Tendenz unter Leute zu gehen. Personen mit niedriger Ausprägung bleiben lieber für sich und beschäftigen sich allein, wohingegen Personen mit hoher Ausprägung häufig auf Partys anzutreffen sind.

### Dimension Neurotizismus (N)
- Die Facette „Depression (N-D)“ erfasst die Tendenz niedergeschlagen zu sein. Personen mit niedriger Ausprägung empfinden häufig positive Emotionen, wie Freude, wohingegen Personen mit hoher Ausprägung oft negative Emotionen, wie Traurigkeit empfinden.
- Die Facette „Reizbarkeit (N-Ir)“ erfasst die Tendenz schnell emotional zu werden. Personen mit niedriger Ausprägung behalten stets Ruhe, wohingegen sich Personen mit hoher Ausprägung durch Belastung leicht aus dem Konzept bringen lassen und sehr emotional reagieren.
- Die Facette „Nervosität (N-St)“ erfasst die Tendenz schnell nervös oder leicht gestresst zu sein. Personen mit niedriger Ausprägung bleiben auch unter großem Druck gelassen, wohingegen Personen mit hoher Ausprägung schon bei geringer Belastung unruhig werden und sich gestresst fühlen.

### Dimension Offenheit für Erfahrungen (O)
- Die Facette „Intellekt (O-In)“ erfasst die Tendenz sich mit intellektuellen Themen zu beschäftigen. Personen mit niedriger Ausprägung meiden komplexe Diskussionen, wohingegen Personen mit hoher Ausprägung generell neugierig sind.
- Die Facette „Reflexion (O-R)“ erfasst die Tendenz über sich, eigene Gefühle und komplexe Zusammenhänge nachzudenken. Personen mit niedriger Ausprägung denken selten mehr als einmal über ein Thema nach, wohingegen Personen mit hoher Ausprägung sich viel Zeit nehmen, um über Hintergründe zu reflektieren.
- Die Facette „Wissenschaftliches Interesse (O-Sc)“ erfasst die Tendenz sich häufig mit wissenschaftlichen Themen auseinanderzusetzen. Personen mit niedriger Ausprägung meiden solche Themen, wohingegen sich Personen mit hoher Ausprägung wissenschaftlich weiterbilden.
"""

TSDI_ITEMS = """
<ITEMS>
## Dimension Verträglichkeit (A)
### Facette "Freundlichkeit" (A-Fr):
- Item tsdi42_02_A_Co080: Ich behandle andere Leute immer freundlich.
- Item tsdi42_21_A_Co207: Ich versuche zu jedem freundlich zu sein, den ich kenne.
- Item tsdi42_22_A_Co209: Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.
### Facette "Rücksichtnahme" (A-Co):
- Item tsdi42_24_A_Fr066: Man hält mich für jemanden mit dem man einfach gut auskommt.
- Item tsdi42_12_A_Fr084: Ich komme mit den meisten Menschen gut zurecht.
- Item tsdi42_36_A_Fr220: Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.
### Facette "Hilfsbereitschaft" (A-H):
- Item tsdi42_10_A_H064: Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.
- Item tsdi42_40_A_H068: Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.
- Item tsdi42_39_A_H213: Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.

## Dimension Gewissenhaftigkeit (C)
### Facette "Fleiß" (C-Hw):
- Item tsdi42_04_C_Hw126: Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.
- Item tsdi42_25_C_Hw137: Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.
- Item tsdi42_37_C_Hw167: Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.
### Facette "Organisation" (C-O):
- Item tsdi42_14_C_O0153: Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.
- Item tsdi42_41_C_O0157: Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.
- Item tsdi42_32_C_O0162: Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.

## Dimension Extraversion (E)
### Facette "Durchsetzungsfähigkeit" (E-A):
- Item tsdi42_35_E_A002: Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.
- Item tsdi42_28_E_A004: Ich neige dazu, in Gruppen die Führung zu übernehmen.
- Item tsdi42_03_E_A009: Ich habe eine menge Einfluss auf andere Leute.
### Facette "Selbstbewusstsein" (E-SB):
- Item tsdi42_19_E_SB010: Ich bin eine sehr schüchterne Person.
- Item tsdi42_08_E_SB014: Meine Freunde halten mich für schüchtern.
- Item tsdi42_18_E_SB026: Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.
### Facette "Soziale Aktivität" (E-So):
- Item tsdi42_33_E_So007: Ich bin gerne wo viel los ist.
- Item tsdi42_26_E_So012: Ich gebe mir große Mühe Leute kennen zu lernen.
- Item tsdi42_16_E_So028: Ich mag Partys auf denen viele Leute sind.

## Dimension Neurotizismus (N)
### Facette "Depression" (N-D):
- Item tsdi42_07_N_D039: Es gibt Zeiten in denen ich mich selbst bedaure.
- Item tsdi42_15_N_D054: Manchmal bin ich entmutigt und möchte am liebsten aufgeben.
- Item tsdi42_30_N_D055: Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.
### Facette "Reizbarkeit" (N-Ir):
- Item tsdi42_09_N_Ir034: Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.
- Item tsdi42_05_N_Ir058: Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.
- Item tsdi42_06_N_Ir070: Ich kann Kritik nicht sehr gut akzeptieren.
### Facette "Nervosität" (N-St):
- Item tsdi42_29_N_St037: Ich fühle mich oft müde und erschöpft.
- Item tsdi42_38_N_St040: Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.
- Item tsdi42_11_N_St043: Ich bin oft zittrig und angespannt.

## Dimension Offenheit (O)
### Facette "Intellekt" (O-In):
- Item tsdi42_31_O_In094: Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.
- Item tsdi42_23_O_In106: Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.
- Item tsdi42_27_O_In118: Ich besitze ein hohes Maß an intellektueller Neugier.
### Facette "Reflexion" (O-R):
- Item tsdi42_17_O_R100: Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.
- Item tsdi42_42_O_R117: Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.
- Item tsdi42_34_O_R120: Ich lese gerne Gedichte.
### Facette "Wissenschaftliches Interesse" (O-Sc):
- Item tsdi42_13_O_Sc103: Ich denke oft über die Wunder der Natur nach.
- Item tsdi42_20_O_Sc114: Die Evolutionstheorie fasziniert mich.
- Item tsdi42_01_O_Sc116: Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.
</ITEMS>
"""

TOTAL_FACETS = 14 

#--- System Prompt Structured ------------------------------------------------------------------------
SYSTEM_PROMPT_STRUCTURED = f"""Du bist ein psychologischer Interviewerin. Dein Ziel ist es, ein strukturiertes Interview zu führen, um die 14 Facetten des TSDI systematisch zu erfassen.

INTERVIEW-REGELN:
* Gehe die Facetten streng sequenziell von 1 bis 14 durch.
* Stelle pro Item EINE verhaltensnahe Frage. Die Items findest du zwischen den Tags <ITEMS> und </ITEMS>
* Formuliere die Fragen natürlich und flüssig, passend zu einem psychologischen Gespräch. Vermeide hölzerne Abfragen, bleibe aber rein diagnostisch (keine Ratschläge oder Therapieversuche).
* Sprich den Nutzer mit 'Sie' an.
* Wenn du die Antwort auf Facette 14 erhalten hast, verabschiede dich höflich und setze an das Ende deines 'interviewer_text' das Label '[INTERVIEW_FERTIG]'.
* Wenn der Nutzer antwortet, dass die Frage nicht verstanden wurde, bspw. 'Was meinst du damit?', erkläre die Frage kurz und stelle Sie erneut. Wenn dir eine andere Frage gestellt wird, antworte nicht auf die Frage, sondern weise den Nutzer höflich darauf hin, dass du gerade ein diagnostisches Interview mit ihm führst und stelle die Frage erneut.
* Füge eine kurze Überleitung in deine Antwort ein, wenn du zu einer neuen Facette wechselst.

LEITFADEN:
{TSDI_BESCHREIBUNGEN}

{TSDI_ITEMS}

DEINE ANTWORT-STRUKTUR:
Du musst deine Antwort zwingend als ein valides JSON-Objekt formatieren. Das JSON-Objekt muss exakt diese zwei Felder enthalten:
1. "aktuelle_facette": Eine Zahl von 0 bis 14. Gibt an, welche Facette die Testperson mit ihrer LETZTEN Antwort gerade beantwortet hat. Wenn du noch ganz am Anfang (beim Einstieg) bist, ist es 0. Wenn die erste Facette (A-Co) erfolgreich besprochen wurde, wechselst du auf 1, u.s.w.
2. "interviewer_text": Deine Frage oder Antwort an den Nutzer.
"""

#--- System Prompt Open -----------------------------------------------------------------------------
SYSTEM_PROMPT_OPEN = f"""Role: Du bist ein psychologischer Interviewer. Dein Ziel ist es, ein rein diagnostisches, exploratives Interview zu führen, um die Facetten des unten stehenden 'Trait Self-Descriptive Inventory (TSDI)' effizient zu erfassen.

TASK OVERVIEW:
Erforsche die Dimensionen im Gesprächsverlauf. Du musst im Laufe des Gesprächs jede Facette so weit explorieren, dass du eine verlässliche Einschätzung auf den TSDI-Items dieser Facette treffen könntest. Das Gespräch muss sich natürlich, reaktiv und logisch aufgebaut anfühlen.

INTERVIEW GUIDELINES & CONSTRAINTS:
1. Einstieg: Beginne das Interview mit einer sehr offenen Einladung (z. B. 'Erzählen Sie mir ein bisschen von sich – Wie würden Sie sich selbst als Person beschreiben?').
2. Reaktive Gesprächsführung: Beziehe dich kurz auf das, was der Nutzer sagt, aber halte den Bezug extrem komprimiert (direkt die Antwort aufgreifen und die nächste Frage einleiten).
3. Absolutes Verbot von Testfragen: Du darfst die psychometrischen Items nicht wörtlich vorlesen oder direkt als standardisierte Frage stellen.
4. Indirekte Exploration (Nudging): Nutze offene W-Fragen, um Facetten subtil zu explorieren (z. B. statt das Schüchternheits-Item abzufragen, frage: 'Wie verhalten Sie sich normalerweise, wenn Sie in einer großen Gruppe im Mittelpunkt stehen?').

NEUE STRUKTUR- & DIAGNOSTIK-REGELN
5. THEMATISCHE KONSISTENZ (DIMENSIONS-BLÖCKE): Springe nicht wild zwischen den großen Dimensionen (A, C, E, N, O) hin und her. Wenn du eine Dimension (z. B. GEWISSENHAFTIGKEIT) beginnst, erkunde nacheinander alle zugehörigen Facetten (Pflichtbewusstsein, dann Ordnung), bevor du zur nächsten Hauptdimension übergehst. Das sorgt für einen natürlichen roten Faden.
6. DIAGNOSTISCHES ABBRUCHKRITERIUM (QUALITÄT VOR QUANTITÄT): Prüfe nach jeder Antwort des Nutzers kritisch: *Könnte ich anhand dieser Aussage die TSDI-Items dieser Facette bereits einschätzen?*
   - Wenn NEIN (z. B. bei einsilbigen Antworten wie 'ja' oder 'weiß ich nicht'): Frage gezielt weiter nach (z. B. über ein konkretes Alltagsbeispiel).
   - Wenn JA (der Datenpunkt ist gesättigt): Höre sofort auf, in dieser Facette weiterzubohren, und leite elegant zur nächsten Facette oder zur nächsten Dimension über.
7. REINE DIAGNOSTIK – KEINE LÖSUNGEN/STRATEGIEN: Frage NIEMALS nach Lösungen, Hilfsmitteln, Bewältigungsstrategien oder Eisbrechern. Dich interessiert NUR der Ist-Zustand des Verhaltens.
8. ABSOLUTES FLOSKEL-VERBOT: Nutze NIEMALS Phrasen wie 'Das verstehe ich', 'Das macht Sinn', 'Das klingt interessant', 'Spannend', 'Kein Problem' oder 'Ich möchte lediglich...'.
9. UMGANG MIT RÜCKFRAGEN / WIDERSTAND: Wenn der Nutzer Fragen stellt oder den Sinn hinterfragt, antworte extrem kurz und sachlich (z. B. 'Es hilft mir, Ihr Verhalten besser einzuordnen.') und stelle direkt die nächste Frage.
10. MAXIMALE KÜRZE: Halte deine Textbeiträge extrem kurz (maximal 1-2 Sätze pro Antwort).
11. SIEZEN: Sprich den Nutzer im gesamten Interview höflich mit 'Sie' an.


12. BEENDIGUNG: Sobald du alle Facetten im freien Gespräch diagnostisch ausreichend abgedeckt hast, verabschiede dich freundlich und platziere am Ende deiner allerletzten Nachricht exakt das Wort '[INTERVIEW_FERTIG]' (inklusive der eckigen Klammern).


# DIAGNOSTIK-LEITFADEN: Trait Self-Descriptive Inventory


BESCHREIBUNGEN:
{TSDI_BESCHREIBUNGEN}

ITEMS:
{TSDI_ITEMS}

DEINE ANTWORT-STRUKTUR:
Du musst deine Antwort zwingend als ein valides JSON-Objekt formatieren. Das JSON-Objekt muss exakt diese zwei Felder enthalten:
1. "aktuelle_facette": Eine Zahl von 0 bis 14. Gibt an, welche Facette die Testperson mit ihrer LETZTEN Antwort gerade beantwortet hat. Wenn du noch ganz am Anfang (beim Einstieg) bist, ist es 0. Wenn die erste Facette (A-Co) erfolgreich besprochen wurde, wechselst du auf 1, u.s.w.
2. "interviewer_text": Deine Frage oder Antwort an den Nutzer.
"""

#--- Condition Configs --------------------------------------------------------------------------------------
CONDITION_CONFIGS = {
    "structured-write": {
        "system_prompt": SYSTEM_PROMPT_STRUCTURED,
        "init_message": json.dumps({
            "aktuelle_facette": 0,
            "interviewer_text": "Vielen Dank für Ihre Teilnahme! Lassen Sie uns direkt beginnen. Würden Sie sagen, dass Sie andere Leute immer freundlich behandeln?"
        })
    },
    "open-write": {
        "system_prompt": SYSTEM_PROMPT_OPEN,
        "init_message": json.dumps({
            "aktuelle_facette": 0,
            "interviewer_text": "Vielen Dank für Ihre Teilnahme! Wir beginnen nun mit dem Interview. Erzählen Sie doch zu Beginn einfach mal: Was haben Sie gestern so erlebt?"
        })
    }
}

def main():
    st.set_page_config(page_title="Persönlichkeits-Diagnostik", page_icon="🧠")
    
    if "step" not in st.session_state:
        params = st.query_params
        st.session_state.default_id = params.get("caseNumber", "")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.condition = random.choice(["structured-write", "structured-write"])
        st.session_state.current_facet_count = 0
        st.session_state.research_consent = False

    # --- PHASE 1: WILLKOMMEN ---
    if st.session_state.step == "welcome":
        st.title("Willkommen zum Interview 🤖")
        st.write("Bitte geben Sie Ihre Daten ein, um mit dem Interview zu beginnen.")
        
        st.markdown("""
        **Anleitung zur Generierung Ihres VP-Codes:**
        * Geben Sie als erstes die Anzahl der Buchstaben des (ersten) Vornamens Ihrer Mutter ein (z.B. 04)
        * Geben Sie als zweites die letzten beiden Buchstaben des Mädchen-(Geburts-)namens der Mutter ein (z.B. ER)
        * Geben Sie als drittes die letzten beiden Buchstaben des (ersten Vornamens) des Vaters ein (z.B. NS)
        * Geben Sie als viertes den Tag Ihres Geburtstags ein (z.B. 24)

        Ein Versuchspersonencode könnte beispielsweise so aussehen: 04ERNS24
        * Erster Vorname der Mutter: *Anna* (04 Buchstaben)
        * Nachname der Mutter: *Müller* (ER als Endung)
        * Erster Vorname des Vaters: *Hans* (NS als Endung)
        * Eigener Geburtstag: *24.12.1993* (Tag.Monat.Jahr)
        """)
        
        vp_code_input = st.text_input("VP-Code (Teilnehmer-Code)", value=st.session_state.default_id, placeholder="z.B. 04ERNS24")
        matrikel_input = st.text_input("Matrikelnummer", placeholder="z.B. 1234567")
        
        if st.button("Weiter zur Studienbeschreibung"):
            if not vp_code_input.strip() or not matrikel_input.strip():
                st.error("Bitte füllen Sie beide Felder aus.")
            else:
                st.session_state.participant_id = vp_code_input.strip()
                st.session_state.matrikelnummer = matrikel_input.strip()
                st.session_state.step = "consent"
                st.rerun()

    # --- PHASE 2: EINWILLIGUNG ---
    elif st.session_state.step == "consent":
        st.title("Informationen zur Studie & Datenschutz 📝")
        st.markdown("""
        ### Beschreibung & Zweck der Studie
        Dieses KI-gestützte Interview dient der Persönlichkeitsdiagnostik. Am Ende erhalten Sie eine Auswertung Ihrer Big Five.
        * **Verpflichtung:** Die Teilnahme ist Teil der Übungsleistung. Wer nicht teilnimmt, erhält keinen Credit.
        * **Ehrlichkeit:** Keine Pflicht zur Wahrheit, aber fiktive Angaben verfälschen die Auswertung.
        * **Ethikvotum:** Bewilligt unter **[PLATZHALTER: Ethikantrag-ID]**.
        
        ### Datenschutz
        * **OpenAI API:** Daten werden verschlüsselt übertragen, nicht zum Training genutzt und nach 30 Tagen gelöscht.
        * **Speicherung:** Daten landen auf der sicheren Nextcloud der Universität Ulm.
        """)
        
        consent_checked = st.checkbox("Ich habe die oben genannten Informationen gelesen und stimme der anonymisierten Nutzung und Speicherung meiner Chatdaten zu Forschungs- und Lehrzwecken zu.")
        if st.button("Interview starten"):
            if consent_checked:
                st.session_state.research_consent = True
                st.session_state.step = "chat"
                
                config = CONDITION_CONFIGS[st.session_state.condition]
                                
                st.session_state.messages = [
                    {"role": "system", "content": config["system_prompt"]},
                    {"role": "assistant", "content": config["init_message"]}
                ]
                st.rerun()
            else:
                st.warning("Bitte stimmen Sie zu.")

    # --- PHASE 3: CHAT ---
    elif st.session_state.step == "chat":
        st.title("Interview im Dialog 💬")

        # Read facet progress
        if st.session_state.messages:
            last_ai_msg = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"][-1]
            try:
                msg_data = json.loads(last_ai_msg)
                st.session_state.current_facet_count = min(max(0, int(msg_data.get("aktuelle_facette", 0))), TOTAL_FACETS)
            except:
                pass

        progress_percentage = float(st.session_state.current_facet_count) / float(TOTAL_FACETS)
        st.markdown(f"Erfasste Facetten: {st.session_state.current_facet_count} von {TOTAL_FACETS}")
        st.progress(progress_percentage)
        st.divider()

        # Inject CSS for scrollable chat container
        st.markdown("""
        <style>
        .chat-container {
            height: 35vh;
            overflow-y: auto;
            display: flex;
            flex-direction: column-reverse;
            ...
        }
        .chat-bubble-user {
            align-self: flex-end;
            background-color: #DCF8C6;
            color: #000;
            padding: 0.6rem 1rem;
            border-radius: 16px 16px 2px 16px;
            max-width: 75%;
            margin: 0.3rem 0;
            font-size: 0.95rem;
        }
        .chat-bubble-ai {
            align-self: flex-start;
            background-color: #FFFFFF;
            color: #000;
            padding: 0.6rem 1rem;
            border-radius: 16px 16px 16px 2px;
            max-width: 75%;
            margin: 0.3rem 0;
            font-size: 0.95rem;
            border: 1px solid #e0e0e0;
        }
        .chat-scroll-anchor { height: 1px; }
        </style>
        """, unsafe_allow_html=True)

        # Build chat HTML
        chat_html = '<div class="chat-container" id="chat-box">'
        interview_ended = False

        for msg in reversed(list(st.session_state.messages)):
            if msg["role"] == "system":
                continue
            if msg["role"] == "assistant":
                try:
                    data = json.loads(msg["content"])
                    text_content = data.get("interviewer_text", "")
                    if "[INTERVIEW_FERTIG]" in text_content:
                        interview_ended = True
                    text_content = text_content.replace("[INTERVIEW_FERTIG]", "").strip()
                except:
                    text_content = msg["content"]
                chat_html += f'<div class="chat-bubble-ai">🤖 {text_content}</div>'
            else:
                chat_html += f'<div class="chat-bubble-user">{msg["content"]}</div>'

        chat_html += '<div class="chat-scroll-anchor" id="bottom"></div></div>'

        # Auto-scroll to bottom
        st.markdown(chat_html, unsafe_allow_html=True)

        st.components.v1.html("""
        <script>
            function scrollChat() {
                const frames = window.parent.document.querySelectorAll('#chat-box');
                if (frames.length > 0) {
                    frames[0].scrollTop = frames[0].scrollHeight;
                }
            }
            scrollChat();
            setTimeout(scrollChat, 100);
            setTimeout(scrollChat, 400);
        </script>
        """, height=0)

        if interview_ended:
            st.success("Das Interview wurde erfolgreich beendet.")
            if st.button("Nächste Seite"):
                st.session_state.step = "ux_survey"
                st.rerun()
        else:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            user_input = st.chat_input("Ihre Antwort hier tippen...")

            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                api_success = False
                
                with st.spinner("🤖 Interviewer überlegt..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=st.session_state.messages,
                            response_format={"type": "json_object"}
                        )
                        ai_msg = response.choices[0].message.content
                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                        api_success = True
                    except Exception as e:
                        st.error(f"KI Fehler: {e}")
                
                # Cloud-Speicherung nur triggern, wenn API erfolgreich war
                if api_success:
                    full_data = {
                        "participant_id": st.session_state.get("participant_id", "unknown"),
                        "condition": st.session_state.condition,
                        "research_consent": st.session_state.research_consent,
                        "ux_responses": st.session_state.get("ux_responses", {}),
                        "chat": st.session_state.messages
                    }
                    threading.Thread(target=save_to_nextcloud, args=(st.session_state.participant_id, full_data), daemon=True).start()
                st.rerun()
    # --- PHASE 4: UX Fragebogen ---
    elif st.session_state.step == "ux_survey":
        st.title("Kurze Bewertung der Erfahrung 📋")
        st.write("Bevor Sie Ihre Auswertung sehen, bitten wir Sie, kurz Ihre Erfahrung mit dem Interview zu bewerten.")
        st.divider()

        # --- PLACEHOLDER: Replace these with your actual UX questionnaire items ---
        st.subheader("🚧 Fragebogen-Platzhalter")
        st.info("Hier wird der UX-Fragebogen eingebettet (z.B. UEQ, AttrakDiff, NASA-TLX o.ä.).")

        with st.form("ux_form"):
            st.markdown("**Beispiel-Items (bitte ersetzen):**")
            
            q1 = st.slider("Das Interview war einfach zu verstehen.", 1, 7, 4)
            q2 = st.slider("Ich fühlte mich während des Interviews wohl.", 1, 7, 4)
            q3 = st.slider("Die KI wirkte natürlich und menschlich.", 1, 7, 4)
            q4 = st.text_area("Haben Sie weitere Anmerkungen zum Interview?", placeholder="Optionaler Freitext...")

            submitted = st.form_submit_button("Weiter zur Auswertung")
            if submitted:
                st.session_state.ux_responses = {
                    "q1_verstaendlichkeit": q1,
                    "q2_wohlbefinden": q2,
                    "q3_natuerlichkeit": q3,
                    "q4_freitext": q4
                }
                st.session_state.step = "results"
                st.rerun()

    # --- PHASE 4: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")
        if "data_saved" not in st.session_state: st.session_state.data_saved = False

        if "ai_bfi" not in st.session_state:
            with st.spinner("KI Analyse läuft..."):
                try:
                    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                    
                    clean_messages = []
                    for m in st.session_state.messages:
                        if m["role"] == "system": continue
                        if m["role"] == "assistant":
                            try:
                                clean_messages.append(f"Interviewer: {json.loads(m['content']).get('interviewer_text', '')}")
                            except:
                                clean_messages.append(f"Interviewer: {m['content']}")
                        else:
                            clean_messages.append(f"Teilnehmer: {m['content']}")
                            
                    chat_text = "\n".join(clean_messages)
                    
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Analysiere den Chat auf Big Five (1-5). Antworte NUR im JSON-Format mit den exakten Keys: 'Extraversion', 'Verträglichkeit', 'Gewissenhaftigkeit', 'Neurotizismus', 'Offenheit'."},
                            {"role": "user", "content": f"Hier ist der Chatverlauf:\n{chat_text}"}
                        ],
                        response_format={"type": "json_object"}
                    )
                    st.session_state.ai_bfi = json.loads(res.choices[0].message.content)
                except Exception as e:
                    st.error(f"Fehler bei der Analyse: {e}")
                    st.session_state.ai_bfi = {t: 0 for t in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]}

        for t in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
            ki_wert = st.session_state.ai_bfi.get(t, 0)
            st.metric(f"Geschätzte Ausprägung: {t}", f"{ki_wert} / 5")
            st.progress(float(ki_wert) / 5.0 if ki_wert else 0.0)

        st.divider()

        if not st.session_state.data_saved:
            if st.button("Ergebnisse final speichern & beenden"):
                final_payload = {
                    "participant_id": st.session_state.participant_id,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
                     "ux_responses": st.session_state.get("ux_responses", {}),
                    "ai_assessment": st.session_state.ai_bfi,
                    "chat": st.session_state.messages
                }
                if save_to_nextcloud(st.session_state.participant_id, final_payload):
                    st.session_state.data_saved = True
                    st.rerun()
                else:
                    st.error("Speicherfehler.")
        else:
            st.success("Daten erfolgreich gespeichert!")
            col_a, col_b = st.columns(2)
            with col_a: st.link_button("Zur Uni-Webseite", "https://www.uni-ulm.de/in/psy-dia/forschung/an-studien-teilnehmen/")
            with col_b: 
                if st.button("🔄 APP RESET"): reset_app()

if __name__ == "__main__":
    main()
