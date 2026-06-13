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

# Daten laden und radikal von fehlerhaften Slashes befreien
NC_USER = st.secrets["nextcloud"]["username"].strip()
NC_PASS = st.secrets["nextcloud"]["password"].strip()
TRANSKRIPT_ORDNER = st.secrets["nextcloud"]["folder_transcripts"].strip("/")
ERGEBNIS_ORDNER = st.secrets["nextcloud"]["folder_results"].strip("/")

# URL-Säuberung: Wir stellen sicher, dass am Ende von files/DEIN_USER ein / steht
base_url = st.secrets["nextcloud"]["url"].strip()
if not base_url.endswith("/"):
    base_url += "/"

# Falls du aus Versehen deinen Usernamen am Ende der URL vergessen hast, fangen wir das hier ab:
if not base_url.endswith(f"files/{NC_USER}/"):
    # Falls die URL nur bis /dav/ geht, bauen wir den Rest sauber an
    if "remote.php/dav" in base_url and not "files" in base_url:
        base_url = base_url.rstrip("/") + f"/files/{NC_USER}/"

NC_URL = base_url
AUTH = HTTPBasicAuth(NC_USER, NC_PASS)

# DIAGNOSE-ANZEIGE (Nur für dich zum Testen – falls es fehlschlägt)
st.write(f"Test-URL: {NC_URL}{TRANSKRIPT_ORDNER}/") # <-- Auskommentieren zum Prüfen!
TRANSKRIPT_ORDNER = st.secrets["nextcloud"]["folder_transcripts"].strip("/")
ERGEBNIS_ORDNER = st.secrets["nextcloud"]["folder_results"].strip("/")

AUTH = HTTPBasicAuth(NC_USER, NC_PASS)

# 3. UTILITY FUNKTIONEN (Via Direkt-HTTP/WebDAV-Anfragen)
def load_transcript_list():
    """Liest alle .json Dateien via WebDAV PROPFIND direkt aus dem Nextcloud-Ordner."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/"
    headers = {"Depth": "1"}
    
    try:
        # PROPFIND ist der Standard-WebDAV-Befehl um Ordnerinhalte aufzulisten
        response = requests.request("PROPFIND", url, auth=AUTH, headers=headers)
        
        if response.status_code not in [207, 200]:
            st.error(f"Nextcloud-Fehler: Status {response.status_code}. Ordnerpfad korrekt?")
            return []
            
        # XML-Antwort der Nextcloud parsen, um Dateinamen zu extrahieren
        root = ET.fromstring(response.content)
        files = []
        
        for response_elem in root.findall(".//{DAV:}response"):
            href_elem = response_elem.find("{DAV:}href")
            if href_elem is not None:
                href = href_elem.text
                filename = href.split("/")[-1]
                # Nur .json Dateien aufnehmen, die kein Ordner selbst sind
                if filename.endswith(".json"):
                    files.append(filename)
        return files
        
    except Exception as e:
        st.error(f"Verbindungsfehler zur Nextcloud: {e}")
        return []

def read_and_format_json_transcript(filename):
    """Lädt die JSON-Datei via HTTP GET und formatiert den Chat."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/{filename}"
    
    response = requests.get(url, auth=AUTH)
    if response.status_code != 200:
        raise Exception(f"Datei konnte nicht geladen werden (Status {response.status_code})")
        
    data = response.json()
    
    # VP-Code extrahieren
    vp_code = data.get("id", filename.replace(".json", ""))
    
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
    return vp_code, full_transcript_text

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

if 'abgesendet' not in st.session_state:
    st.session_state.abgesendet = False

# 5. BENUTZEROBERFLÄCHE (UI)
st.title("📝 Wissenschaftliche Untersuchung: KI-Interviews")
st.write("""
Willkommen zu unserer Studie! 
Im ersten Schritt wird dir ein zufälliges Transkript eines KI-Interviews zugelost. 
Bitte lies dir dieses aufmerksam durch und fülle im Anschluss den kurzen Persönlichkeitsfragebogen aus.
""")

st.write("---")

# SCHRITT 1: ZULOSEN
if st.session_state.aktuelles_transkript_file is None:
    st.subheader("Schritt 1: Transkript erhalten")
    
    if not st.session_state.urne:
        st.warning("Keine Transkripte im Nextcloud-Ordner gefunden oder Urne leer. Bitte den Studienleiter kontaktieren.")
    else:
        if st.button("🎲 Transkript zufällig zulosen", type="primary"):
            gezogenes_file = random.choice(st.session_state.urne)
            st.session_state.urne.remove(gezogenes_file)
            
            with st.spinner("Transkript wird geladen..."):
                try:
                    vp_code, text = read_and_format_json_transcript(gezogenes_file)
                    st.session_state.aktuelles_transkript_file = gezogenes_file
                    st.session_state.vp_code = vp_code
                    st.session_state.transkript_text = text
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Laden der Datei: {e}")

# SCHRITT 2 & 3: ANZEIGEN & BEWERTEN
else:
    if not st.session_state.abgesendet:
        st.success("Dir wurde erfolgreich ein Interview-Transkript zugelost!")
        
        st.subheader("Schritt 2: Transkript lesen")
        st.text_area(
            label="Inhalt des Gesprächs:", 
            value=st.session_state.transkript_text, 
            height=450, 
            disabled=True
        )
        
        st.write("---")
        
        st.subheader("Schritt 3: Persönlichkeitseinschätzung")
        st.write("Bitte schätze die Person im Interview anhand der folgenden Skalen ein (1 = trifft gar nicht zu, 5 = trifft vollkommen zu):")
        
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
                with st.spinner("Deine Antworten werden sicher übertragen..."):
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_VP_Code": st.session_state.vp_code,
                        "BFI_Extraversion": extraversion,
                        "BFI_Vertraeglichkeit": vertraeglichkeit,
                        "BFI_Gewissenhaftigkeit": gewissenhaftigkeit,
                        "BFI_Neurotizismus": neurotizismus,
                        "BFI_Offenheit": offenheit,
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

    else:
        st.balloons()
        st.subheader("🎉 Vielen Dank für deine Teilnahme!")
        st.write("Deine Antworten wurden erfolgreich gespeichert. Du kannst das Browserfenster jetzt schließen.")
        
        if st.button("Nächste Teilnahme starten"):
            st.session_state.aktuelles_transkript_file = None
            st.session_state.vp_code = ""
            st.session_state.transkript_text = ""
            st.session_state.abgesendet = False
            st.rerun()
