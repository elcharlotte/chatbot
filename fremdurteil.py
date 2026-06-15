import streamlit as st
import random
import pandas as pd
from datetime import datetime
import io
import json
import requests
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET

# 1. SEITEN-KONFIGURATION
st.set_page_config(page_title="Forschungsstudie: Transkript-Bewertung", page_icon="📝", layout="centered")

# Zugangsdaten aus Secrets laden & bereinigen
NC_USER = st.secrets["nextcloud"]["username"].strip()
NC_PASS = st.secrets["nextcloud"]["password"].strip()
TRANSKRIPT_ORDNER = st.secrets["nextcloud"]["folder_transcripts"].strip("/")
ERGEBNIS_ORDNER = st.secrets["nextcloud"]["folder_results"].strip("/")

base_url = st.secrets["nextcloud"]["url"].strip()
if not base_url.endswith("/"):
    base_url += "/"
if not base_url.endswith(f"files/{NC_USER}/"):
    if "remote.php/dav" in base_url and not "files" in base_url:
        base_url = base_url.rstrip("/") + f"/files/{NC_USER}/"

NC_URL = base_url
AUTH = HTTPBasicAuth(NC_USER, NC_PASS)

# 2. UTILITY FUNKTIONEN (Nextcloud-Interaktion)
def load_transcript_list():
    """Liest alle .json Dateien via WebDAV PROPFIND aus der Nextcloud."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/"
    headers = {"Depth": "1"}
    try:
        response = requests.request("PROPFIND", url, auth=AUTH, headers=headers)
        if response.status_code not in [207, 200]:
            st.error(f"Nextcloud-Fehler: Status {response.status_code}. Ordnerpfad korrekt?")
            return []
            
        root = ET.fromstring(response.content)
        files = []
        for response_elem in root.findall(".//{DAV:}response"):
            href_elem = response_elem.find("{DAV:}href")
            if href_elem is not None:
                href = href_elem.text
                filename = href.split("/")[-1]
                if filename.endswith(".json"):
                    files.append(filename)
        return files
    except Exception as e:
        st.error(f"Verbindungsfehler zur Nextcloud: {e}")
        return []

def read_and_format_json_transcript(filename):
    """Lädt die JSON-Datei, extrahiert ID, Chat und das KI-Assessment (falls vorhanden)."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/{filename}"
    response = requests.get(url, auth=AUTH)
    if response.status_code != 200:
        raise Exception(f"Datei konnte nicht geladen werden (Status {response.status_code})")
        
    data = response.json()
    
    # 1. Flexible Extraktion des VP-Codes des Interviewten (sucht nach 'participant_id' oder 'id')
    vp_code = data.get("participant_id", data.get("id", filename.replace(".json", "")))
    
    # 2. KI-Bewertung extrahieren (Fällt auf Standard 3 zurück, falls im JSON nicht vorhanden)
    ai_assessment = data.get("ai_assessment", {
        "Extraversion": 3,
        "Verträglichkeit": 3,
        "Gewissenhaftigkeit": 3,
        "Neurotizismus": 3,
        "Offenheit": 3
    })
    
    # 3. Chat-Verlauf formatieren
    formatted_chat = []
    chat_verlauf = data.get("chat", [])
    for message in chat_verlauf:
        role = message.get("role")
        content = message.get("content", "").strip()
        
        if role == "system":
            continue
            
        # Falls der Assistant-Text als JSON-String verpackt ist (wie im neuen Output-Beispiel)
        if role == "assistant" and content.startswith("{"):
            try:
                content_json = json.loads(content)
                content = content_json.get("interviewer_text", content)
            except:
                pass
        
        if role == "assistant":
            label = "Interviewer (KI)"
        elif role == "user":
            label = "Teilnehmer (Mensch)"
        else:
            label = role.capitalize()
            
        formatted_chat.append(f"{label}:\n{content}\n")
        
    full_transcript_text = "\n".join(formatted_chat)
    return vp_code, full_transcript_text, ai_assessment

def upload_results_to_nextcloud(filename, csv_data):
    """Lädt die CSV-Ergebnisdatei via HTTP PUT in die Nextcloud hoch."""
    url = f"{NC_URL}{ERGEBNIS_ORDNER}/{filename}"
    headers = {"Content-Type": "text/csv; charset=utf-8"}
    response = requests.put(url, data=csv_data.encode('utf-8'), auth=AUTH, headers=headers)
    if response.status_code not in [201, 204]:
        raise Exception(f"Upload fehlgeschlagen mit Status {response.status_code}")

# 3. SESSION STATE INITIALISIERUNG
if 'step' not in st.session_state:
    st.session_state.step = "welcome"

if 'participant_id' not in st.session_state:
    st.session_state.participant_id = ""

if 'matrikelnummer' not in st.session_state:
    st.session_state.matrikelnummer = ""

if 'urne' not in st.session_state:
    st.session_state.urne = load_transcript_list()

if 'aktuelles_transkript_file' not in st.session_state:
    st.session_state.aktuelles_transkript_file = None

if 'vp_code' not in st.session_state:
    st.session_state.vp_code = ""

if 'transkript_text' not in st.session_state:
    st.session_state.transkript_text = ""

if 'ai_scores' not in st.session_state:
    st.session_state.ai_scores = {}

if 'user_scores' not in st.session_state:
    st.session_state.user_scores = {}


# --- PHASE 1: WILLKOMMEN & DATENEINGABE ---
if st.session_state.step == "welcome":
    st.title("Willkommen zu Teil 2 der Übung: Transkript-Bewertung 📝")
    st.write("Bitte geben Sie Ihre Daten ein, um mit der Zulosung und Bewertung zu beginnen.")
    
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
    
    vp_code_input = st.text_input("VP-Code (Dein Teilnehmer-Code)", placeholder="z.B. 04ERNS24")
    matrikel_input = st.text_input("Matrikelnummer", placeholder="z.B. 1234567")
    
    if st.button("Weiter zur Beschreibung", type="primary"):
        if not vp_code_input.strip() or not matrikel_input.strip():
            st.error("Bitte füllen Sie beide Felder aus.")
        else:
            st.session_state.participant_id = vp_code_input.strip()
            st.session_state.matrikelnummer = matrikel_input.strip()
            st.session_state.step = "consent"
            st.rerun()


# --- PHASE 2: EINWILLIGUNG & ABLAUF ---
elif st.session_state.step == "consent":
    st.title("Informationen zum Ablauf & Datenschutz 📝")
    st.markdown("""
    ### Beschreibung & Ablauf der Übungssitzung
    In diesem zweiten Teil der Übung nehmen Sie die Rolle einer **fremdbeurteilenden Person** ein. Ihnen wird das anonymisierte Transkript eines bereits geführten Interviews zugelost.
    
    * **Ihre Aufgabe:** Lesen Sie das Transkript aufmerksam durch. Schätzen Sie die interviewte Person im Anschluss auf den Big-Five-Persönlichkeitsskalen ein.
    * **Verpflichtung:** Diese Fremdbeurteilung ist der zweite Teil der wöchentlichen Übungsleistung. Wer nicht teilnimmt oder unvollständige Daten abgibt, erhält keinen Credit.
    * **Ethikvotum:** Bewilligt unter **[PLATZHALTER: Ethikantrag-ID]**.
    
    ### Datenschutz
    * **Anonymität:** Die Ihnen vorgelegten Transkripte enthalten keinerlei Klarnamen oder direkt identifizierbare Merkmale. Ihre eigenen Angaben (Matrikelnummer) werden strikt getrennt von den Bewertungsergebnissen zur Leistungsverbuchung genutzt.
    * **Speicherung:** Alle Auswertungen und Daten werden auf sicheren Servern gespeichert.
    """)
    
    consent_checked = st.checkbox("Ich habe die oben genannten Informationen gelesen und stimme der anonymisierten Nutzung und Speicherung meiner Beurteilungsdaten zu Forschungs- und Lehrzwecken zu.")
    
    if st.button("Studie starten & Transkript zulosen", type="primary"):
        if consent_checked:
            st.session_state.step = "evaluation"
            st.rerun()
        else:
            st.warning("Bitte stimmen Sie den Datenschutzbestimmungen zu, um fortzufahren.")


# --- PHASE 3: EVALUATION (LOSEN, LESEN & FRAGEBOGEN) ---
elif st.session_state.step == "evaluation":
    
    # Unterphase A: Noch kein Transkript gelost
    if st.session_state.aktuelles_transkript_file is None:
        st.subheader("Schritt 1: Transkript erhalten")
        st.write("Klicken Sie auf den Button, um ein zufälliges Interview-Transkript aus dem System zugelost zu bekommen.")
        
        if not st.session_state.urne:
            st.warning("Keine Transkripte im Nextcloud-Ordner gefunden oder Urne leer. Bitte den Studienleiter kontaktieren.")
        else:
            if st.button("🎲 Transkript zufällig zulosen", type="primary"):
                gezogenes_file = random.choice(st.session_state.urne)
                st.session_state.urne.remove(gezogenes_file)
                
                with st.spinner("Transkript wird geladen..."):
                    try:
                        vp_code, text, ai_scores = read_and_format_json_transcript(gezogenes_file)
                        st.session_state.aktuelles_transkript_file = gezogenes_file
                        st.session_state.vp_code = vp_code
                        st.session_state.transkript_text = text
                        st.session_state.ai_scores = ai_scores
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Laden der Datei: {e}")

    # Unterphase B: Transkript gelost, Fragebogen anzeigen
    elif not st.session_state.user_scores:
        st.success("Ihnen wurde erfolgreich ein Interview-Transkript zugelost!")
        
        st.subheader("Schritt 2: Transkript lesen")
        
        # NEU: Ein wunderschöner, kontrastreicher Scroll-Container statt der grauen Textarea
        # .replace("\n", "<br>") sorgt dafür, dass die Zeilenumbrüche im HTML erhalten bleiben
        html_transkript = st.session_state.transkript_text.replace("\n", "<br>")
        
        st.markdown(
            f"""
            <div style="
                background-color: #f9f9f9;
                color: #111111;
                padding: 20px;
                border-radius: 8px;
                border: 1px solid #e0e0e0;
                height: 450px;
                overflow-y: scroll;
                font-family: monospace;
                font-size: 14px;
                line-height: 1.6;
                box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
            ">
                {html_transkript}
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        st.write("---")
        
        st.subheader("Schritt 3: Persönlichkeitseinschätzung")
        st.write("Bitte schätzen Sie die Person im Interview anhand der folgenden Skalen ein (1 = trifft gar nicht zu, 5 = trifft vollkommen zu):")
        
        with st.form("fragebogen_form"):
            extraversion = st.slider("Die Person wirkt extravertiert, gesellig und gesprächig.", 1, 5, 3)
            vertraeglichkeit = st.slider("Die Person wirkt rücksichtsvoll, empathisch und kooperativ.", 1, 5, 3)
            gewissenhaftigkeit = st.slider("Die Person wirkt organisiert, gründlich und zielstrebig.", 1, 5, 3)
            neurotizismus = st.slider("Die Person wirkt emotional labil, unsicher oder nervös.", 1, 5, 3)
            offenheit = st.slider("Die Person wirkt offen für neue Erfahrungen und einfallsreich.", 1, 5, 3)
            
            st.write("")
            anmerkungen = st.text_area("Gibt es noch sonstige Auffälligkeiten oder Bemerkungen zur Person? (Optional)", max_chars=500)
            
            submit_button = st.form_submit_button("Formular absenden", type="primary")
            
            if submit_button:
                with st.spinner("Ihre Antworten werden sicher übertragen..."):
                    # 1. Zwischenspeichern für das Feedback
                    st.session_state.user_scores = {
                        "Extraversion": extraversion,
                        "Verträglichkeit": vertraeglichkeit,
                        "Gewissenhaftigkeit": gewissenhaftigkeit,
                        "Neurotizismus": neurotizismus,
                        "Offenheit": offenheit
                    }
                    
                    # 2. Daten für die CSV strukturieren (Inklusive RATER-Infos!)
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Rater_VP_Code": st.session_state.participant_id,      
                        "Rater_Matrikelnummer": st.session_state.matrikelnummer, 
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_Target_VP_Code": st.session_state.vp_code, 
                        "USER_Extraversion": extraversion,
                        "USER_Vertraeglichkeit": vertraeglichkeit,
                        "USER_Gewissenhaftigkeit": gewissenhaftigkeit,
                        "USER_Neurotizismus": neurotizismus,
                        "USER_Offenheit": offenheit,
                        "AI_Extraversion": st.session_state.ai_scores.get("Extraversion"),
                        "AI_Vertraeglichkeit": st.session_state.ai_scores.get("Verträglichkeit"),
                        "AI_Gewissenhaftigkeit": st.session_state.ai_scores.get("Gewissenhaftigkeit"),
                        "AI_Neurotizismus": st.session_state.ai_scores.get("Neurotizismus"),
                        "AI_Offenheit": st.session_state.ai_scores.get("Offenheit"),
                        "Freitext_Anmerkungen": anmerkungen.replace("\n", " ")
                    }
                    
                    df = pd.DataFrame([ergebnis_daten])
                    csv_string = df.to_csv(index=False, sep=";")
                    
                    # Eindeutigen Ergebnis-Dateinamen generieren
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_target_name = "".join(x for x in st.session_state.vp_code if x.isalnum() or x in "._-").strip()
                    clean_rater_name = "".join(x for x in st.session_state.participant_id if x.isalnum() or x in "._-").strip()
                    dateiname = f"ergebnis_Rater_{clean_rater_name}_Target_{clean_target_name}_{timestamp_str}.csv"
                    
                    try:
                        upload_results_to_nextcloud(dateiname, csv_string)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern der Daten: {e}")
                        st.session_state.user_scores = {}

    # Unterphase C: Abgesendet -> Feedback-Bildschirm anzeigen
    else:
        st.balloons()
        st.subheader("🎉 Vielen Dank für Ihre Teilnahme!")
        st.write("Ihre Antworten wurden erfolgreich und sicher unter Ihrer Matrikelnummer registriert.")
        
        st.write("---")
        st.subheader("🤖 Ihr Urteil im Vergleich zur KI-Bewertung")
        st.write("Hier sehen Sie, wie nah Ihre Einschätzung an der algorithmischen Auswertung der KI lag:")
        
        vergleichs_daten = []
        gesamte_abweichung = 0
        
        for dimension in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
            user_val = st.session_state.user_scores.get(dimension, 3)
            ai_val = st.session_state.ai_scores.get(dimension, 3)
            diff = abs(user_val - ai_val)
            gesamte_abweichung += diff
            
            if diff == 0:
                feedback = "🎯 Volltreffer!"
            elif diff == 1:
                feedback = "👍 Sehr nah dran"
            else:
                feedback = "🔄 Andere Wahrnehmung"
                
            vergleichs_daten.append({
                "Big-Five Dimension": dimension,
                "Deine Einschätzung": user_val,
                "KI-Einschätzung": ai_val,
                "Abweichung": diff,
                "Feedback": feedback
            })
            
        df_vergleich = pd.DataFrame(vergleichs_daten)
        st.table(df_vergleich)
        
        st.write("")
        if gesamte_abweichung <= 2:
            st.info(f"🧠 **Fazit:** Sie haben eine extreme Ähnlichkeit zur KI-Auswertung! Ihre Gesamtabweichung liegt bei nur **{gesamte_abweichung}** Punkten.")
        elif gesamte_abweichung <= 5:
            st.info(f"📊 **Fazit:** Gute Übereinstimmung. Sie haben das Profil im Wesentlichen genau so wahrgenommen wie der Algorithmus (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        else:
            st.info(f"👥 **Fazit:** Spannend! Ihre menschliche Intuition weicht vom Algorithmus ab (Gesamtabweichung: **{gesamte_abweichung}** Punkte). Genau diese Unterschiede untersuchen wir.")

        st.write("---")
        
        # Komplett-Reset für den Kiosk-Modus
        if st.button("Nächste Teilnahme starten"):
            st.session_state.step = "welcome"
            st.session_state.participant_id = ""
            st.session_state.matrikelnummer = ""
            st.session_state.aktuelles_transkript_file = None
            st.session_state.vp_code = ""
            st.session_state.transkript_text = ""
            st.session_state.ai_scores = {}
            st.session_state.user_scores = {}
            st.rerun()
