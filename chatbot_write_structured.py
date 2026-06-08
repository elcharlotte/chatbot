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

# --- UI KOMPONENTEN ---
def main():
    st.set_page_config(page_title="Persönlichkeits-Diagnostik", page_icon="🧠")
    
    if "step" not in st.session_state:
        params = st.query_params
        # Fallback-ID generieren, falls nichts in der URL oder Eingabe steht
        st.session_state.default_id = params.get("caseNumber", f"user_{uuid.uuid4().hex[:8]}")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.interaction_count = 0
        # NEU: Versuchsbedingung fest im Session State hinterlegen
        st.session_state.condition = "write_structured"

    # --- PHASE 1: WILLKOMMEN & ID-EINGABE ---
    if st.session_state.step == "welcome":
        st.title("Willkommen zum Interview 🤖")
        st.write("Bitte geben Sie zunächst Ihre Teilnehmer-ID ein.")
        
        participant_id_input = st.text_input(
            "Teilnehmer-ID (Participant ID)", 
            value=st.session_state.default_id,
            help="Bitte geben Sie die Ihnen zugewiesene ID ein."
        )
        
        if st.button("Weiter zur Studienbeschreibung"):
            if not participant_id_input.strip():
                st.error("Bitte geben Sie eine gültige ID ein.")
            else:
                st.session_state.participant_id = participant_id_input.strip()
                st.session_state.step = "consent"
                st.rerun()

    # --- PHASE 2: STUDIENBESCHREIBUNG & EINWILLIGUNG ---
    elif st.session_state.step == "consent":
        st.title("Informationen zur Studie & Datenschutz 📝")
        
        st.markdown("""
        ### Beschreibung der Studie
        In diesem KI-gestützten Interview untersuchen wir sprachliche Muster im Kontext der Persönlichkeitsdiagnostik. 
        Das Gespräch wird von einem KI-Interviewer geführt und umfasst genau 10 Interaktionen.
        
        ### Umgang mit Ihren Daten
        * **Wo werden die Daten gespeichert?** Ihre Daten (Chatverlauf und Auswertung) werden verschlüsselt auf den sicheren Servern der Universität Ulm (**Nextcloud/Cloudstore**) abgelegt.
        * **Wo werden sie NICHT gespeichert?** Es werden keine personenbezogenen Daten auf externen kommerziellen Servern dauerhaft gespeichert. Die Chat-Inhalte werden via API an OpenAI verarbeitet, aber dort laut deren Datenschutzrichtlinien für Forschungs-APIs *nicht* zum Training genutzt und nach maximal 30 Tagen gelöscht.
        * **Anonymisierung**: Die Speicherung erfolgt ausschließlich unter der von Ihnen angegebenen Teilnehmer-ID. Es werden keine Klarnamen oder IP-Adressen mit den Forschungsdaten verknüpft.
        """)
        
        st.divider()
        
        consent_checked = st.checkbox(
            "Ich habe die Informationen gelesen und stimme der anonymisierten Nutzung und Speicherung meiner Chatdaten zu Forschungszwecken zu."
        )
        
        if st.button("Interview starten"):
            if consent_checked:
                st.session_state.research_consent = True
                st.session_state.step = "chat"
                st.session_state.messages = [
                    {"role": "system", "content": "Role: Du bist ein psychologischer Interviewer in einer wissenschaftlichen Persönlichkeitsstudie. Dein Ziel ist es, ein offenes, exploratives Interview zu führen, um die Ausprägungen des Nutzers in den Facetten des unten stehenden "Trait Self-Descriptive Inventory (TSDI)" zu erfassen.

TASK OVERVIEW:
Erforsche alle 5 Dimensionen und deren Facetten im Gesprächsverlauf. Du musst am Ende des Interviews jede Facette durch mindestens 3 offene, vertiefende Nachfragen (Follow-up-Fragen) exploriert haben. Das Interview soll sich für den Nutzer wie ein freies, ungezwungenes Gespräch anfühlen, nicht wie ein Test.

INTERVIEW GUIDELINES & CONSTRAINTS:
1. Einstieg: Beginne das Interview mit einer sehr offenen Einladung (z. B. "Erzähl mir ein bisschen von dir, was machst du gerne und wie würdest du dich selbst als Person beschreiben?").
2. Offene Gesprächsführung: Überlasse dem Nutzer die Initiative. Verwende aktives Zuhören. Greife Aspekte auf, die der Nutzer von sich aus einbringt, und vertiefe diese.
3. Absolutes Verbot von Testfragen: Du darfst die psychometrischen Items NIEMALS wörtlich vorlesen oder direkt als standardisierte Frage stellen (z. B. Nicht fragen: "Hält man dich für schüchtern?").
4. Indirekte Exploration (Nudging): Nutze stattdessen offene W-Fragen, um Facetten zu explorieren (z. B. statt das Schüchternheits-Item abzufragen, frage: "Wie fühlst du dich normalerweise, wenn du in einer großen Gruppe im Mittelpunkt stehst?").
5. Vertiefung (Follow-up): Wenn der Nutzer ein Thema anschneidet, das zu einer Facette passt, nutze mindestens 3 vertiefende Nachfragen ("Kannst du das genauer beschreiben?", "Wie wirkt sich das in deinem Alltag aus?", "Was bedeutet das für dich?"), um den Redefluss zu fördern und tiefere Einblicke zu gewinnen.
6. Agenda-Kontrolle: Halte im Hintergrund fest, welche Facetten du bereits exploriert hast. Wenn ein Thema erschöpft ist, leite elegant und sanft zu einem neuen, offenen Lebensbereich über (z. B. Freizeit, Beruf/Studium, soziale Kontakte), um bisher unberührte Facetten anzustoßen.

---
# DIAGNOSTIK-LEITFADEN: Trait Self-Descriptive Inventory

## DIMENSION: VERTRÄGLICHKEIT (A)
Beschreibung: Misst die zwischenmenschliche Orientierung. Hohe Werte stehen für Altruismus, Vertrauen und Harmoniebedürfnis; niedrige Werte für Egoismus, Skepsis und Kompetitivität.
### Facette: Kooperation / Vertrauen (A-Co)
Beschreibung: Bereitschaft zur Zusammenarbeit, Vertrauen in das Gute im Menschen und Vermeidung von Konfrontationen.
* Item tsdi42_02_A_Co080: Ich behandle andere Leute immer freundlich.
* Item tsdi42_21_A_Co207: Ich versuche zu jedem freundlich zu sein, den ich kenne.
* Item tsdi42_22_A_Co209: Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.
### Facette: Freundlichkeit / Mitgefühl (A-Fr)
Beschreibung: Herzlicher Umgang mit Mitmenschen, Empathie und emotionale Unterstützung.
* Item tsdi42_24_A_Fr066: Man hält mich für jemanden mit dem man einfach gut auskommt.
* Item tsdi42_12_A_Fr084: Ich komme mit den meisten Menschen gut zurecht.
* Item tsdi42_36_A_Fr220: Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.
### Facette: Hilfsbereitschaft (A-H)
Beschreibung: Aktive Unterstützung anderer, Großzügigkeit und die Neigung, für andere da zu sein.
* Item tsdi42_10_A_H064: Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.
* Item tsdi42_40_A_H068: Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.
* Item tsdi42_39_A_H213: Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.

## DIMENSION: GEWISSENHAFTIGKEIT (C)
Beschreibung: Grad an Selbstkontrolle, Genauigkeit, Zielstrebigkeit und Organisation. Hohe Werte stehen für Disziplin und Verlässlichkeit; niedrige Werte für Spontaneität und Nachlässigkeit.
### Facette: Pflichtbewusstsein / Fleiß (C-Hw)
Beschreibung: Arbeitsmoral, Ausdauer bei schwierigen Aufgaben und das Einhalten von Verpflichtungen.
* Item tsdi42_04_C_Hw126: Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.
* Item tsdi42_25_C_Hw137: Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.
* Item tsdi42_37_C_Hw167: Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.
### Facette: Ordnung / Besonnenheit (C-O)
Beschreibung: Struktur im Alltag, Vorliebe für Planung und das Vermeiden unüberlegter Handlungen.
* Item tsdi42_14_C_O0153: Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.
* Item tsdi42_41_C_O0157: Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.
* Item tsdi42_32_C_O0162: Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.

## DIMENSION: EXTRAVERSION (E)
Beschreibung: Aktivität und zwischenmenschliches Verhalten. Hohe Werte stehen für Geselligkeit, Durchsetzungsvermögen und Optimismus; niedrige Werte für Introversion, Zurückhaltung und Ruhe.
### Facette: Aktivität / Durchsetzungsvermögen (E-A)
Beschreibung: Tendenz, die Initiative zu ergreifen, Energiegeladenheit und das Einnehmen einer Führungsposition.
* Item tsdi42_35_E_A002: Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.
* Item tsdi42_28_E_A004: Ich neige dazu, in Gruppen die Führung zu übernehmen.
* Item tsdi42_03_E_A009: Ich habe eine Menge Einfluss auf andere Leute.
### Facette: Schüchternheit (E-SB)
Beschreibung: Suche nach Anregung, Begeisterungsfähigkeit und eine vitale Lebensenergie.
* Item tsdi42_19_E_SB010: Ich bin eine sehr schüchterne Person.
* Item tsdi42_08_E_SB014: Meine Freunde halten mich für schüchtern.
* Item tsdi42_18_E_SB026: Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.
### Facette: Geselligkeit / Herzlichkeit (E-So)
Beschreibung: Freude am Zusammensein mit anderen Menschen, Knüpfen von Kontakten und Feierfreudigkeit.
* Item tsdi42_33_E_So007: Ich bin gerne wo viel los ist.
* Item tsdi42_26_E_So012: Ich gebe mir große Mühe Leute kennen zu lernen.
* Item tsdi42_16_E_So028: Ich mag Partys auf denen viele Leute sind.

## DIMENSION: NEUROTIZISMUS (N)
Beschreibung: Emotionale Labilität vs. Stabilität. Tendenz, negative Emotionen wie Angst, Trauer oder Ärger intensiver zu erleben und empfindlich auf Stress zu reagieren.
### Facette: Depressivität / Dysthymie (N-D)
Beschreibung: Neigung zu gedrückter Stimmung, Selbstzweifeln, Einsamkeitsgefühlen und Pessimismus.
* Item tsdi42_07_N_D039: Es gibt Zeiten in denen ich mich selbst bedaure.
* Item tsdi42_15_N_D054: Manchmal bin ich entmutigt und möchte am liebsten aufgeben.
* Item tsdi42_30_N_D055: Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.
### Facette: Reizbarkeit / Irritierbarkeit (N-Ir)
Beschreibung: Neigung zu Frustration, Empfindlichkeit gegenüber Kritik und schnelles Genervtsein.
* Item tsdi42_09_N_Ir034: Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.
* Item tsdi42_05_N_Ir058: Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.
* Item tsdi42_06_N_Ir070: Ich kann Kritik nicht sehr gut akzeptieren.
### Facette: Stressanfälligkeit / Ängstlichkeit (N-St)
Beschreibung: Nervosität in Stresssituationen, Sorgen bezüglich der Zukunft und körperliche Stresssymptome.
* Item tsdi42_29_N_St037: Ich fühle mich oft müde und erschöpft.
* Item tsdi42_38_N_St040: Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.
* Item tsdi42_11_N_St043: Ich bin oft zittrig und angespannt.

## DIMENSION: OFFENHEIT FÜR ERFAHRUNGEN (O)
Beschreibung: Intellektuelle Neugier, Vorliebe für Abwechslung, ausgeprägte Phantasie und Wertschätzung von Kunst und Kultur.
### Facette: Intellekt / Ideen (O-In)
Beschreibung: Freude am Nachdenken, Interesse an abstrakten oder philosophischen Fragestellungen und neuen Denkansätzen.
* Item tsdi42_31_O_In094: Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.
* Item tsdi42_23_O_In106: Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.
* Item tsdi42_27_O_In118: Ich besitze ein hohes Maß an intellektueller Neugier.
### Facette: Reflexion / Phantasie (O-R)
Beschreibung: Reiches Innenleben, Tagträumerei und tiefe Beschäftigung mit eigenen Gedanken und Büchern.
* Item tsdi42_17_O_R100: Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.
* Item tsdi42_42_O_R117: Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.
* Item tsdi42_34_O_R120: Ich lese gerne Gedichte.
### Facette: wissenschaftliches Interesse (O-Sc)
Beschreibung: Interesse an Naturphänomenen, wissenschaftlichen Konzepten und grundlegenden Fragen der Existenz.
* Item tsdi42_13_O_Sc103: Ich denke oft über die Wunder der Natur nach.
* Item tsdi42_20_O_Sc114: Die Evolutionstheorie fasziniert mich.
* Item tsdi42_01_O_Sc116: Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.
"},
                    {"role": "assistant", "content": f"Vielen Dank! Die ID {st.session_state.participant_id} ist registriert. Wir beginnen nun mit dem Interview. Erzählen Sie doch mal: Was haben Sie gestern so gemacht?"}
                ]
                st.rerun()
            else:
                st.warning("Bitte bestätigen Sie die Einwilligungserklärung, um fortzufahren.")

    # --- PHASE 3: CHAT (NUR TEXT) ---
    elif st.session_state.step == "chat":
        st.title("Interview im Dialog 💬")
        user_msgs = [m for m in st.session_state.messages if m["role"] == "user"]
        st.session_state.interaction_count = len(user_msgs)
        st.info(f"Interaktion {st.session_state.interaction_count} von 10")
        
        # Chatverlauf anzeigen
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        if st.session_state.interaction_count >= 10:
            st.warning("Interview beendet.")
            if st.button("Zur Auswertung"):
                st.session_state.step = "results"
                st.rerun()
        else:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            
            # Reiner Text-Input via standard chat_input
            user_input = st.chat_input("Ihre Antwort hier tippen...")

            if user_input:
                # 1. Sofort im UI anzeigen
                st.session_state.messages.append({"role": "user", "content": user_input})
                
                # 2. KI-Antwort generieren
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
                
                # 3. Nextcloud-Zwischenspeicherung im Hintergrund
                # ANPASSUNG: "condition" hier für die Rohdaten-Updates hinzugefügt
                full_data = {
                    "participant_id": st.session_state.participant_id,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
                    "chat": st.session_state.messages
                }
                
                threading.Thread(
                    target=save_to_nextcloud, 
                    args=(st.session_state.participant_id, full_data),
                    daemon=True
                ).start()
                
                st.rerun()

    # --- PHASE 4: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")
        
        if "data_saved" not in st.session_state:
            st.session_state.data_saved = False

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

        traits = ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]
        for t in traits:
            ki_wert = st.session_state.ai_bfi.get(t, 0)
            st.metric(f"Geschätzte Ausprägung: {t}", f"{ki_wert} / 5")
            st.progress(float(ki_wert) / 5.0 if ki_wert else 0.0)

        st.divider()

        if not st.session_state.data_saved:
            st.subheader("Abschluss")
            if st.button("Ergebnisse final speichern & beenden"):
                # ANPASSUNG: "condition" im finalen JSON-Payload integriert
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
                    st.error("Speicherfehler beim finalen Senden.")
        else:
            st.success("Daten erfolgreich auf dem Server der Uni Ulm gespeichert!")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.link_button("Zur Uni-Webseite", "https://www.uni-ulm.de/in/psy-dia/forschung/an-studien-teilnehmen/")
            with col_b:
                if st.button("🔄 APP RESET (Nächste Person)"):
                    reset_app()

if __name__ == "__main__":
    main()
