# -*- coding: utf-8 -*-
import streamlit as st
from openai import OpenAI
import json
import requests
import uuid
import threading
import random
import time
from datetime import datetime
import io
import hashlib
from streamlit_mic_recorder import mic_recorder

# --- ADMIN KONFIGURATION ---
EMERGENCY_PASSWORD = "SicheresNotfallPasswort123!" # <-- Hier dein Wunschpasswort eintragen

# --- KONFIGURATION & HELPER ------------------------------------------------------------------
# 1) ANPASSUNG: matrikelnummer als Parameter hinzugefügt und save_time entfernt
def save_to_nextcloud(participant_id, matrikelnummer, data_dict, final=True):
    try:
        base_url = "https://cloudstore.uni-ulm.de/remote.php/dav/files/ffg79"
        folder = "Forschungsdaten"
        
        # Dateiname enthält jetzt VP-Code und Matrikelnummer statt Zeitstempel
        if final:
            filename = f"interview_{participant_id}_{matrikelnummer}.json"
        else:
            filename = f"interview_{participant_id}_{matrikelnummer}_preliminary.json"
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

### Dimension Ehrlichkeit-Bescheidenheit (HH)
- Die Facette „Aufrichtigkeit (HH-Si)“ zeigt auf, wie authentisch eine Person im zwischenmenschlichen Kontakt ist. Personen mit niedriger Ausprägung in dieser Skala verstellen sich manchmal, um persönliche Ziele zu erreichen. Personen mit hoher Ausprägung verhalten sich hingegen stets aufrichtig und unverstellt. Sie beeinflussen andere nicht zu ihrem eigenen Vorteil.
- Die Facette "Fairness (HH-Fa)" beschreibt, wie ehrlich und regelkonform das Verhalten einer Person ist. Personen mit niedriger Ausprägung in dieser Skala neigen dazu, Regeln nicht so genau zu nehmen oder sogar zu brechen, um sich einen Vorteil zu verschaffen. Für Personen mit hoher Ausprägung geht Ehrlichkeit gegenüber ihren Mitmenschen und der Gesellschaft über alles und sie bereichern sich nicht auf Kosten anderer.
- Die Facette "Bescheidenheit (HH-Mo)" zeigt, wie bescheiden jemand in Bezug auf sich selbst ist. Personen mit niedriger Ausprägung in dieser Skala neigen dazu, sich anderen gegenüber privilegiert und überlegen zu fühlen. Personen mit hoher Ausprägung betrachten sich und andere Menschen als gleichwertig und beanspruchen für sich keine besondere Behandlung.
</BESCHREIBUNGEN>
"""

TSDI_ITEMS = """
<ITEMS>
## Dimension Verträglichkeit (A)
### 1. Facette "Freundlichkeit" (A-Fr):
- Item tsdi42_24_A_Fr066: Halten andere Menschen Sie für jemanden, mit dem man einfach gut auskommt? Wenn ja, warum? 
- Item tsdi42_12_A_Fr084: Würden Sie sagen, dass Sie mit den meisten Menschen gut zurecht kommen? Warum denken Sie das?
- Item tsdi42_36_A_Fr220: Versuchen Sie, fröhlich zu sein, auch wenn es nicht so gut läuft? Wie oft gelingt Ihnen das? 
### 2. Facette "Rücksichtnahme" (A-Co):
- Item tsdi42_02_A_Co080: Behandeln Sie andere Leute freundlich? Wie häufig tun Sie das und was bedeutet "freundlich behandeln" für Sie konkret?
- Item tsdi42_21_A_Co207: Versuchen Sie immer, zu jedem freundlich zu sein, den Sie kennen? Was tun Sie konkret, um zu jedem freundlich zu sein?
- Item tsdi42_22_A_Co209:  Wie oft gelingt es Ihnen , auch zu Menschen höflich zu sein, die Ihnen gegenüber unfreundlich sind? Was hilft Ihnen, höflich zu bleiben, wenn jemand unfreundlich zu Ihnen ist?
### 3. Facette "Hilfsbereitschaft" (A-H):
- Item tsdi42_10_A_H064: Würden Sie sagen, es bereitet Ihnen Freude, anderen mit ihren Problemen zu helfen? Was für Probleme anderer beschäftigen Sie dabei am meisten?
- Item tsdi42_40_A_H068: Wie oft helfen Sie anderen Leuten, auch wenn nichts für Sie dabei herausspringt? Tun Sie das gerne? was motiviert Sie dabei?
- Item tsdi42_39_A_H213: Sind Sie großzügig, wenn es darum geht, anderen zu helfen und wenn ja, was tun Sie konkret, wenn Sie anderen helfen?

## Dimension Gewissenhaftigkeit (C)
### 4. Facette "Fleiß" (C-Hw):
- Item tsdi42_04_C_Hw126: Führen Sie Dinge, zu denen Sie sich verpflichtet haben, immer zu Ende? 
- Item tsdi42_25_C_Hw137: Würden Sie sich selbst als ausdauernden Arbeiter beschreiben? Was zeigt sich bei Ihnen, wenn Sie besonders ausdauernd arbeiten?
- Item tsdi42_37_C_Hw167: Wenn Sie etwas anfangen, arbeiten Sie dann solange daran, bis es Sie zufriedenstellt? Was tun Sie, wenn eine Aufgabe noch nicht zu Ihrer Zufriedenheit erledigt ist?
### 5. Facette "Organisation" (C-O):
- Item tsdi42_14_C_O0153: Halten Sie Ihre persönlichen Sachen gerne ordentlich und organisiert? Woran merken Sie das? 
- Item tsdi42_41_C_O0157: Entwickeln Sie für Aufgaben einen Plan und halten sich daran? Was für Pläne erstellen Sie typischerweise für Aufgaben?
- Item tsdi42_32_C_O0162: Würden Sie sagen, dass Sie versuchen, vollständig vorbereitet zu sein, bevor Sie eine Aufgabe anpacken? Was gehört für Sie zu einer vollständigen Vorbereitung dazu?

## Dimension Extraversion (E)
### 6. Facette "Durchsetzungsfähigkeit" (E-A):
- Item tsdi42_35_E_A002: Sprechen Sie lauter, wenn Sie meinen, einen wichtigen Beitrag liefern zu können? Wie oft kommt das vor und was sind typische Situationen, in denen Sie lauter sprechen?
- Item tsdi42_28_E_A004: Neigen Sie dazu, in Gruppen die Führung zu übernehmen? Wie sieht das aus?
- Item tsdi42_03_E_A009: Was würden Sie sagen: Wie stark ist der Einfluss, den Sie auf andere Leute haben? Worin zeigt sich das?
### 7. Facette "Selbstbewusstsein" (E-SB):
- Item tsdi42_19_E_SB010: Sind Sie eine schüchterne Person? Was sind Situationen, in denen Ihre Schüchternheit am sträksten auftritt?
- Item tsdi42_08_E_SB014: Halten Ihre Freunde Sie für schüchtern? Was, glauben Sie, lässt Ihre Freunde so über Sie denken?
- Item tsdi42_18_E_SB026: Würden Sie sagen, Sie fühlen sich unwohl, wenn Sie im Zentrum der Aufmerksamkeit stehen? Was an dieser Situation macht Ihnen am meisten zu schaffen?
### 8. Facette "Soziale Aktivität" (E-So):
- Item tsdi42_33_E_So007: Sind Sie gerne dort, wo viel los ist? An was für Orte oder Situationen denken Sie bei dieser Frage?
- Item tsdi42_26_E_So012: Geben Sie sich Mühe, neue Leute kennenzulernen? Wenn ja, wie tun Sie das? 
- Item tsdi42_16_E_So028: Mögen Sie Partys, auf denen viele Leute sind? 

## Dimension Neurotizismus (N)
### 9. Facette "Depression" (N-D):
- Item tsdi42_07_N_D039: Gibt es Zeiten, in denen Sie sich selbst bedauern? Wie oft kommt das vor und was sind typische Anlässe dafür, dass Sie sich selbst bedauern?
- Item tsdi42_15_N_D054: Sind Sie manchmal entmutigt und möchten am liebsten aufgeben? Wie häufig fühlen Sie sich so? 
- Item tsdi42_30_N_D055: Befürchten Sie, dass Sie Ihre Ziele nicht erreichen könnten? Wie häufig kommt das vor? 
### 10. Facette "Reizbarkeit" (N-Ir):
- Item tsdi42_09_N_Ir034: Regen Sie sich manchmal so auf, dass es Ihnen auf den Magen schlägt? Was sind typische Auslöser für diese Reaktion?
- Item tsdi42_05_N_Ir058: Wie klar können Sie denken, wenn Sie aufgebracht sind? Was passiert dann konkret mit Ihren Gedanken?
- Item tsdi42_06_N_Ir070: Wie gut können Sie Kritik akzeptieren? Was fällt Ihnen an Kritik besonders schwer?
### 11. Facette "Nervosität" (N-St):
- Item tsdi42_29_N_St037: Fühlen Sie sich oft müde und erschöpft? Wie häufig kommt das vor?
- Item tsdi42_38_N_St040: Wenn Sie unter großem Stress stehen - Sind Sie dann oft kurz davor zusammenzubrechen? Wie häufig erleben Sie das und Was löst diesen Zustand bei Ihnen typischerweise aus?
- Item tsdi42_11_N_St043: Sind Sie oft zittrig und angespannt? 

## Dimension Offenheit (O)
### 12. Facette "Intellekt" (O-In):
- Item tsdi42_31_O_In094: Führen Sie gerne intellektuelle Diskussionen mit Freunden? Worüber diskutieren Sie dabei am liebsten?
- Item tsdi42_23_O_In106: Finden Sie intellektuelle Themen interessanter als Sport wie Fußball, Tennis oder Basketball?  Was für Themen interessieren Sie dabei besonders?
- Item tsdi42_27_O_In118: Würden Sie sagen, Sie besitzen ein hohes Maß an intellektueller Neugier? 
### 13. Facette "Reflexion" (O-R):
- Item tsdi42_17_O_R100: Wie viel Zeit verbringen Sie damit, die Beweggründe des Verhaltens anderer Leute zu erkunden? Was versuchen Sie dabei herauszufinden?
- Item tsdi42_42_O_R117: Wie viel Zeit verbringen Sie damit, Ihre eigene Gefühlswelt zu erkunden? 
- Item tsdi42_34_O_R120: Lesen Sie gerne Gedichte? Was für Gedichte lesen Sie am liebsten?
### 14. Facette "Wissenschaftliches Interesse" (O-Sc):
- Item tsdi42_13_O_Sc103: Wie oft denken Sie oft über die Wunder der Natur nach? Was für Aspekte der Natur faszinieren Sie dabei am meisten?
- Item tsdi42_20_O_Sc114: Fasziniert Sie die Evolutionstheorie? 
- Item tsdi42_01_O_Sc116: Würden Sie sagen, Sie haben sich viele Gedanken über den Ursprung des Universums gemacht? Was für Fragen zum Ursprung des Universums beschäftigen Sie am meisten?

## Dimension Ehrlichkeit-Bescheidenheit (HH)
### 15. Facette "Aufrichtigkeit" (HH-Si):
- Item x42i47_hh_si001_t2: Wie oft verhalten Sie sich einer Person, die Sie nicht mögen, gegenüber sehr nett, weil Sie etwas von ihr wollen? Was tun Sie dann konkret?
- Item x42i15_hh_si005_t2: Würden Sie Schmeicheleien verwenden, um eine Gehaltserhöhung oder Beförderung zu bekommen? Wie sicher sind Sie sich? 
- Item x42i04_hh_si009_t2:  Angenommen eine Person, von der Sie etwas wollen macht einen schlechten Witz. Würden Sie lachen? Was tun Sie, wenn Ihnen ein Witz gar nicht gefällt, Sie aber etwas von der Person wollen?
### 16. Facette "Fairness" (HH-Fa):
- Item x42i31_hh_fa006_t2: Würden Sie in Versuchung geraten, Diebesgut zu kaufen, wenn Sie knapp bei Kasse wären? Wie stark wäre diese Versuchung? 
- Item x42i17_hh_fa010_t2: Würden Sie behaupten, dass Sie niemals Bestechungsgeld annehmen, egal wie hoch es wäre? Wie sicher sind Sie sich dabei? 
- Item x42i08_hh_fa002_t2:  Wären Sie bereit, eine Million Euro zu stehlen, wenn Sie wüssten, dass Sie niemals erwischt werden? Was würde für Sie in dieser Situation den Unterschied machen?
### 17. Facette "Bescheidenheit" (HH-Mo):
- Item x42i51_hh_mo008_t2: Wie finden Sie es, wenn andere Leute Sie behandeln, als ob Sie ihnen überlegen wären? Was beduetet es für Sie, "überlegen" behandelt zu werden?
- Item x42i34_hh_mo004_t2: Sehen Sie sich als ganz normale Person, die nicht besser ist als andere? Was macht Sie Ihrer Meinung nach zu einer "ganz normalen" Person?
- Item x42i24_hh_mo016_t2: Wie sehr möchten Sie, dass alle wissen, dass Sie eine wichtige, angesehene Person sind? Was würde Ihnen das Gefühl geben, eine wichtige, angesehene Person zu sein?
</ITEMS>
"""

TOTAL_FACETS = 17
MAX_INTERACTIONS = 60

#--- System Prompt Structured ------------------------------------------------------------------------
SYSTEM_PROMPT_STRUCTURED = f"""Du bist ein erfahrener psychologischer Interviewer. Dein Ziel ist es, ein strukturiertes Interview zu führen, um die 17 Facetten des erweiterten TSDI systematisch zu erfassen.

INTERVIEW-REGELN:
* Gehe die Facetten streng sequenziell von 1 bis 17 durch.
* Stelle pro Item EINE verhaltensnahe Frage. Die Items findest du zwischen den Tags <ITEMS> und </ITEMS>.
* Stelle die Items wenn möglich als offene Fragen, auf die man nicht einfach mit ja oder nein antworten kann, bspw. 'Wie großzügig sind Sie, wenn es darum geht, anderen zu helfen?' oder 'Inwieweit versuchen Sie fröhlich zu sein, auch wenn es nicht so gut läuft?

* Vermeide Phrasen wie '<Aussage>. Wie sehen Sie das bei sich?' und verschachtelte Sätze.
* Formuliere die Fragen natürlich und gesprächsnah. Vermeide repetitive Phrasen wie 'Nun zur nächsten Frage:', 'Vielen Dank', 'Das freut mich zu hören', 'interessant' oder 'Das tut mir leid'.
* Sprich den Nutzer mit 'Sie' an.
* Wenn du die Antwort auf das letzte Item erhalten hast, reagiere mit '[INTERVIEW_FERTIG] Damit sind wir am Ende des Interviews angekommen. Ich danke Ihnen für Ihre Offenheit. Schönen Tag noch!'. 
* Wenn der Nutzer antwortet, dass die Frage nicht verstanden wurde, bspw. 'Was meinst du damit?', erkläre die Frage kurz und stelle Sie erneut.
* Wenn dir eine andere Frage gestellt wird, antworte nicht auf die Frage, sondern weise den Nutzer höflich darauf hin, dass du gerade ein diagnostisches Interview mit ihm führst. Stelle die vorherige Frage dann erneut.

LEITFADEN:
{TSDI_BESCHREIBUNGEN}

{TSDI_ITEMS}

DEINE ANTWORT-STRUKTUR:
Du musst deine Antwort zwingend als ein valides JSON-Objekt formatieren. Das JSON-Objekt muss exakt diese zwei Felder enthalten:
1. "aktuelle_facette": Eine Zahl von 1 bis 17. Gibt an, welche Facette die Testperson mit ihrer LETZTEN Antwort gerade beantwortet hat. Wenn du noch ganz am Anfang (beim Einstieg) bist, ist es 1. Wenn die erste Facette (A-Co) erfolgreich besprochen wurde, wechselst du auf 2, u.s.w.
2. "interviewer_text": Deine Frage oder Antwort an den Nutzer.
"""

#--- System Prompt Open -----------------------------------------------------------------------------
SYSTEM_PROMPT_OPEN = f"""Du bist ein erfahrener psychologischer Interviewer. Dein Ziel ist es, ein rein diagnostisches, exploratives und offenes Interview zu führen, um die 17 Facetten des erweiterten 'Trait Self-Descriptive Inventory (TSDI)' effizient zu erfassen.

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
2. DIMENSIONS-VERGLEICH: Frage den Nutzer direkt im Anschluss an die Beschreibung, wie er sich auf dieser Dimension im Allgemeinen im Vergleich zu anderen Personen einschätzt. (Warte auf Antwort).
3. DIMENSIONS-AUSPRÄGUNG: Frage den Nutzer, wie er zu dieser Einschätzung kommt. (Warte auf Antwort). 
4. ÜBERGANG ZU FACETTE 1: Mache einen kurzen, prägnanten Übergang zur 1. Facette der jeweiligen Dimension. Gib die Definition der aktuellen Facette aus (Nutze die Beschreibungen zwischen den Tags <BESCHREIBUNGEN> und </BESCHREIBUNGEN>).
5. FACETTEN-VERGLEICH (FIXE FRAGE 1): Frage den Nutzer, wie er sich auf dieser spezifischen Facette im Vergleich to anderen Personen einschätzt. (Warte auf Antwort).
6a. FACETTEN-ALLTAG (FIXE FRAGE 2): Frage den Nutzer nach einem konkreten Beispiel oder einer Alltagssituation, in der sich diese Eigenschaft bei ihm besonders deutlich zeigt (z.B. was ihm dabei leicht fällt oder wo er an Grenzen stößt). (Warte auf Antwort).
6b. ADAPTIVE VERTIEFUNG (FLEXIBLE FRAGEN): Nutze die verbleibenden Fragen des Budgets (siehe Max-Fragen-Regel), um aktiv und empathisch auf das einzugehen, was der Nutzer in den Schritten 5 und 6a geantwortet hat. Du entscheidest hier völlig frei und adaptiv, welche Nachfragen am hilfreichsten sind, um die Messung auf dieser Facette präzise zu verfeinern (z. B. Nachhaken bei Widersprüchen, Vertiefung unklarer Aussagen oder Erkunden von Ausnahmesituationen). Stelle auch hier immer nur EINE Frage pro Nachricht und prüfe nach jeder Antwort auf diagnostische Sättigung.
7. ÜBERGANG ZU FACETTE 2: Mache einen kurzen, prägnanten Übergang zur 2. Facette dieser Dimension und wiederhole die Schritte 5 bis 6b. Wiederhole dies für alle Facetten der Dimension, bevor du mit Schritt 1 für die nächste Hauptdimension fortfährst.

VERTIEFUNG, SÄTTIGUNG & AUSNAHMESITUATIONEN:
- Max-Fragen-Regel: Stelle 4 Fragen pro Facette (einschließlich der fixen Fragen aus Schritt 5 und 6a sowie der adaptiven Nachfragen aus Schritt 6b).
- REGELESTREUE VERTIEFUNG (AUSNAHMEN ERFORSCHEN): Wenn ein Nutzer eine Tendenz sehr stark beschreibt, nutze eine deiner adaptiven Fragen in Schritt 6b, um nach *Ausnahmesituationen* zu fragen (z. B.: "Gibt es Momente oder Situationen, in denen Sie sich ganz anders verhalten, als Sie es gerade beschrieben haben? Wie sehen diese aus?"). Das liefert wertvolle diagnostische Tiefe.
- Nutze offene W-Fragen, um Facetten subtil zu explorieren, falls die Antworten zu einsilbig sind.
- Prüfe nach jeder Antwort des Nutzers kritisch: *Könnte ich anhand dieser Aussage die TSDI-Items dieser Facette bereits einschätzen?*
   - Wenn NEIN (und das Max-Fragen-Limit nicht erreicht ist): Nutze Schritt 6b, um gezielt nach konkreten Verhaltensweisen, Motiven oder den oben genannten Ausnahmen zu fragen.
   - Wenn JA (Sättigung erreicht): Höre sofort auf, in dieser Facette weiterzubohren, und leite elegant zur nächsten Facette oder Dimension über (Schritt 7).

WEITERE INTERVIEW-REGELN:
- REINE DIAGNOSTIK – KEINE LÖSUNGEN/STRATEGIEN: Frage NIEMALS nach Lösungen, Hilfsmitteln, Bewältigungsstrategien oder Eisbrechern. Dich interessiert NUR der Ist-Zustand des Verhaltens und wie der Nutzer damit umgeht (nicht, wie er es lösen will).
- SIEZEN: Sprich den Nutzer im gesamten Interview höflich mit 'Sie' an.
- BEENDIGUNG: Sobald du alle Facetten im freien Gespräch diagnostisch ausreichend abgedeckt hast, bedanke dich für das Gespräch, verabschiede dich freundlich und platziere am Ende deiner allerletzten Nachricht exakt das Wort '[INTERVIEW_FERTIG]' (inklusive der eckigen Klammern).

# DIAGNOSTIK-LEITFADEN: Trait Self-Descriptive Inventory (TSDI)
LEITFADEN:
{TSDI_BESCHREIBUNGEN} 


DEINE ANTWORT-STRUKTUR:
Du musst deine Antwort zwingend als ein valides JSON-Objekt formatieren. Das JSON-Objekt muss exakt diese zwei Felder enthalten:
1. "aktuelle_facette": Eine Zahl von 0 bis 17. Gibt an, welche Facette die Testperson mit ihrer LETZTEN Antwort gerade beantwortet hat. Wenn du noch ganz am Anfang (beim Einstieg) bist, ist es 0. Wenn die erste Facette (A-Co) erfolgreich besprochen wurde, wechselst du auf 1, u.s.w.
2. "interviewer_text": Deine Frage oder Antwort an den Nutzer.
"""

INIT_PROMPT_STRUCTURED = """
Vielen Dank fuer Ihre Teilnahme! \n\nIch bin ein AI Agent und werde im weiteren Verlauf ein persoenlichkeitsdiagnostisches Interview mit Ihnen fuehren. Dies wird weitestgehend wie ein gewoehnlicher Fragebogen ablaufen. \n\nLassen Sie uns direkt beginnen. Wie sehr haelt man Sie fuer jemanden, mit dem man einfach gut auskommt?
"""

INIT_PROMPT_OPEN = """
Vielen Dank fuer Ihre Teilnahme! Ich bin ein AI Agent und werde im weiteren Verlauf ein persoenlichkeitsdiagnostisches Interview mit Ihnen fuehren. Lassen Sie uns mit dem ersten Thema beginnen: der Dimension 'Extraversion'. Diese Dimension beschreibt, inwiefern Personen gesellig, gespraechig, freundlich und aktiv sind. Menschen mit hoher Auspraegung fuehlen sich wohl in Gruppen und moegen aufregende Situationen, waehrend Personen mit niedriger Auspraegung eher zurueckhaltend und bedachtsam sind. Wie wuerden Sie sich im Vergleich zu anderen Personen hinsichtlich Ihrer Extraversion einschaetzen?
"""


#--- Condition Configs --------------------------------------------------------------------------------------
CONDITION_CONFIGS = {
    "structured-write": {
        "system_prompt": SYSTEM_PROMPT_STRUCTURED,
        "init_message": json.dumps({
            "aktuelle_facette": 1,
            "interviewer_text": f"{INIT_PROMPT_STRUCTURED}"
        })
    },
    "open-write": {
        "system_prompt": SYSTEM_PROMPT_OPEN,
        "init_message": json.dumps({
            "aktuelle_facette": 1,
            "interviewer_text": f"{INIT_PROMPT_OPEN}"
        })
    },
    "structured-speech": {
        "system_prompt": SYSTEM_PROMPT_STRUCTURED,
        "init_message": json.dumps({
            "aktuelle_facette": 1,
            "interviewer_text": f"{INIT_PROMPT_STRUCTURED}"
        })
    },
    "open-speech": {
        "system_prompt": SYSTEM_PROMPT_OPEN,
        "init_message": json.dumps({
            "aktuelle_facette": 1,
            "interviewer_text": f"{INIT_PROMPT_OPEN}"
        })
    },
}

#--- UI -----------------------------------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Persönlichkeits-Diagnostik", page_icon="🧠")

    client = OpenAI(api_key=st.secrets["openai"]["api_key"])

    if "step" not in st.session_state:
        params = st.query_params
        st.session_state.default_id = params.get("caseNumber", "")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.condition = random.choice(["structured-write", 
                                                    "open-write"])#, 
                                                    #"structured-speech", 
                                                    #"open-speech"])
        st.session_state.current_facet_count = 0
        st.session_state.research_consent = False
        st.session_state.experiment_start_time = time.time()

    # --- 2) ANPASSUNG: NOTFALL-BUTTON SPRINGT ZUM INTERVIEW-ENDE ---
    with st.sidebar:
        st.subheader("⚙️ Administration")
        with st.expander("Notfall-Optionen", expanded=False):
            pwd_input = st.text_input("Admin-Passwort", type="password", key="emergency_pwd")
            if pwd_input == EMERGENCY_PASSWORD:
                st.error("⚠️ Autorisierter Bereich")
                if st.button("⏭️ Interview überspringen & zu UX-Fragen"):
                    # Zeitstempel für das vorzeitige Ende setzen, um NameErrors im Payload zu verhindern
                    st.session_state.interview_end_time = time.time()
                    # Direkt zum ersten UX-Fragebogen springen
                    st.session_state.step = "ux_survey1"
                    st.rerun()
            elif pwd_input:
                st.caption("❌ Falsches Passwort")

    # --- PHASE 1: WILLKOMMEN ---
    if st.session_state.step == "welcome":
        st.title("Willkommen zum Interview 🤖")
        st.write("Bitte geben Sie Ihre Daten ein, um mit dem Interview zu beginnen.")
        
        st.markdown("""
        **Anleitung zur Generierung Ihres VP-Codes:**
        * Geben Sie als erstes die Anzahl der Buchstaben des (ersten) Vornamens Ihrer Mutter ein (z.B. 04)
        * Geben Sie als zweites die letzten beiden Buchstaben des Mädchen-(Geburts-)namens der Mutter ein (z.B. ER)
        * Geben Sie als drittes die letzten beiden Buchstaben des (ersten Vornamens) des Vaters ein (z.B. NS)
        * Geben Sie als viertes den Tag Ihrem Geburtstags ein (z.B. 24)

        Ein Versuchspersonencode könnte beispielsweise so aussehen: 04ERNS24
        """)
        
        vp_code_input = st.text_input("VP-Code (Teilnehmer-Code)", value=st.session_state.default_id, placeholder="z.B. 04ERNS24")
        matrikel_input = st.text_input("Matrikelnummer", placeholder="z.B. 1234567")
        
        if st.button("Weiter zur Beschreibung der Übung"):
            if not vp_code_input.strip() or not matrikel_input.strip():
                st.error("Bitte füllen Sie beide Felder aus.")
            else:
                st.session_state.participant_id = vp_code_input.strip()
                st.session_state.matrikelnummer = matrikel_input.strip()
                st.session_state.step = "consent"
                st.rerun()

    # --- PHASE 2: EINWILLIGUNG ---
    elif st.session_state.step == "consent":
        st.title("Informationen zum Ablauf & Datenschutz 📝")
        st.markdown("""
        ### Beschreibung & Zweck 

        Dieses KI-gestützte Interview dient der Persönlichkeitsdiagnostik. Am Ende erhalten Sie eine Auswertung Ihrer Big Five.
        Bitte führen Sie das Interview in einer durchgängigen Sitzung durch und unterbrechen Sie das Interview nicht. Die Bearbeitung wird ca. 45 Minuten dauern. 
        
        * **Lesitungsnachweis:** Die Teilnahme am Interview ist Teil der Übungsleistung. Wer nicht teilnimmt, erhält keinen Credit.
        * **Ehrlichkeit:** Es gibt keine Pflicht zu wahrheitsgemäßen Angaben, aber fiktive Angaben verfälschen die Auswertung und schränken die Selbsterfahrung ein.       

        ### Datenschutz

        * **OpenAI API:** Die Interview Daten werden verschlüsselt an openAI übertragen, aber NICHT zum Training genutzt und nach 30 Tagen gelöscht.
        * **Speicherung:** Die Interview Daten werden in einer Nextcloud der Universität Ulm gespeichert.
        * **Ethikvotum:** Die Verwendung des KI-Chatbots via openAI API wurde von der Ethikkommission bewilligt unter **[EG-IIP-2026049]**.
        
        """)
        
        consent_checked = st.checkbox("Ich habe die oben genannten Informationen gelesen und stimme der Nutzung und Speicherung meiner Chatdaten zu Forschungs- und Lehrzwecken zu.")
        
        if st.session_state.condition in ["structured-write", "open-write"]:
            button_name = "Interview starten"
        else:
            button_name = "Weiter zum Mikrofon-Test"
        
        if st.button(button_name):
            if consent_checked:
                st.session_state.research_consent = True
                if button_name == "Interview starten":
                    st.session_state.step = "chat_write"
                    st.session_state.interview_start_time = time.time()
                else:
                    st.session_state.step = "mic_test"
                
                config = CONDITION_CONFIGS[st.session_state.condition]
                                
                st.session_state.messages = [
                    {"role": "system", "content": config["system_prompt"]},
                    {"role": "assistant", "content": config["init_message"]}
                ]
                st.rerun()
            else:
                st.warning("Bitte stimmen Sie zu.")

    # --- PHASE 2.5: MIKROFON TEST ---
    elif st.session_state.step == "mic_test":
        st.title("🎙️ Mikrofon-Test & Vorbereitung")
        st.write("Bitte testen Sie Ihr Mikrofon, bevor das Interview startet. Sprechen Sie nach dem Starten der Aufnahme ein paar Worte (z. B. 'Hallo, Test').")
        
        # --- WICHTIGER GEWÄHLTER HINWEIS FÜR DIE NUTZER ---
        st.info("⚠️ **Wichtiger Hinweis zur Geräteauswahl:** Der Chatbot nutzt automatisch das Standard-Mikrofon Ihres Computers. Falls das falsche Mikrofon (z.B. die interne Webcam statt Ihres Headsets) aktiv ist, folgen Sie bitte kurz dieser Anleitung:")
        
        with st.expander("📋 Anleitung: So legen Sie Ihr Wunsch-Mikrofon fest"):
            st.markdown("""
            ### 🪟 Unter Windows:
            1. Drücken Sie die **Windows-Taste** auf Ihrer Tastatur und tippen Sie **'Soundeinstellungen'** ein (dann Enter drücken).
            2. Scrollen Sie nach unten zum Bereich **'Eingabe'**.
            3. Wählen Sie dort Ihr Wunsch-Mikrofon aus.
            4. Klicken Sie (falls sichtbar) auf **'Als Standardgerät festlegen'**.
           
            ### 🍏 Unter macOS:
            1. Öffnen Sie die **Systemeinstellungen** --> **Ton**.
            2. Wechseln Sie auf den Reiter **'Eingabe'**.
            3. Klicken Sie Ihr Wunsch-Mikrofon an, sodass es blau hinterlegt ist. Es ist nun das systemweite Standardgerät.
          
            *Laden Sie die Seite nach der Änderung ggf. einmal neu, falls Ihr Mikrofon weiterhin nicht erkannt wird.*
            """)
        
        st.write("---")
        audio_record = mic_recorder(
                start_prompt="Aufnahme starten",
                stop_prompt="Aufnahme stoppen",
                key="speech_recorder"
            )
           
        if audio_record:
            audio_bytes = audio_record['bytes']
            audio_hash = hashlib.md5(audio_bytes).hexdigest()
            if audio_hash != st.session_state.get("last_audio_hash"):
                st.session_state.last_audio_hash = audio_hash
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "audio.wav"
         
            with st.spinner("Prüfe Audio-Eingang..."):
                try:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                    if transcript.text.strip():
                        st.session_state.mic_test_transcript = transcript.text
                        st.session_state.mic_test_passed = True

                    else:
                        st.session_state.mic_test_transcript = "Es wurde kein Text erkannt. Bitte lauter sprechen oder das richtige Eingabegerät in den Browsereinstellungen wählen."
                        st.session_state.mic_test_passed = False
                except Exception as e:
                    st.error(f"Fehler beim Mikrofon-Test: {e}")
       
        # Visuelle Rückmeldung für die Person
        if "mic_test_transcript" in st.session_state:
            st.info(f"**Erkanntes Audio:** „{st.session_state.mic_test_transcript}“")
         
            if st.session_state.mic_test_passed:
                st.success("✅ Mikrofon funktioniert erfolgreich! Sie können das Interview jetzt starten.")
                if st.button("Interview starten"):
                    st.session_state.step = "chat_speech"
                    st.session_state.interview_start_time = time.time()
                    st.rerun()
            else:
                st.error("❌ Audio-Signal zu schwach oder fehlerhaft. Bitte versuchen Sie es erneut.") 

    # --- PHASE 3A: CHAT WRITE ---
    elif st.session_state.step == "chat_write":
        st.title("Interview im Dialog 💬")
        is_structured = st.session_state.condition.startswith("structured")

        if is_structured:
            if st.session_state.messages:
                last_ai_msg = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"][-1]
                try:
                    msg_data = json.loads(last_ai_msg)
                    st.session_state.current_facet_count = min(max(0, int(msg_data.get("aktuelle_facette", 0))), TOTAL_FACETS)
                except:
                    pass
            progress_percentage = float(st.session_state.current_facet_count) / float(TOTAL_FACETS)
            st.markdown(f"Facette {st.session_state.current_facet_count} von {TOTAL_FACETS}")
            st.progress(progress_percentage)
        else:
            st.session_state.interaction_count = len([m for m in st.session_state.messages if m["role"] == "user"])
            interaction_count_capped = min(st.session_state.interaction_count, MAX_INTERACTIONS)
            progress_percentage = float(interaction_count_capped) / float(MAX_INTERACTIONS)
            st.markdown(f"Interaktion {st.session_state.interaction_count} von {MAX_INTERACTIONS}")
            st.progress(progress_percentage)

        st.divider()

        # Inject CSS for scrollable chat container
        st.markdown("""
        <style>
        .chat-container { height: 35vh; overflow-y: auto; display: flex; flex-direction: column-reverse; padding: 1rem; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #fafafa; margin-bottom: 1rem; }
        .chat-bubble-user { align-self: flex-end; background-color: #DCF8C6; color: #000; padding: 0.6rem 1rem; border-radius: 16px 16px 2px 16px; max-width: 75%; margin: 0.3rem 0; font-size: 0.95rem; }
        .chat-bubble-ai { align-self: flex-start; background-color: #FFFFFF; color: #000; padding: 0.6rem 1rem; border-radius: 16px 16px 16px 2px; max-width: 75%; margin: 0.3rem 0; font-size: 0.95rem; border: 1px solid #e0e0e0; }
        </style>
        """, unsafe_allow_html=True)

        chat_html = '<meta charset="UTF-8"><div class="chat-container" id="chat-box">'
        interview_ended = False

        for msg in reversed(list(st.session_state.messages)):
            if msg["role"] == "system": continue
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

        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

        if interview_ended:
            if "interview_end_time" not in st.session_state:
                st.session_state.interview_end_time = time.time()
            st.success("Das Interview wurde erfolgreich beendet.")
            if st.button("Nächste Seite"):
                st.session_state.step = "ux_survey1"
                st.rerun()
        else:
            user_input = st.chat_input("Ihre Antwort hier tippen...")

            if user_input:
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H:%M:%S")
                })
                api_success = False
                
                with st.spinner("🤖 Interviewer überlegt..."):
                    try:
                        api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=api_messages,
                            response_format={"type": "json_object"}
                        )
                        ai_msg = response.choices[0].message.content
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": ai_msg,
                            "timestamp": datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d_%H:%M:%S")
                        })
                        api_success = True
                    except Exception as e:
                        st.error(f"KI Fehler: {e}")
                
                if api_success:
                    full_data = {
                        "participant_id": st.session_state.get("participant_id", "unknown"),
                        "matrikelnummer": st.session_state.matrikelnummer,
                        "condition": st.session_state.condition,
                        "research_consent": st.session_state.research_consent,
                        "chat": st.session_state.messages,
                        "timing": {
                            "experiment_start_time": datetime.fromtimestamp(st.session_state.experiment_start_time).strftime("%Y-%m-%d_%H:%M:%S"),
                            "interview_start_time": datetime.fromtimestamp(st.session_state.interview_start_time).strftime("%Y-%m-%d_%H:%M:%S")
                        }
                    }
                    # 1) ANPASSUNG: args enthält nun st.session_state.matrikelnummer
                    threading.Thread(target=save_to_nextcloud, args=(st.session_state.participant_id, st.session_state.matrikelnummer, full_data, False), daemon=True).start()
                st.rerun()

    # --- PHASE 3B: CHAT SPEECH ---
    elif st.session_state.step == "chat_speech":
        st.title("Interview im Dialog 💬")
        user_msgs = [m for m in st.session_state.messages if m["role"] == "user"]
        st.session_state.interaction_count = len(user_msgs)
        is_structured = st.session_state.condition.startswith("structured")

        if is_structured:
            current_facet_count = 0
            if st.session_state.messages:
                last_ai_msg = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"][-1]
                try:
                    msg_data = json.loads(last_ai_msg)
                    current_facet_count = min(max(0, int(msg_data.get("aktuelle_facette", 0))), TOTAL_FACETS)
                except:
                    pass
            progress_percentage = float(current_facet_count) / float(TOTAL_FACETS)
            st.markdown(f"Facette {current_facet_count} von {TOTAL_FACETS}")
            st.progress(progress_percentage)
        else:
            interaction_count_capped = min(st.session_state.interaction_count, MAX_INTERACTIONS)
            progress_percentage = float(interaction_count_capped) / float(MAX_INTERACTIONS)
            st.markdown(f"Interaktion {st.session_state.interaction_count} von {MAX_INTERACTIONS}")
            st.progress(progress_percentage)

        st.divider()
        interview_ended = False

        for msg in st.session_state.messages:
            if msg["role"] != "system":
                if msg["role"] == "assistant":
                    try:
                        data = json.loads(msg["content"])
                        display_text = data.get("interviewer_text", msg["content"])
                        if "[INTERVIEW_FERTIG]" in display_text:
                            interview_ended = True
                        display_text = display_text.replace("[INTERVIEW_FERTIG]", "").strip()
                    except:
                        display_text = msg["content"]
                else:
                    display_text = msg["content"]
                with st.chat_message(msg["role"]):
                    st.markdown(display_text)

        if interview_ended:
            if "interview_end_time" not in st.session_state:
                st.session_state.interview_end_time = time.time()
            st.success("Das Interview wurde erfolgreich beendet.")
            if st.button("Nächste Seite"):
                st.session_state.step = "ux_survey1"
                st.rerun()
        else:
            user_input = None
            st.write("---")
            st.write("🎤 **Antwort einsprechen:**")
            
            audio_record = mic_recorder(
                start_prompt="Aufnahme starten",
                stop_prompt="Aufnahme stoppen",
                key="interview_speech_recorder"
            )
            
            if audio_record:
                audio_bytes = audio_record['bytes']
                audio_hash = hashlib.md5(audio_bytes).hexdigest()

                if audio_hash != st.session_state.get("last_processed_audio_hash"):
                    st.session_state.last_processed_audio_hash = audio_hash
                    audio_file = io.BytesIO(audio_bytes)
                    audio_file.name = "audio.wav"
                    
                    with st.spinner("🎧 Ich höre zu..."):
                        try:
                            transcript = client.audio.transcriptions.create(
                                model="whisper-1", 
                                file=audio_file
                            )
                            user_input = transcript.text
                        except Exception as e:
                            st.error(f"Spracherkennungs-Fehler: {e}")

            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                with st.spinner("🤖 Interviewer überlegt..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=st.session_state.messages,
                            response_format={"type": "json_object"}
                        )
                        ai_msg = response.choices[0].message.content
                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                    except Exception as e:
                        st.error(f"KI Fehler: {e}")
                
                full_data = {
                    "participant_id": st.session_state.participant_id,
                    "matrikelnummer": st.session_state.matrikelnummer,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
                    "chat": st.session_state.messages
                }
                
                # 1) ANPASSUNG: args enthält nun st.session_state.matrikelnummer
                threading.Thread(
                    target=save_to_nextcloud, 
                    args=(st.session_state.participant_id, st.session_state.matrikelnummer, full_data, False),
                    daemon=True
                ).start()
                st.rerun()

    # --- PHASE 4: UX Fragebogen Interview ---
    elif st.session_state.step == "ux_survey1":
        st.title("Wie war das Interview? 📋")
        st.divider()

        with st.form("ux_form"):
            q1 = st.slider("Ich wusste manchmal nicht, wie ich auf eine Frage antworten sollte.", 1, 5, 3)
            q2 = st.slider("Ich emfpand die Interaktion mit dem KI-Chatbot ermüdend.", 1, 5, 3)
            q3 = st.slider("Insgesamt erlaubt die Befragung durch das LLM ein recht angemessenes Bild meiner Persönlichkeit zu zeichnen.", 1, 5, 3)
            q4 = st.slider("Ich empfand die Interaktion mit dem KI-Chatbot als frustrierend. ", 1, 5, 3)
            q5 = st.slider("Es fiel mir leicht, mich auf das Gespräch zu konzentrieren.", 1, 5, 3)
            q6 = st.slider("Ich emfpand die Interaktion mit dem KI-Chatbot als angenehm. ", 1, 5, 3)
            q7 = st.slider("Ich denke die Interaktion mit dem KI-Chatbot hätte effizienter sein können.", 1, 5, 3) # gefixt: q7 statt q8 im slider key
            q9 = st.slider("Ich empfand die Interaktion mit dem KI-Chatbot als sicher.", 1, 5, 3)
            q10 = st.slider("Ich empfand die Interaktion mit dem KI-Chatbot als interessant.", 1, 5, 3)
            q11 = st.slider("Ich fand die Fragen des KI-Chatbot nicht sonderlich gut gewählt.", 1,5,3)
            q12 = st.slider("Ich hätte gegenüber einer menschlichen Interviewerin sozial erwünschter reagiert.", 1,5,3)
                    
            submitted = st.form_submit_button("Weiter zur Auswertung")
            if submitted:
                st.session_state.ux_responses_interview = {
                    "q1_verstaendlichkeit": q1, "q2_ermüdung": q2, "q3_adequaet": q3, "q4_frust": q4,
                    "q5_konzentr": q5, "q6_angenehm": q6, "q8_ineffizient": q7, "q9_sicher": q9, 
                    "q10_interessant": q10, "q11_auswahl": q11, "q12_socdes": q12
                }
                st.session_state.step = "results"
                st.rerun()

    # --- PHASE 5: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")

        if "ai_bfi" not in st.session_state:
            with st.spinner("KI Analyse läuft..."):
                try:
                    clean_messages = []
                    for m in st.session_state.messages:
                        if m["role"] == "system": 
                            continue
                        if m["role"] == "assistant":
                            # Einheitliches Parsen für Write und Speech
                            try:
                                content_data = json.loads(m['content'])
                                interviewer_text = content_data.get('interviewer_text', '')
                                clean_messages.append(f"Interviewer: {interviewer_text}")
                            except:
                                # Falls es mal kein JSON-String war
                                clean_messages.append(f"Interviewer: {m['content']}")
                        else:
                            clean_messages.append(f"Teilnehmer: {m['content']}")
                            
                    chat_text = "\n".join(clean_messages)
                    
                    # Hier erzwingen wir das Wort JSON im System-Prompt für BEIDE Bedingungen
                    analysis_system_prompt = (
                    "Du bist ein erfahrener Persönlichkeitspsychologe. "
                    "Analysiere den übermittelten Chatverlauf auf Facettenebene der Big Five. "
                    "Du MUSST deine Antwort als valides JSON-Objekt formatieren. "
                    "Nutze ALS SCHLÜSSEL EXAKT NUR diese Namen (ohne Kürzel oder Klammern):\n"
                    "Freundlichkeit, Rücksichtnahme, Hilfsbereitschaft, Fleiß, Organisation, "
                    "Durchsetzungsfähigkeit, Selbstbewusstsein, Soziale Aktivität, Depression, "
                    "Reizbarkeit, Nervosität, Intellekt, Reflexion, Wissenschaftliches Interesse, "
                    "Aufrichtigkeit, Fairness, Bescheidenheit.\n"
                    "Die Werte müssen Zahlen von 1 bis 5 sein.\n"
                    f"{TSDI_BESCHREIBUNGEN}"
                    )
                    
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": analysis_system_prompt},
                            {"role": "user", "content": f"Hier ist der Chatverlauf:\n{chat_text}"}
                        ],
                        response_format={"type": "json_object"}
                    )
                    st.session_state.ai_bfi = json.loads(res.choices[0].message.content)
                except Exception as e:
                    st.error(f"Fehler bei der Analyse: {e}")
                    st.session_state.ai_bfi = {t: 0 for t in ["Freundlichkeit", "Rücksichtnahme", "Hilfsbereitschaft", "Fleiß", "Organisation", "Durchsetzungsfähigkeit", "Selbstbewusstsein", "Soziale Aktivität", "Depression", "Reizbarkeit", "Nervosität", "Intellekt", "Reflexion", "Wissenschaftliches Interesse", "Aufrichtigkeit", "Fairness", "Bescheidenheit"]}
        
        DIMENSION_FACETS = {
            "Ehrlichkeit-Bescheidenheit": ["Aufrichtigkeit", "Fairness", "Bescheidenheit"],
            "Neurotizismus": ["Depression", "Reizbarkeit", "Nervosität"],
            "Extraversion": ["Durchsetzungsfähigkeit", "Selbstbewusstsein", "Soziale Aktivität"],
            "Verträglichkeit": ["Freundlichkeit", "Rücksichtnahme", "Hilfsbereitschaft"],
            "Gewissenhaftigkeit": ["Fleiß", "Organisation"],
            "Offenheit": ["Intellekt", "Reflexion", "Wissenschaftliches Interesse"],
        }

        for dimension, facets in DIMENSION_FACETS.items():
            st.subheader(dimension)
            for t in facets:
                ki_wert = st.session_state.ai_bfi.get(t, 0)
                st.metric(f"{t}", f"{ki_wert} / 5")
                st.progress(float(ki_wert) / 5.0 if ki_wert else 0.0)
            st.divider()

        if st.button("Weiter um Übungsblock zu beenden"):
            st.session_state.step = "ux_survey2"
            st.rerun()

# --- PHASE 6: UX Fragebogen Auswertung ---
    elif st.session_state.step == "ux_survey2":
        st.title("Wie war die Auswertung? 📋")
        st.divider()

        with st.form("ux_form_results"):
            q13 = st.slider("Ich habe insgesamt wahrheitsgemäß gegenüber dem KI-Chatbot geantwortet. ", 1, 5, 3)
            q14 = st.slider("Die Einschätzung der KI passt weitestgehend mit meiner eigenen Wahrnehmung zusammen.", 1, 5, 3)
            
            # --- NEU: Offenes Kommentarfeld innerhalb des Formulars ---
            kommentar_ki = st.text_area(
                "Haben Sie Kommentare zu dem KI-Interview?",
                placeholder="Ihr Feedback, Anmerkungen oder Kritik...",
                max_chars=1000
            )
        
            submitted = st.form_submit_button("Übungsblock abschließen!")
            if submitted:
                # Hier fügen wir den Kommentar der Datenstruktur hinzu
                st.session_state.ux_responses_results = {
                    "q13_wahrheit": q13,
                    "q14_passung": q14,
                    "kommentar_ki_interview": kommentar_ki  # <-- Wird mit abgespeichert
                }

                experiment_end_time = time.time()
                final_payload = {
                    "participant_id": st.session_state.participant_id,
                    "matrikelnummer": st.session_state.matrikelnummer,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
                    "ux_responses_interview": st.session_state.get("ux_responses_interview", {}),
                    "ux_responses_results": st.session_state.ux_responses_results, # Enthält nun auch das Kommentarfeld
                    "ai_assessment": st.session_state.ai_bfi,
                    "chat": st.session_state.messages,
                    "timing": {
                        "experiment_start_time": datetime.fromtimestamp(st.session_state.experiment_start_time).strftime("%Y-%m-%d_%H:%M:%S"),
                        "experiment_end_time": datetime.fromtimestamp(experiment_end_time).strftime("%Y-%m-%d_%H:%M:%S"),
                        "interview_start_time": datetime.fromtimestamp(st.session_state.interview_start_time).strftime("%Y-%m-%d_%H:%M:%S"),
                        "interview_end_time": datetime.fromtimestamp(st.session_state.interview_end_time).strftime("%Y-%m-%d_%H:%M:%S"),
                        "duration_interview_seconds": round(st.session_state.interview_end_time - st.session_state.interview_start_time, 2),
                        "duration_experiment_seconds": round(experiment_end_time - st.session_state.experiment_start_time, 2)
                    }
                }
                # 1) ANPASSUNG: Hier wird st.session_state.matrikelnummer übergeben
                if save_to_nextcloud(st.session_state.participant_id, st.session_state.matrikelnummer, final_payload, True):
                    st.session_state.data_saved = True
                    st.session_state.step = "farewell"
                    st.rerun()
                else:
                    st.error("Speicherfehler. Bitte versuchen Sie es erneut.")
    
    # --- PHASE 7: ABSCHLUSS ---
    elif st.session_state.step == "farewell":
        st.title("Vielen Dank! 🎉")
        st.success("Ihre Daten wurden erfolgreich gespeichert.")
        st.divider()
        st.link_button("Zur Uni-Webseite", "https://www.uni-ulm.de/in/psy-dia/forschung/an-studien-teilnehmen/")

if __name__ == "__main__":
    main()
