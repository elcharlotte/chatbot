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
st.set_page_config(page_title="Teil 2 Übung: Transkript-Bewertung", page_icon="📝", layout="centered")

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

# 3. UTILITY FUNKTIONEN
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
    """Lädt die JSON-Datei, extrahiert ID, Chat und das KI-Assessment."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/{filename}"
    response = requests.get(url, auth=AUTH)
    if response.status_code != 200:
        raise Exception(f"Datei konnte nicht geladen werden (Status {response.status_code})")
        
    data = response.json()
    
    # 1. VP-Code extrahieren
    vp_code = data.get("id", filename.replace(".json", ""))
    
    # 2. KI-Bewertung extrahieren (Fällt auf Standard 3 zurück, falls nicht vorhanden)
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

# 4. SESSION STATE INITIALISIERUNG
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

if 'abgesendet' not in st.session_state:
    st.session_state.abgesendet = False

# 5. BENUTZEROBERFLÄCHE (UI)
st.title("📝 Fremdbeurteilung")
st.write("""
Willkommen zum zweiten Teil der Übungssitzung! 
Im ersten Schritt wird Ihnen ein zufälliges Transkript eines KI-Interviews zugelost. 
Bitte lesen Sie sich dieses aufmerksam durch und füllen Sie im Anschluss den Persönlichkeitsfragebogen über die Person, deren Transkript Sie gelesen haben, aus.
""")

st.write("---")

# SCHRITT 1: ZULOSEN
if st.session_state.aktuelles_transkript_file is None:
    st.subheader("Schritt 1: Transkript erhalten")
    
    if not st.session_state.urne:
        st.warning("Keine Transkripte im Nextcloud-Ordner gefunden oder Urne leer. Bitte kontaktiere elisa.altgassen@uni-ulm.de.")
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

# SCHRITT 2 & 3: ANZEIGEN & BEWERTEN
else:
    if not st.session_state.abgesendet:
        st.success("Ihnen wurde erfolgreich ein Interview-Transkript zugelost!")
        
        st.subheader("Schritt 2: Transkript lesen")
        st.text_area(
            label="Inhalt des Gesprächs:", 
            value=st.session_state.transkript_text, 
            height=450, 
            disabled=True
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
                    # Nutzereinschätzungen zwischenspeichern für den Feedback-Bildschirm
                    st.session_state.user_scores = {
                        "Extraversion": extraversion,
                        "Verträglichkeit": vertraeglichkeit,
                        "Gewissenhaftigkeit": gewissenhaftigkeit,
                        "Neurotizismus": neurotizismus,
                        "Offenheit": offenheit
                    }
                    
                    # Für die CSV-Datei vorbereiten (wir speichern auch direkt die KI-Werte zum Vergleich mit ab!)
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_VP_Code": st.session_state.vp_code,
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
                    
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_vp_name = "".join(x for x in st.session_state.vp_code if x.isalnum() or x in "._-").strip()
                    dateiname = f"ergebnis_{clean_vp_name}_{timestamp_str}.csv"
                    
                    try:
                        upload_results_to_nextcloud(dateiname, csv_string)
                        st.session_state.abgesendet = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern der Daten: {e}")

    # DER NEUE RÜCKMELDUNGS-BILDSCHIRM
    else:
        st.balloons()
        st.subheader("🎉 Vielen Dank für Ihre Teilnahme!")
        st.write("Ihre Antworten wurden erfolgreich und sicher in der Nextcloud gespeichert.")
        
        st.write("---")
        st.subheader("🤖 Ihr Urteil im Vergleich zur KI-Bewertung")
        st.write("Hier sehen Sie, wie nah Ihre Einschätzung an der Einschäzung der KI lag:")
        
        # Tabelle für den visuellen Vergleich bauen
        vergleichs_daten = []
        gesamte_abweichung = 0
        
        for dimension in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
            user_val = st.session_state.user_scores.get(dimension, 3)
            ai_val = st.session_state.ai_scores.get(dimension, 3)
            # Absolute Differenz berechnen
            diff = abs(user_val - ai_val)
            gesamte_abweichung += diff
            
            # Feedback-Spruch je nach Abweichung
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
            
        # Als schöne Streamlit-Tabelle anzeigen
        df_vergleich = pd.DataFrame(vergleichs_daten)
        st.table(df_vergleich)
        
        # Gesamt-Fazit ziehen
        st.write("")
        if gesamte_abweichung <= 2:
            st.info(f"🧠 **Fazit:** Sie haben eine extreme Ähnlichkeit zur KI-Auswertung! Die Gesamtabweichung liegt bei nur **{gesamte_abweichung}** Punkten über alle 5 Dimensionen hinweg.")
        elif gesamte_abweichung <= 5:
            st.info(f"📊 **Fazit:** Gute Übereinstimmung. Sie haben das Profil im Wesentlichen genau so wahrgenommen wie der Algorithmus (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        else:
            st.info(f"👥 **Fazit:** Spannend! Ihre menschliche Intuition weicht in einigen Punkten von der KI ab (Gesamtabweichung: **{gesamte_abweichung}** Punkte). Genau diese Unterschiede untersuchen wir in dieser Forschungsarbeit.")

        st.write("---")
        
        # Kiosk-Button für die nächste Versuchsperson
        if st.button("Nächste Teilnahme starten"):
            st.session_state.aktuelles_transkript_file = None
            st.session_state.vp_code = ""
            st.session_state.transkript_text = ""
            st.session_state.ai_scores = {}
            st.session_state.user_scores = {}
            st.session_state.abgesendet = False
            st.rerun()
