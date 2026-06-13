import streamlit as st
import random
import pandas as pd
from datetime import datetime
from webdav3.client import Client
import io

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

# 3. UTILITY FUNKTIONEN (Nextcloud-Interaktion)
def load_transcript_list():
    """Liest alle .txt Dateien aus dem Nextcloud-Transkriptordner."""
    try:
        # .list() benötigt den Ordnernamen. Wir hängen ein '/' an, 
        # damit WebDAV weiß, dass es ein Verzeichnis ist.
        ordner_pfad = f"{TRANSKRIPT_ORDNER}/"
        files = client.list(ordner_pfad)
        
        # Nur .txt Dateien herausfiltern
        transcripts = [f for f in files if f.endswith('.txt')]
        return transcripts
    except Exception as e:
        st.error(f"Fehler beim Laden der Transkriptliste: {e}")
        return []

def read_transcript_content(filename):
    """Lädt den Textinhalt einer spezifischen Datei aus der Nextcloud."""
    # Falls der filename vom Server schon den Ordnerpfad enthält, bereinigen wir ihn
    clean_filename = filename.split("/")[-1]
    remote_path = f"{TRANSKRIPT_ORDNER}/{clean_filename}"
    
    buffer = io.BytesIO()
    # Nutze die offizielle WebDAV-Methode zum direkten Download in den Speicher
    client.download_from(remote_path=remote_path, file_to=buffer)
    return buffer.getvalue().decode('utf-8')

def upload_results_to_nextcloud(filename, csv_data):
    """Lädt die CSV-Ergebnisdatei in den Ergebnisordner der Nextcloud hoch."""
    remote_path = f"{ERGEBNIS_ORDNER}/{filename}"
    buffer = io.BytesIO(csv_data.encode('utf-8'))
    client.upload_to(remote_path=remote_path, file_to=buffer)

# 4. SESSION STATE INITIALISIERUNG (Zustandsverwaltung)
if 'urne' not in st.session_state:
    # Beim ersten Start die Liste der Transkripte aus Nextcloud holen
    st.session_state.urne = load_transcript_list()

if 'aktuelles_transkript' not in st.session_state:
    st.session_state.aktuelles_transkript = None

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

# SCHRITT 1: LOREN
if st.session_state.aktuelles_transkript is None:
    st.subheader("Schritt 1: Transkript erhalten")
    
    if not st.session_state.urne:
        st.warning("Keine Transkripte im Nextcloud-Ordner gefunden oder Urne leer. Bitte den Studienleiter kontaktieren.")
    else:
        if st.button("🎲 Transkript zufällig zulosen", type="primary"):
            # Zufälliges Element aus der Urne ziehen und entfernen (Balancing)
            gezogenes_transkript = random.choice(st.session_state.urne)
            st.session_state.urne.remove(gezogenes_transkript)
            
            # Text live aus Nextcloud nachladen
            with st.spinner("Transkript wird geladen..."):
                text = read_transcript_content(gezogenes_transkript)
                
            st.session_state.aktuelles_transkript = gezogenes_transkript
            st.session_state.transkript_text = text
            st.rerun()

# SCHRITT 2 & 3: ANZEIGEN & BEWERTEN
else:
    if not st.session_state.abgesendet:
        st.success(f"Dir wurde folgendes Transkript zugelost: **{st.session_state.aktuelles_transkript}**")
        
        # Textbox zur Anzeige des Transkripts (Scrollbar inklusive)
        st.subheader("Schritt 2: Transkript lesen")
        st.text_area(
            label="Inhalt des Interviews:", 
            value=st.session_state.transkript_text, 
            height=400, 
            disabled=True
        )
        
        st.write("---")
        
        # Der Fragebogen
        st.subheader("Schritt 3: Persönlichkeitseinschätzung")
        st.write("Bitte schätze die Person im Interview anhand der folgenden Skalen ein (1 = trifft gar nicht zu, 5 = trifft vollkommen zu):")
        
        with st.form("fragebogen_form"):
            # Beispiel-Items (kannst du beliebig erweitern/anpassen)
            extraversion = st.slider("Die Person wirkt extravertiert, gesellig und gesprächig.", 1, 5, 3)
            vertraeglichkeit = st.slider("Die Person wirkt rücksichtsvoll, empathisch und kooperativ.", 1, 5, 3)
            gewissenhaftigkeit = st.slider("Die Person wirkt organisiert, gründlich und zielstrebig.", 1, 5, 3)
            neurotizismus = st.slider("Die Person wirkt emotional labil, unsicher oder nervös.", 1, 5, 3)
            offenheit = st.slider("Die Person wirkt offen für neue Erfahrungen und einfallsreich.", 1, 5, 3)
            
            st.write("")
            anmerkungen = st.text_area("Gibt es noch sonstige Auffälligkeiten oder Bemerkungen zur Person? (Optional)", max_chars=500)
            
            submit_button = st.form_submit_button("Formular absenden", type="primary")
            
            if submit_button:
                with st.spinner("Deine Antworten werden verschlüsselt übertragen..."):
                    # Daten strukturieren
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Bewertetes_Transkript": st.session_state.aktuelles_transkript,
                        "BFI_Extraversion": extraversion,
                        "BFI_Vertraeglichkeit": vertraeglichkeit,
                        "BFI_Gewissenhaftigkeit": gewissenhaftigkeit,
                        "BFI_Neurotizismus": neurotizismus,
                        "BFI_Offenheit": openness,
                        "Freitext_Anmerkungen": anmerkungen.replace("\n", " ") # Zeilenumbrüche für CSV entfernen
                    }
                    
                    # DataFrame erzeugen und in CSV-String umwandeln
                    df = pd.DataFrame([ergebnis_daten])
                    csv_string = df.to_csv(index=False, sep=";")
                    
                    # Dateiname eindeutig generieren
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dateiname = f"ergebnis_{st.session_state.aktuelles_transkript.replace('.txt', '')}_{timestamp_str}.csv"
                    
                    # In Nextcloud hochladen
                    try:
                        upload_results_to_nextcloud(dateiname, csv_string)
                        st.session_state.abgesendet = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern der Daten. Bitte versuche es erneut oder wende dich an den Studienleiter. (Fehler: {e})")

    else:
        # Danksagung nach erfolgreichem Upload
        st.balloons()
        st.subheader("🎉 Vielen Dank für deine Teilnahme!")
        st.write("Deine Antworten wurden erfolgreich und anonymisiert in unserer Forschungsdatenbank gespeichert. Du kannst das Browserfenster jetzt schließen.")
        
        # Ermöglicht einem neuen Teilnehmer am selben Gerät einen Neustart
        if st.button("Nächste Teilnahme starten"):
            st.session_state.aktuelles_transkript = None
            st.session_state.transkript_text = ""
            st.session_state.abgesendet = False
            st.rerun()
