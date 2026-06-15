import streamlit as st
from openai import OpenAI
import json
import requests
import uuid
import threading

# --- KONFIGURATION & HELPER ---
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


# --- TSDI LEITFADEN ---
TSDI_BESCHREIBUNGEN = """
<BESCHREIBUNGEN>
DIMENSIONEN:
Extraversion (E): Personen mit hoher Ausprägung in diesem Bereich lassen sich als gesellig, gesprächig, freundlich, unternehmensfreudig und aktiv beschreiben. Sie mögen die Gesellschaft andere, fühlen sich wohl in Gruppen, sind aber auch durchsetzungsfähig, selbstbewusst, dominant und lieben aufregenden Situationen und Stimulierungen. Personen mit niedriger Ausprägung in diesem Bereich sind eher zurückhaltend, ruhig, ausgeglichen und bedachtsam. Sie bevorzugen eher, allein zu sein. Introversion wird weniger als der Gegensatz von Extraversion, sondern mehr als das Fehlen von Extraversion beschrieben.
Neurotizismus (N) : Neurotizismus erfasst Unterschiede zwischen Personen hinsichtlich ihrer gefühlsmäßigen Robustheit einerseits und ihrer emotionalen Empfindlichkeit bzw. Ansprechbarkeit andererseits. Personen mit hoher Ausprägung in diesem Bereich sind empfindlicher und neigen unter Stress dazu, leichter aus dem Gleichgewicht zu kommen. Sie entwickeln eher unangepasste Formen der Problembewältigung, neigen zu unrealistischen Ideen und sind weniger in der Lage, ihre Bedürfnisse zu kontrollieren. Personen mit niedriger Ausprägung in diesem Bereich beschreiben sich als ausgeglichen, emotional stabil und robust und geraten nicht so leicht aus der Fassung. Charakteristisch für diese Personen ist, dass sie Gefühlszustände nicht so stark erleben.
Gewissenhaftigkeit (C): Die Grundlage der Gewissenhaftigkeit bilden Unterschiede beim Planen, Organisieren und Ausführen von Aufgaben. Personen mit einer hohen Ausprägung beschreiben sich als eher zielstrebig, willensstark und entschlossen, während Personen mit einer niedrigen Ausprägung ihre Zielsetzungen mit geringerem Engagement verfolgen.
Verträglichkeit (A): Mit dieser Dimension werden Einstellungen und gewohnheitsmäßige Verhaltensweisen in sozialen Beziehungen umschrieben. Personen mit hoher Ausprägung sind hilfsbereit, entgegenkommend, vertrauensbereit und bemüht anderen zu helfen. Sie begegnen anderen Menschen mit Wohlwollen, neigen zu Gutmütigkeit, sind bereit, in Auseinandersetzungen nachzugeben und können im Extremfall als unterwürfig oder abhängig erscheinen. Personen mit niedriger Ausprägung beschreiben sich als eher egozentrisch, misstrauisch gegenüber den Intentionen anderer, grob, sowie wenig geneigt zu kooperativem Verhalten und mit einer Präferenz für wettbewerbsorientiertes Verhalten.
Offenheit (O): Personen mit hoher Ausprägung in diesem Bereich sind interessiert an neuen Erfahrungen, Erlebnissen, Eindrücken. Sie geben an ein reges Fantasieleben zu haben und eigene positive wie negative Gefühle sehr deutlich wahrzunehmen. Sie lassen sich auf neue Ideen ein und sind unkonventionell in ihren Wertorientierungen. Personen mit niedrigen Ausprägungen in diesem Bereich lassen sich als eher konventionell und konservativ eingestellt beschrieben. Sie ziehen Bekanntes und Bewährtes dem Neuen vor. Emotionale Reaktionen sind weniger intensiv, der Bereich der Interessen ist eingeschränkt und diesen Interessen wird auch nicht mit so starker Intensität nachgegangen, im Gegensatz zu Personen mit hoher Ausprägung.
Ehrlichkeit-Bescheidenheit (HH): Personen mit sehr niedrigen Werten in der Skala "Ehrlichkeit-Bescheidenheit" neigen dazu, sich zu verstellen, um ihre Ziele zu erreichen. Sie nehmen Regeln häufig nicht so genau, streben nach materiellem Reichtum und Ansehen und neigen dazu, sich anderen gegenüber privilegiert und überlegen zu fühlen. Personen mit sehr hohen Werten in dieser Skala hingegen verhalten sich stets authentisch und ehrlich. Sie vermeiden es, andere zu ihren eigenen Gunsten zu beeinflussen, und handeln stets fair. Sie streben weder Luxusgüter noch einen hohen sozialen Status an, noch haben sie den Anspruch, bevorzugt behandelt zu werden.

FACETTEN:
### Dimension Extraversion (E)
- Die Facette „Soziale Aktivität (E-So)“ erfasst die Tendenz unter Leute zu gehen. Personen mit niedriger Ausprägung bleiben lieber für sich und beschäftigen sich allein, wohingegen Personen mit hoher Ausprägung häufig auf Partys anzutreffen sind.
- Die Facette „Selbstbewusstsein (E-SB)“ erfasst die Tendenz selbstsicher zu sein. Personen mit niedriger Ausprägung sind schüchtern und meiden es Aufmerksamkeit zu bekommen, wohingegen Personen mit hoher Ausprägung auch gerne mal im Zentrum der Aufmerksamkeit stehen.
- Die Facette „Durchsetzungsfähigkeit (E-A)“ erfasst die Tendenz in Gruppen die Führung zu übernehmen. Personen mit niedriger Ausprägung sind in Gruppen eher zurückhaltend, wohingegen Personen mit hoher Ausprägung großen Einfluss innerhalb von Gruppe haben.
### Dimension Neurotizismus (N)
- Die Facette „Depression (N-D)“ erfasst die Tendenz niedergeschlagen zu sein. Personen mit niedriger Ausprägung empfinden häufig positive Emotionen, wie Freude, wohingegen Personen mit hoher Ausprägung oft negative Emotionen, wie Traurigkeit empfinden.
- Die Facette „Nervosität (N-St)“ erfasst die Tendenz schnell nervös oder leicht gestresst zu sein. Personen mit niedriger Ausprägung bleiben auch unter großem Druck gelassen, wohingegen Personen mit hoher Ausprägung schon bei geringer Belastung unruhig werden und sich gestresst fühlen.
- Die Facette „Reizbarkeit (N-Ir)“ erfasst die Tendenz schnell emotional zu werden. Personen mit niedriger Ausprägung behalten stets Ruhe, wohingegen sich Personen mit hoher Ausprägung durch Belastung leicht aus dem Konzept bringen lassen und sehr emotional reagieren.
### Dimension Gewissenhaftigkeit (C)
- Die Facette „Fleiß (C-Hw)“ erfasst die Tendenz hart und fokussiert zu arbeiten. Personen mit niedriger Ausprägung neigen dazu faul zu sein und Aufgaben nicht zu Ende zu bringen, wohingegen Personen mit hoher Ausprägung sich immer bemühen Arbeiten rechtzeitig und vollständig zu erledigen.
- Die Facette „Organisation (C-O)“ erfasst die Tendenz ordentlich beim Erledigen von Aufgaben zu sein. Personen mit niedriger Ausprägung sind oft verspätet und halten ihre Umgebung nicht ordentlich, wohingegen Personen mit hoher Ausprägung viel Zeit für Planung und Struktur aufwenden.
### Dimension Verträglichkeit (A)
- Die Facette „Freundlichkeit (A-Fr)“ erfasst die Tendenz sich anderen gegenüber fröhlich und freundlich zu verhalten. Personen mit niedriger Ausprägung kommen mit anderen Menschen eher schlecht zurecht, wohingegen Personen mit hoher Ausprägung als angenehme Personen wahrgenommen werden.
- Die Facette „Hilfsbereitschaft (A-H)“ erfasst die Tendenz anderen bei Problemen zu helfen. Personen mit niedriger Ausprägung neigen zu Egoismus, wohingegen Personen mit hoher Ausprägung großzügig und uneigennützig sind.
- Die Facette „Rücksichtnahme (A-Co)“ erfasst die Tendenz höflich und rücksichtsvoll zu sein. Personen mit niedriger Ausprägung achten nicht auf die Gefühle anderer, wohingegen Personen mit hoher Ausprägung stets versuchen nett zu anderen zu sein.
### Dimension Offenheit (O)
- Die Facette „Intellekt (O-In)" erfasst die Tendenz sich mit intellektuellen Themen zu beschäftigen. Personen mit niedriger Ausprägung meiden komplexe Diskussionen, wohingegen Personen mit hoher Ausprägung generell neugierig sind.
- Die Facette „Wissenschaftliches Interesse (O-Sc)" erfasst die Tendenz sich häufig mit wissenschaftlichen Themen auseinanderzusetzen. Personen mit niedriger Ausprägung meiden solche Themen, wohingegen sich Personen mit hoher Ausprägung wissenschaftlich weiterbilden.
- Die Facette „Reflexion (O-R)" erfasst die Tendenz über sich, eigene Gefühle und komplexe Zusammenhänge nachzudenken. Personen mit niedriger Ausprägung denken selten mehr als einmal über ein Thema nach, wohingegen Personen mit hoher Ausprägung sich viel Zeit nehmen, um über Hintergründe zu reflektieren.
### Dimension Ehrlichkeit-Bescheidenheit (HH)
- Die Facette „Aufrichtigkeit (HH-Si)“ zeigt auf, wie authentisch eine Person im zwischenmenschlichen Kontakt ist. Personen mit niedriger Ausprägung in dieser Skala verstellen sich manchmal, um persönliche Ziele zu erreichen. Personen mit hoher Ausprägung verhalten sich hingegen stets aufrichtig und unverstellt. Sie beeinflussen andere nicht zu ihrem eigenen Vorteil.
- Die Facette "Fairness (HH-Fa)" beschreibt, wie ehrlich und regelkonform das Verhalten einer Person ist. Personen mit niedriger Ausprägung in dieser Skala neigen dazu, Regeln nicht so genau zu nehmen oder sogar zu brechen, um sich einen Vorteil zu verschaffen. Für Personen mit hoher Ausprägung geht Ehrlichkeit gegenüber ihren Mitmenschen und der Gesellschaft über alles und sie bereichern sich nicht auf Kosten anderer.
- Die Facette "Bescheidenheit (HH-Mo)" zeigt, wie bescheiden jemand in Bezug auf sich selbst ist. Personen mit niedriger Ausprägung in dieser Skala neigen dazu, sich anderen gegenüber privilegiert und überlegen zu fühlen. Personen mit hoher Ausprägung betrachten sich und andere Menschen als gleichwertig und beanspruchen für sich keine besondere Behandlung.
</BESCHREIBUNGEN>
"""


TSDI_ITEMS = """
## Skalen auf Facettenebene
### Dimension Verträglichkeit (A)
#### Facette "Rücksichtnahme" (A-Co):
- Item tsdi42_02_A_Co080: Ich behandle andere Leute immer freundlich.
- Item tsdi42_21_A_Co207: Ich versuche zu jedem freundlich zu sein, den ich kenne.
- Item tsdi42_22_A_Co209: Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.
#### Facette "Freundlichkeit" (A-Fr):
- Item tsdi42_24_A_Fr066: Man hält mich für jemanden mit dem man einfach gut auskommt.
- Item tsdi42_12_A_Fr084: Ich komme mit den meisten Menschen gut zurecht.
- Item tsdi42_36_A_Fr220: Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.
#### Facette "Hilfsbereitschaft" (A-H):
- Item tsdi42_10_A_H064: Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.
- Item tsdi42_40_A_H068: Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.
- Item tsdi42_39_A_H213: Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.
### Dimension Gewissenhaftigkeit (C)
#### Facette "Fleiß" (C-Hw):
- Item tsdi42_04_C_Hw126: Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.
- Item tsdi42_25_C_Hw137: Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.
- Item tsdi42_37_C_Hw167: Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.
#### Facette "Organisation" (C-O):
- Item tsdi42_14_C_O0153: Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.
- Item tsdi42_41_C_O0157: Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.
- Item tsdi42_32_C_O0162: Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.
### Dimension Extraversion (E)
#### Facette "Durchsetzungsfähigkeit" (E-A):
- Item tsdi42_35_E_A002: Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.
- Item tsdi42_28_E_A004: Ich neige dazu, in Gruppen die Führung zu übernehmen.
- Item tsdi42_03_E_A009: Ich habe eine menge Einfluss auf andere Leute.
#### Facette "Selbstbewusstsein" (E-SB):
- Item tsdi42_19_E_SB010: Ich bin eine sehr schüchterne Person.
- Item tsdi42_08_E_SB014: Meine Freunde halten mich für schüchtern.
- Item tsdi42_18_E_SB026: Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.
#### Facette "Soziale Aktivität" (E-So):
- Item tsdi42_33_E_So007: Ich bin gerne wo viel los ist.
- Item tsdi42_26_E_So012: Ich gebe mir große Mühe Leute kennen zu lernen.
- Item tsdi42_16_E_So028: Ich mag Partys auf denen viele Leute sind.
### Dimension Neurotizismus (N)
#### Facette "Depression" (N-D):
- Item tsdi42_07_N_D039: Es gibt Zeiten in denen ich mich selbst bedaure.
- Item tsdi42_15_N_D054: Manchmal bin ich entmutigt und möchte am liebsten aufgeben.
- Item tsdi42_30_N_D055: Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.
#### Facette "Reizbarkeit" (N-Ir):
- Item tsdi42_09_N_Ir034: Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.
- Item tsdi42_05_N_Ir058: Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.
- Item tsdi42_06_N_Ir070: Ich kann Kritik nicht sehr gut akzeptieren.
#### Facette "Nervosität" (N-St):
- Item tsdi42_29_N_St037: Ich fühle mich oft müde und erschöpft.
- Item tsdi42_38_N_St040: Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.
- Item tsdi42_11_N_St043: Ich bin oft zittrig und angespannt.
### Dimension Offenheit (O)
#### Facette "Intellekt" (O-In):
- Item tsdi42_31_O_In094: Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.
- Item tsdi42_23_O_In106: Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.
- Item tsdi42_27_O_In118: Ich besitze ein hohes Maß an intellektueller Neugier.
#### Facette "Reflexion" (O-R):
- Item tsdi42_17_O_R100: Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.
- Item tsdi42_42_O_R117: Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.
- Item tsdi42_34_O_R120: Ich lese gerne Gedichte.
#### Facette "Wissenschaftliches Interesse" (O-Sc):
- Item tsdi42_13_O_Sc103: Ich denke oft über die Wunder der Natur nach.
- Item tsdi42_20_O_Sc114: Die Evolutionstheorie fasziniert mich.
- Item tsdi42_01_O_Sc116: Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.
### Dimension Ehrlichkeit-Bescheidenheit (HH)
#### Facette "Aufrichtigkeit" (HH-Si):
- Item x42i47_hh_si001_t2: Wenn ich von einer Person, die ich nicht mag, etwas will, verhalte ich mich dieser Person gegenüber sehr nett um es zu bekommen.
- Item x42i15_hh_si005_t2: Ich würde keine Schmeicheleien benutzen, um eine Gehaltserhöhung zu bekommen oder befördert zu werden, auch wenn ich wüsste, dass es erfolgreich wäre.
- Item x42i04_hh_si009_t2: Wenn ich von jemandem etwas will, lache ich auch noch über dessen schlechteste Witze.
#### Facette "Fairness" (HH-Fa):
- Item x42i31_hh_fa006_t2: Ich würde in Versuchung geraten, Diebesgut zu kaufen, wenn ich knapp bei Kasse wäre.
- Item x42i17_hh_fa010_t2: Ich würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.
- Item x42i08_hh_fa002_t2: Wenn ich wüsste, dass ich niemals erwischt werde, wäre ich bereit, eine Million zu stehlen.
#### Facette "Bescheidenheit" (HH-Mo):
- Item x42i51_hh_mo008_t2: Ich will nicht, dass andere Leute mich behandeln, als ob ich ihnen überlegen sei.
- Item x42i34_hh_mo004_t2: Ich bin eine ganz normale Person, die nicht besser ist als andere.
- Item x42i24_hh_mo016_t2: Ich will, dass alle wissen, dass ich eine wichtige angesehene Person bin.
"""


TOTAL_FACETS = 17


# Das Wort 'JSON' MUSS im Prompt stehen, damit der response_format Modus funktioniert.
# Technische Ausgabe-Anweisung: Generiere die Antwort immer so, dass sie mit dem geforderten JSON-Format der API kompatibel ist.
SYSTEM_PROMPT = f"""Du bist ein erfahrener psychologischer Interviewer. Dein Ziel ist es, ein rein diagnostisches, exploratives und offenes Interview zu führen, um die 17 Facetten des erweiterten 'Trait Self-Descriptive Inventory (TSDI)' effizient zu erfassen.

STRIKTE TURN-TAKING-REGEL (WICHTIGSTE REGEL):
- Gib pro Interaktion/Nachricht IMMER NUR EINE EINZIGE FRAGE aus.
- Stelle niemals zwei Fragen in einem Absatz oder in einer Nachricht.
- Warte nach jeder Frage zwingend die Antwort des Nutzers ab.

STRIKTE REIHENFOLGE DER DIMENSIONEN:
Gehe die Dimensionen exakt in dieser Reihenfolge durch: 
1. Extraversion (E)
2. Neurotizismus (N)
3. Gewissenhaftigkeit (C)
4. Verträglichkeit (A)
5. Offenheit für Erfahrungen (O)
6. Ehrlichkeit-Bescheidenheit (HH)

Springe nicht zwischen den Dimensionen hin und her. Erkunde eine Dimension und all ihre zugehörigen Facetten vollständig, bevor du zur nächsten Hauptdimension übergehst.

ABLAUF-LEITFADEN PRO DIMENSION & FACETTE:
Befolge für jede einzelne Dimension und deren Facetten exakt diese chronologische Reihenfolge. Gehe erst zum nächsten Schritt, wenn der vorherige Schritt durch eine Antwort des Nutzers abgeschlossen ist:

1. DIMENSIONS-BESCHREIBUNG: Gib die Definition der aktuellen Hauptdimension aus (Nutze die Beschreibungen zwischen den Tags <BESCHREIBUNGEN> und </BESCHREIBUNGEN>). Nenne dabei auch kurz die zugehörigen Facetten. (KEINE Frage in dieser Nachricht stellen, sondern direkt zu Schritt 2 übergehen).
2. DIMENSIONS-VERGLEICH: Frage den Nutzer direkt im Anschluss an die Beschreibung, wie er sich auf dieser Dimension im Vergleich zu anderen Personen einschätzt. (Warte auf Antwort).
3. DIMENSIONS-AUSPRÄGUNG: Frage den Nutzer, in welchen Aspekten dieser Dimension er besonders heraussticht (hohe Ausprägung) oder wo er eher niedrig ausgeprägt ist. (Warte auf Antwort).4. ÜBERGANG ZU FACETTE 1: Mache einen kurzen, prägnanten Übergang zur 1. Facette der jeweiligen Dimension.
4. ÜBERGANG ZU FACETTE 1: Mache einen kurzen, prägnanten Übergang zur 1. Facette der jeweiligen Dimension.
5. FACETTEN-VERGLEICH: Frage den Nutzer, wie er sich auf dieser spezifischen Facette im Vergleich zu anderen Personen einschätzt. (Warte auf Antwort).
6. FACETTEN-ALLTAG: Frage den Nutzer nach einem konkreten Beispiel oder einer Alltagssituation, in der sich diese Eigenschaft bei ihm besonders deutlich zeigt (z.B. was ihm dabei leicht fällt oder wo er an Grenzen stößt). (Warte auf Antwort).
7. ÜBERGANG ZU FACETTE 2: Mache einen kurzen, prägnanten Übergang zur 2. Facette dieser Dimension und wiederhole die Schritte 5 und 6. Wiederhole dies für alle Facetten der Dimension, bevor du mit Schritt 1 für die nächste Hauptdimension fortfährst.

VERTIEFUNG, SÄTTIGUNG & AUSNAHMESITUATIONEN:
- Max-Fragen-Regel: Stelle maximal 5 Fragen pro Facette (einschließlich der Fragen aus Schritt 5 und 6 sowie eventueller Nachfragen).
- REGELESTREUE VERTIEFUNG (AUSNAHMEN ERFORSCHEN): Wenn ein Nutzer eine Tendenz sehr stark beschreibt, nutze eine deiner verfügbaren Fragen, um nach *Ausnahmesituationen* zu fragen (z. B.: "Gibt es Momente oder Situationen, in denen Sie sich ganz anders verhalten, als Sie es gerade beschrieben haben? Wie sehen diese aus?"). Das liefert wertvolle diagnostische Tiefe.
- Nutze offene W-Fragen, um Facetten subtil zu explorieren, falls die Antworten zu einsilbig sind.
- Prüfe nach jeder Antwort des Nutzers kritisch: *Könnte ich anhand dieser Aussage die TSDI-Items dieser Facette bereits einschätzen?*
   - Wenn NEIN (und das Max-Fragen-Limit nicht erreicht ist): Frage gezielt nach konkreten Verhaltensweisen, Motiven oder den oben genannten Ausnahmen nach.
   - Wenn JA (Sättigung erreicht): Höre sofort auf, in dieser Facette weiterzubohren, und leite elegant zur nächsten Facette oder Dimension über.

WEITERE INTERVIEW-REGELN:
- REINE DIAGNOSTIK – KEINE LÖSUNGEN/STRATEGIEN: Frage NIEMALS nach Lösungen, Hilfsmitteln, Bewältigungsstrategien oder Eisbrechern. Dich interessiert NUR der Ist-Zustand des Verhaltens und wie der Nutzer damit umgeht (nicht, wie er es lösen will).
- SIEZEN: Sprich den Nutzer im gesamten Interview höflich mit 'Sie' an.
- BEENDIGUNG: Sobald du alle Facetten im freien Gespräch diagnostisch ausreichend abgedeckt hast, bedanke dich für das Gespräch, verabschiede dich freundlich und platziere am Ende deiner allerletzten Nachricht exakt das Wort '[INTERVIEW_FERTIG]' (inklusive der eckigen Klammern).

# DIAGNOSTIK-LEITFADEN: Trait Self-Descriptive Inventory (TSDI)
LEITFADEN:
{TSDI_BESCHREIBUNGEN} 

{TSDI_ITEMS}
"""

def main():
    st.set_page_config(page_title="Persönlichkeits-Diagnostik (Unstrukturiert)", page_icon="🧠")
    
    if "step" not in st.session_state:
        params = st.query_params
        st.session_state.default_id = params.get("caseNumber", f"user_{uuid.uuid4().hex[:8]}") # muss das hier stehen, oder kann das weg, also kann casenumber leer bleiben: st.session_state.default_id = params.get("caseNumber", "")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.condition = "open-write"
        st.session_state.current_facet_count = 0
        st.session_state.research_consent = False

    # --- PHASE 1: WILLKOMMEN ---
    if st.session_state.step == "welcome":
        st.title("Willkommen zum Interview 🤖")
        st.write("Bitte geben Sie Ihre Daten ein, um mit dem Interview zu beginnen.")
        
        st.markdown("""
        ##### Anleitung zur Generierung Ihres VP-Codes
        
        1. Geben Sie als erstes die Anzahl der Buchstaben des (ersten) Vornamens Ihrer Mutter ein (z.B. 04).
        2. Geben Sie als zweites die letzten beiden Buchstaben des Mädchen-(Geburts-)namens der Mutter ein (z.B. ER).
        3. Geben Sie als drittes die letzten beiden Buchstaben des (ersten Vornamens) des Vaters ein (z.B. NS).
        4. Geben Sie als viertes den Tag Ihres Geburtstags ein (z.B. 24).
        
        ###### Beispiel:

        Ein Versuchspersonencode könnte beispielsweise so aussehen: **04ERNS24**
        
        - Erster Vorname der Mutter: *Anna* (04 Buchstaben)
        - Nachname der Mutter: *Müller* (ER als Endung)
        - Erster Vorname des Vaters: *Hans* (NS als Endung)
        - Eigener Geburtstag: *24.12.1993* (Tag.Monat.Jahr)
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
        ### Beschreibung der Studie
        Dieses KI-gestützte Interview dient der Persönlichkeitsdiagnostik. 
        Das Gespräch wird von einem KI-Interviewer in einem geführt, und endet automatisch, sobald alle psychologischen Facetten der BigFive im Dialog ausreichend erkundet wurden.
        
        ### Umgang mit Ihren Daten
        * **Speicherung:** Verschlüsselt auf den sicheren Servern der Universität Ulm (**Nextcloud/Cloudstore**).
        * **Anonymisierung:** Die Speicherung erfolgt ausschließlich unter Ihrer Teilnehmer-ID.
        """)
        
        st.divider()
        consent_checked = st.checkbox("Ich stimme der anonymisierten Nutzung und Speicherung meiner Chatdaten zu Forschungszwecken zu.")
        
        if st.button("Interview starten"):
            if consent_checked:
                st.session_state.research_consent = True
                st.session_state.step = "chat"
                
                first_ai_msg = "Vielen Dank für Ihre Teilnahme! Ich bin ein AI Agent und werde im weiteren Verlauf ein persönlichkeitsdiagnostisches Interview mit Ihnen führen. Lassen Sie uns mit dem ersten Thema beginnen: der Dimension 'Extraversion'. Diese Dimension beschreibt, inwiefern Personen gesellig, gesprächig, freundlich und aktiv sind. Menschen mit hoher Ausprägung fühlen sich wohl in Gruppen und mögen aufregende Situationen, während Personen mit niedriger Ausprägung eher zurückhaltend und bedachtsam sind. Wie würden Sie sich im Vergleich zu anderen Personen hinsichtlich Ihrer Extraversion einschätzen?"


# Erzählen Sie doch zu Beginn einfach mal: Was haben Sie gestern so erlebt?"
                
# Erzählen Sie mir ein bisschen von sich – Wie würden Sie sich selbst als Person beschreiben?

# „Erzählen Sie mir von sich und Ihrem Alltag. Was beschäftigt Sie derzeit besonders?“

# „Wenn Sie an Ihr Leben bisher denken: Welche Stationen oder Erfahrungen haben Sie besonders geprägt?“
                
# lieber eine Frage über eine Kindheitserfahrung?

                
                st.session_state.messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "assistant", "content": first_ai_msg}
                ]
                st.rerun()
            else:
                st.warning("Bitte bestätigen Sie die Einwilligungserklärung, um fortzufahren.")

    # --- PHASE 3: CHAT ---
    elif st.session_state.step == "chat":
        st.title("Interview im Dialog 💬")
        
        interview_ended = any("[INTERVIEW_FERTIG]" in m["content"] for m in st.session_state.messages if m["role"] == "assistant")
        
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"].replace("[INTERVIEW_FERTIG]", "").strip())

        if interview_ended:
            st.success("Das Interview wurde von der KI erfolgreich beendet, da alle Facetten explorativ erfasst wurden.")
            if st.button("Zur Auswertung"):
                st.session_state.step = "results"
                st.rerun()
        else:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            user_input = st.chat_input("Ihre Antwort hier tippen...")

            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                with st.spinner("🤖 Interviewer überlegt..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=st.session_state.messages
                        )
                        ai_msg = response.choices[0].message.content
                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                    except Exception as e:
                        st.error(f"KI Fehler: {e}")
                
                full_data = {
                    "participant_id": st.session_state.participant_id,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
                    "chat": st.session_state.messages
                }
                threading.Thread(target=save_to_nextcloud, args=(st.session_state.participant_id, full_data), daemon=True).start()
                st.rerun()

    # --- PHASE 4: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")
        if "data_saved" not in st.session_state: st.session_state.data_saved = False

        if "ai_bfi" not in st.session_state:
            with st.spinner("KI Analyse läuft..."):
                try:
                    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                    chat_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages if m["role"] != "system"])
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Analysiere den Chat auf Big Five (1-5). Antworte NUR JSON mit Keys: 'Extraversion', 'Verträglichkeit', 'Gewissenhaftigkeit', 'Neurotizismus', 'Offenheit'."},
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
                    "id": st.session_state.participant_id,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
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
