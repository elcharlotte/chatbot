import streamlit as st
import random
import pandas as pd
from datetime import datetime
from webdav3.client import Client
import io
import json

# 1. SEITEN-KONFIGURATION
st.set_page_config(page_title="Forschungsstudie: Transkript-Bewertung", page_icon="📝", layout="centered")

# 2. WEBDAV / NEXTCLOUD VERBINDUNG AUFBAUEN
@st.cache_resource
def get_nextcloud_client():
    """Erstellt eine dauerhafte Verbindung zur Nextcloud basierend auf den Secrets."""
    options = {
        'webdav_url': st.secrets["nextcloud"]["url"],
        'webdav_username': st.secrets["nextcloud"]["username"],
        'webdav_password': st.secrets["nextcloud"]["password"]
    }
    return Client(options)

try:
    client = get_nextcloud_client()
except Exception as e:
    st.error("Verbindung zur Nextcloud fehlgeschlagen. Bitte überprüfe die Secrets.")
    st.stop()

# Pfade aus den Secrets auslesen
TRANSKRIPT_ORDNER = st.secrets["nextcloud"]["folder_transcripts"]
ERGEBNIS_ORDNER = st.secrets["nextcloud"]["folder_results"]

# 3. UTILITY FUNKTIONEN (Nextcloud-Interaktion für deine JSON-Struktur)
def load_transcript_list():
    """Liest alle .json Dateien aus dem Nextcloud-Transkriptordner."""
    try:
        # Wir säubern den Ordnernamen von eventuellen Schrägstrichen am Anfang/Ende
        clean_folder = TRANSKRIPT_ORDNER.strip("/")
        
        # Einige WebDAV-Versionen brauchen den relativen Pfad ohne führenden Slash
        files = client.list(clean_folder)
        
        # Nur .json Dateien filtern
        transcripts = [f for f in files if f.endswith('.json')]
        return transcripts
    except Exception as e:
        # Wenn es fehlschlägt, testen wir einen alternativen absoluten WebDAV-Aufruf
        try:
            files = client.list(f"/{TRANSKRIPT_ORDNER.strip('/')}")
            return [f for f in files if f.endswith('.json')]
        except:
            st.error(f"Fehler beim Laden der Transkriptliste: {e}")
            return []

def read_and_format_json_transcript(filename):
    """Lädt die JSON-Datei, extrahiert die ID sowie den formatierten Chat-Verlauf."""
    clean_filename = filename.split("/")[-1]
    
    # Pfad absolut und sauber zusammensetzen
    clean_folder = TRANSKRIPT_ORDNER.strip("/")
    remote_path = f"{clean_folder}/{clean_filename}"
    
    buffer = io.BytesIO()
    client.download_from(remote_path=remote_path, file_to=buffer)
    
    json_text = buffer.getvalue().decode('utf-8')
    data = json.loads(json_text)
    
    vp_code = data.get("id", clean_filename.replace(".json", ""))
    
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
    """Lädt die CSV-Ergebnisdatei in den Ergebnisordner der Nextcloud hoch."""
    clean_folder = ERGEBNIS_ORDNER.strip("/")
    remote_path = f"{clean_folder}/{filename}"
    buffer = io.BytesIO(csv_data.encode('utf-8'))
    client.upload_to(remote_path=remote_path, file_to=buffer)

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
            # Zufälliges JSON aus der Urne ziehen und für diese Session entfernen (Balancing)
            gezogenes_file = random.choice(st.session_state.urne)
            st.session_state.urne.remove(gezogenes_file)
            
            # Text live aus Nextcloud laden & parsen
            with st.spinner("Transkript wird geladen..."):
                vp_code, text = read_and_format_json_transcript(gezogenes_file)
                
            st.session_state.aktuelles_transkript_file = gezogenes_file
            st.session_state.vp_code = vp_code
            st.session_state.transkript_text = text
            st.rerun()

# SCHRITT 2 & 3: ANZEIGEN & BEWERTEN
else:
    if not st.session_state.abgesendet:
        st.success("Dir wurde erfolgreich ein Interview-Transkript zugelost!")
        
        # Textbox zur Anzeige des reinen Transkript-Inhalts (Scrollbar inklusive)
        st.subheader("Schritt 2: Transkript lesen")
        st.text_area(
            label="Inhalt des Gesprächs:", 
            value=st.session_state.transkript_text, 
            height=450, 
            disabled=True
        )
        
        st.write("---")
        
        # Der Fragebogen
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
                    # Daten strukturieren
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_VP_Code": st.session_state.vp_code,  # Die extrahierte ID (z.B. "07mit hexaco")
                        "BFI_Extraversion": extraversion,
                        "BFI_Vertraeglichkeit": vertraeglichkeit,
                        "BFI_Gewissenhaftigkeit": gewissenhaftigkeit,
                        "BFI_Neurotizismus": neurotizismus,
                        "BFI_Offenheit": openness,
                        "Freitext_Anmerkungen": anmerkungen.replace("\n", " ")  # Zeilenumbrüche entfernen
                    }
                    
                    # DataFrame erzeugen und in CSV-String umwandeln
                    df = pd.DataFrame([ergebnis_daten])
                    csv_string = df.to_csv(index=False, sep=";")
                    
                    # Eindeutigen Dateinamen für das Ergebnis generieren (Nutzt den echten VP-Code im Namen)
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_vp_name = "".join(x for x in st.session_state.vp_code if x.isalnum() or x in "._-").strip()
                    dateiname = f"ergebnis_{clean_vp_name}_{timestamp_str}.csv"
                    
                    # In Nextcloud abspeichern
                    try:
                        upload_results_to_nextcloud(dateiname, csv_string)
                        st.session_state.abgesendet = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern der Daten. Bitte versuche es erneut oder wende dich an den Studienleiter. (Fehler: {e})")

    else:
        # Ansicht nach erfolgreichem Absenden
        st.balloons()
        st.subheader("🎉 Vielen Dank für deine Teilnahme!")
        st.write("Deine Antworten wurden erfolgreich gespeichert. Du kannst das Browserfenster jetzt schließen.")
        
        # Option für Testzwecke / Kiosk-Modus im Labor
        if st.button("Nächste Teilnahme starten"):
            st.session_state.aktuelles_transkript_file = None
            st.session_state.vp_code = ""
            st.session_state.transkript_text = ""
            st.session_state.abgesendet = False
            st.rerun()
