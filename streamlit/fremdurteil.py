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
st.set_page_config(page_title="Übung Teil 2: Transkript-Bewertung", page_icon="📝", layout="wide")

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


# 2. UTILITY FUNKTIONEN (Nextcloud-Interaktion & Filterung)
def get_all_files_from_nextcloud_folder(folder_path):
    """Hilfsfunktion: Holt alle Dateinamen aus einem spezifischen Nextcloud-Ordner via WebDAV."""
    url = f"{NC_URL}{folder_path}/"
    headers = {"Depth": "1"}
    files = set()
    try:
        response = requests.request("PROPFIND", url, auth=AUTH, headers=headers)
        if response.status_code in [207, 200]:
            root = ET.fromstring(response.content)
            for response_elem in root.findall(".//{DAV:}response"):
                href_elem = response_elem.find("{DAV:}href")
                if href_elem is not None:
                    filename = href_elem.text.split("/")[-1]
                    if filename:  # Verzeichniseintrag selbst ignorieren
                        files.add(filename)
    except Exception as e:
        st.error(f"Fehler beim Lesen des Ordners {folder_path}: {e}")
    return files


def analyze_nextcloud_data():
    """
    Kerneylement für das Debugging und die Urnenberechnung.
    Analysiert beide Ordner parallel und ordnet IDs zu.
    """
    # 1. Dateien aus Forschungsdaten laden
    transcript_files = get_all_files_from_nextcloud_folder(TRANSKRIPT_ORDNER)
    
    # Geheime Whitelist aus Secrets laden (Fallback auf leere Liste, falls nicht gesetzt)
    allowed_prelims = st.secrets["nextcloud"].get("allowed_preliminary_vpcodes", [])
    
    # Valide Urnen-Dateien bestimmen
    urne_dateien = []
    for f in transcript_files:
        if not f.endswith(".json"):
            continue
            
        # Fall A: Es ist eine reguläre finale Datei (deine bisherige Logik)
        if not f.endswith("_preliminary.json"):
            prelim_version = f.replace(".json", "_preliminary.json")
            if prelim_version in transcript_files:
                urne_dateien.append(f)
        
        # Fall B: Es ist eine reine Preliminary-Datei, aber der VP-Code steht auf der Whitelist
        else:
            # Beispiel-Dateiname: "interview_04ERNS24_1234567_preliminary.json"
            # Wir splitten den Namen, um an den VP-Code zu kommen
            parts = f.split("_")
            if len(parts) >= 2:
                # Da deine Benennung "interview_VPCODE_..." ist, steht der VPCODE an Index 1
                vp_code_from_file = parts[1] 
                
                if vp_code_from_file in allowed_prelims:
                    urne_dateien.append(f)
                    
    # 2. Dateien aus Fremdurteil laden (ab hier bleibt alles exakt wie in deinem Code)
    result_files = get_all_files_from_nextcloud_folder(ERGEBNIS_ORDNER)
    
    zugelost_in_bearbeitung = []
    bereits_bewertet = []
    
    # Extraktions-Logik basierend auf dem '_target_'-Muster
    for f in result_files:
        if "rater_" in f.lower() and "_target_" in f.lower() and f.endswith(".csv"):
            try:
                # Isoliere den Teil nach "_target_"
                target_part = f.split("_target_")[1]
                
                if target_part.endswith("_preliminary.csv"):
                    # Fall: In Bearbeitung / Zugelost
                    target_id = target_part.replace("_preliminary.csv", "")
                    transcript_name = f"{target_id}.json"
                    zugelost_in_bearbeitung.append(transcript_name)
                else:
                    # Fall: Final Bewertet
                    target_id = target_part.replace(".csv", "")
                    transcript_name = f"{target_id}.json"
                    bereits_bewertet.append(transcript_name)
            except Exception:
                pass

    return {
        "urne_total": urne_dateien,
        "zugelost_preliminary": list(set(zugelost_in_bearbeitung)),
        "bereits_bewertet_final": list(set(bereits_bewertet))
    }


def calculate_available_urn():
    """Berechnet die aktuell frei verfügbaren Transkripte für Rater und schließt das eigene aus."""
    data = analyze_nextcloud_data()
    alle_transkripte = data["urne_total"]
    
    # 1. Blockiert durch andere Rater (preliminary oder final)
    blockiert = set([t.lower() for t in data["zugelost_preliminary"] + data["bereits_bewertet_final"]])
    
    # 2. Eigenes Transkript ausschließen (Sicherheitsabgleich mit User-Inputs)
    user_vp = st.session_state.get("participant_id", "").strip().lower()
    user_matrikel = st.session_state.get("matrikelnummer", "").strip().lower()
    
    verfuegbar = []
    for t in alle_transkripte:
        t_lower = t.lower()
        
        # Falls die Datei bereits von jemand anderem blockiert ist -> überspringen
        if t_lower in blockiert:
            continue
            
        # Abgleich: Ist es das eigene Transkript?
        # Beispiel-Name: "interview_04ERNS24_1234567_preliminary.json" oder "interview_04ERNS24_1234567.json"
        parts = t_lower.split("_")
        
        ist_eigenes = False
        if len(parts) >= 3:
            vp_in_file = parts[1]        # "04erns24"
            matrikel_in_file = parts[2]  # "1234567" (bzw. ohne .json Endung falls kürzer)
            
            # Bereinige potenzielle Dateiendungen, falls der String dort aufhört
            matrikel_in_file = matrikel_in_file.replace(".json", "")
            
            if vp_in_file == user_vp or matrikel_in_file == user_matrikel:
                ist_eigenes = True
                
        # Fallback-Sicherheit: Falls die Namensstruktur mal abweicht, machen wir einen groben Text-Match
        if user_vp in t_lower or (len(user_matrikel) > 4 and user_matrikel in t_lower):
            ist_eigenes = True
            
        # Nur hinzufügen, wenn es NICHT das eigene Interview ist
        if not ist_eigenes:
            verfuegbar.append(t)
    
    # Falls ALLES vergeben ist (oder nur noch das eigene übrig wäre), Fallback auf alle außer das eigene
    if alle_transkripte and not verfuegbar:
        # Erneuter Filter für den Fallback-Pool: Alle Transkripte, außer dem eigenen
        fallback_pool = []
        for t in alle_transkripte:
            t_lower = t.lower()
            parts = t_lower.split("_")
            if len(parts) >= 3:
                if parts[1] != user_vp and parts[2].replace(".json", "") != user_matrikel:
                    fallback_pool.append(t)
            elif user_vp not in t_lower:
                fallback_pool.append(t)
                
        return fallback_pool, True
        
    return verfuegbar, False


def read_and_format_json_transcript(filename):
    """Lädt die JSON-Datei, extrahiert ID, Chat und berechnet/extrahiert das KI-Assessment."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/{filename}"
    response = requests.get(url, auth=AUTH)
    if response.status_code != 200:
        raise Exception(f"Datei konnte nicht geladen werden (Status {response.status_code})")
        
    data = response.json()
    vp_code = data.get("participant_id", data.get("id", filename.replace(".json", "")))
    
    # 1. Rohe KI-Facetten-Scores aus dem JSON laden
    ai_raw = data.get("ai_assessment", {})
    
    # Fallback-Werte (Mitte der Skala = 3), falls ein Key im JSON fehlen sollte
    ai_facets = {
        "A-Fr": ai_raw.get("Freundlichkeit", 3),
        "A-Co": ai_raw.get("Rücksichtnahme", 3),
        "A-H":  ai_raw.get("Hilfsbereitschaft", 3),
        "C-Hw": ai_raw.get("Fleiß", 3),
        "C-O":  ai_raw.get("Organisation", 3),
        "E-A":  ai_raw.get("Durchsetzungsfähigkeit", 3),
        "E-SB": ai_raw.get("Selbstbewusstsein", 3),
        "E-So": ai_raw.get("Soziale Aktivität", 3),
        "N-D":  ai_raw.get("Depression", 3),
        "N-Ir": ai_raw.get("Reizbarkeit", 3),
        "N-St": ai_raw.get("Nervosität", 3),
        "O-In": ai_raw.get("Intellekt", 3),
        "O-R":  ai_raw.get("Reflexion", 3),
        "O-Sc": ai_raw.get("Wissenschaftliches Interesse", 3),
        "HH-Si": ai_raw.get("Aufrichtigkeit", 3),
        "HH-Fa": ai_raw.get("Fairness", 3),
        "HH-Mo": ai_raw.get("Bescheidenheit", 3)
    }
    
    # 2. KI-Hauptdimensionen (Big Five) mathematisch aggregieren
    ai_dimensions = {
        "Verträglichkeit": round((ai_facets["A-Fr"] + ai_facets["A-Co"] + ai_facets["A-H"]) / 3, 2),
        "Gewissenhaftigkeit": round((ai_facets["C-Hw"] + ai_facets["C-O"]) / 2, 2),
        "Extraversion": round((ai_facets["E-A"] + ai_facets["E-SB"] + ai_facets["E-So"]) / 3, 2),
        "Neurotizismus": round((ai_facets["N-D"] + ai_facets["N-Ir"] + ai_facets["N-St"]) / 3, 2),
        "Offenheit": round((ai_facets["O-In"] + ai_facets["O-R"] + ai_facets["O-Sc"]) / 3, 2)
    }
    
    # Kombiniertes Paket im Session State speichern
    ai_assessment_compiled = {
        "dimensions": ai_dimensions,
        "facets": ai_facets
    }
    
    # Chat-Verlauf Formatierung
    formatted_chat = []
    chat_verlauf = data.get("chat", [])
    for message in chat_verlauf:
        role = message.get("role")
        content = message.get("content", "").strip()
        
        if role == "system":
            continue
            
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
    return vp_code, full_transcript_text, ai_assessment_compiled


def upload_results_to_nextcloud(filename, csv_data):
    """Lädt eine CSV-Ergebnisdatei via HTTP PUT in die Nextcloud hoch."""
    url = f"{NC_URL}{ERGEBNIS_ORDNER}/{filename}"
    headers = {"Content-Type": "text/csv; charset=utf-8"}
    response = requests.put(url, data=csv_data.encode('utf-8'), auth=AUTH, headers=headers)
    if response.status_code not in [201, 204]:
        raise Exception(f"Upload fehlgeschlagen mit Status {response.status_code}")


def delete_preliminary_file(filename):
    """Löscht die temporäre Vorab-Datei via HTTP DELETE, wenn das Formular final gesendet wurde."""
    url = f"{NC_URL}{ERGEBNIS_ORDNER}/{filename}"
    try:
        requests.delete(url, auth=AUTH)
    except:
        pass


# 3. SESSION STATE INITIALISIERUNG
if 'step' not in st.session_state: st.session_state.step = "welcome"
if 'participant_id' not in st.session_state: st.session_state.participant_id = ""
if 'matrikelnummer' not in st.session_state: st.session_state.matrikelnummer = ""
if 'alter' not in st.session_state: st.session_state.alter = ""
if 'geschlecht' not in st.session_state: st.session_state.geschlecht = "Keine Angabe"
if 'consent_given' not in st.session_state: st.session_state.consent_given = False
if 'urne' not in st.session_state: st.session_state.urne = []
if 'aktuelles_transkript_file' not in st.session_state: st.session_state.aktuelles_transkript_file = None
if 'vp_code' not in st.session_state: st.session_state.vp_code = ""
if 'transkript_text' not in st.session_state: st.session_state.transkript_text = ""
if 'ai_scores' not in st.session_state: st.session_state.ai_scores = {}
if 'user_scores' not in st.session_state: st.session_state.user_scores = {}
if 'preliminary_filename' not in st.session_state: st.session_state.preliminary_filename = ""
if 'start_zeitpunkt' not in st.session_state: st.session_state.start_zeitpunkt = None


# --- PHASE 1: WILLKOMMEN & DATENEINGABE ---
if st.session_state.step == "welcome":
    st.title("Willkommen zu Teil 2 der Übung: Transkript-Bewertung 📝")
    st.write("Bitte geben Sie Ihre Daten ein, um mit der Zulosung und Bewertung zu beginnen.")
    
    st.markdown("""
    **Anleitung zur Generierung Ihres VP-Codes:**
    * Geben Sie als erstes die Anzahl der Buchstaben des (ersten) Vornamens Ihrer Mutter ein (z.B. 04)
    * Geben Sie als zweites die letzten beiden Buchstaben des Mädchen-(Geburts-)namens der Mutter ein (z.B. ER)
    * Geben Sie als drittes die letzten beiden Buchstaben des (ersten Vornamens) des Vaters ein (z.B. NS)
    * Geben Sie als viertes den Tag Ihrem Geburtstags ein (z.B. 24)

    Ein Versuchspersonencode könnte beispielsweise so aussehen: 04ERNS24
    """)
    
    vp_code_input = st.text_input("VP-Code (Dein Teilnehmer-Code)*", placeholder="z.B. 04ERNS24")
    matrikel_input = st.text_input("Matrikelnummer*", placeholder="z.B. 1234567")
    
    st.write("---")
    st.subheader("Demografische Angaben (Freiwillig)")
    alter_input = st.text_input("Alter (Optional)", placeholder="z.B. 23")
    geschlecht_input = st.selectbox("Geschlecht (Optional)", ["Keine Angabe", "Weiblich", "Männlich", "Divers"])
    
    if st.button("Weiter zur Beschreibung", type="primary"):
        if not vp_code_input.strip() or not matrikel_input.strip():
            st.error("Bitte füllen Sie die Pflichtfelder (*) aus.")
        else:
            st.session_state.participant_id = "".join(x for x in vp_code_input.strip() if x.isalnum())
            st.session_state.matrikelnummer = "".join(x for x in matrikel_input.strip() if x.isalnum())
            st.session_state.alter = alter_input.strip() if alter_input.strip() else "Keine Angabe"
            st.session_state.geschlecht = geschlecht_input
            st.session_state.step = "consent"
            st.rerun()


# --- PHASE 2: EINWILLIGUNG & ABLAUF ---
elif st.session_state.step == "consent":
    st.title("Informationen zum Ablauf & Datenschutz 📝")
    st.markdown("""
    ### Beschreibung & Ablauf der Übungssitzung
    In diesem zweiten Teil der Übung nehmen Sie die Rolle einer **fremdbeurteilenden Person** ein. Ihnen wird das anonymisierte Transkript eines bereits geführten Interviews zugelost.
    
    * **Ihre Aufgabe:** Lesen Sie das Transkript aufmerksam durch. Schätzen Sie die interviewte Person im Anschluss auf den 17 TSDI-Persönlichkeitsfacetten ein.
    * **Leistungsnachweis:** Diese Fremdbeurteilung ist der zweite Teil der wöchentlichen Übungsleistung.
    """)
    
    consent_checked = st.checkbox("Ich stimme der Nutzung meiner anonymisierten Daten für Lehr- und Forschungszwecke zu.")
    
    if st.button("Übungsblock starten & Transkript zulosen", type="primary"):
        st.session_state.consent_given = consent_checked
        st.session_state.step = "evaluation"
        st.rerun()


# --- PHASE 3: EVALUATION (LOSEN, LESEN & FRAGEBOGEN) ---
elif st.session_state.step == "evaluation":
    
    if st.session_state.aktuelles_transkript_file is None:
        st.subheader("Schritt 1: Transkript erhalten")
        st.write("Klicken Sie auf den Button, um ein zufälliges Interview-Transkript aus dem System zugelost zu bekommen.")
        
        if st.button("🎲 Transkript zufällig zulosen", type="primary"):
            with st.spinner("Urne wird mit Nextcloud abgeglichen und Transkript reserviert..."):
                aktuelle_urne, von_vorne_begonnen = calculate_available_urn()
                st.session_state.urne = aktuelle_urne
                
                if not st.session_state.urne:
                    st.error("Keine freien Transkripte im Nextcloud-Ordner gefunden.")
                else:
                    if von_vorne_begonnen:
                        st.toast("🔄 Info: Alle Transkripte wurden bereits einmal verteilt! Eine neue Runde startet von vorne.", icon="ℹ️")
                    
                    gezogenes_file = random.choice(st.session_state.urne)
                    
                    try:
                        vp_code, text, ai_scores = read_and_format_json_transcript(gezogenes_file)
                      
                        # Startzeitpunkt festhalten
                        st.session_state.start_zeitpunkt = datetime.now()
                       
                        rater_string = f"rater_{st.session_state.participant_id}_{st.session_state.matrikelnummer}"
                        target_clean_id = gezogenes_file.replace(".json", "")
                        target_string = f"target_{target_clean_id}"
                        
                        # PRELIMINARY DATEINAME (Sofort hochladen um zu blockieren)
                        prelim_filename = f"{rater_string}_{target_string}_preliminary.csv"
                        placeholder_csv = "Status;Zeitstempel\npreliminary;" + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        upload_results_to_nextcloud(prelim_filename, placeholder_csv)
                        
                        st.session_state.preliminary_filename = prelim_filename
                        st.session_state.aktuelles_transkript_file = gezogenes_file
                        st.session_state.vp_code = vp_code
                        st.session_state.transkript_text = text
                        st.session_state.ai_scores = ai_scores
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Fehler beim Reservieren der Datei: {e}")

    elif not st.session_state.user_scores:
        st.success("Ihnen wurde erfolgreich ein Interview-Transkript zugelost und für Sie reserviert!")
        st.write("---")
        
        # 1. ERSTELLUNG DES ZWEISPALTIGEN LAYOUTS
        col_left, col_right = st.columns([1, 1]) 
        
        # Wir starten das Formular HIER, damit alle Eingaben gesammelt übertragen werden
        with st.form("fragebogen_form"):
            
            # --- LINKE SPALTE: TRANSKRIPT ---
            with col_left:
                st.subheader("📝 Schritt 2: Transkript lesen")
                html_transkript = st.session_state.transkript_text.replace("\n", "<br>")
                
                st.markdown(
                    f"""
                    <div style="background-color: #f9f9f9; color: #111111; padding: 20px; border-radius: 8px;
                                border: 1px solid #e0e0e0; height: 650px; overflow-y: scroll;
                                font-family: monospace; font-size: 14px; line-height: 1.6;">
                        {html_transkript}
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            # --- RECHTE SPALTE: EINSCHÄTZUNG ---
            with col_right:
                st.subheader("🔍 Schritt 3: TSDI-Einschätzung")
                
                # Scrollbare Box NUR für die Slider
                with st.container(height=650):
                    st.markdown("## 🤝 Dimension Verträglichkeit (A)")
                    st.markdown("### 1. Facette: Freundlichkeit (A-Fr)")
                    a_fr_1 = st.slider("Die Person gilt als jemand, mit dem man einfach gut auskommt.", 1, 5, 3, key="x42i29")
                    a_fr_2 = st.slider("Die Person kommt mit den meisten Menschen gut zurecht.", 1, 5, 3, key="x42i14")
                    a_fr_3 = st.slider("Die Person versucht auch fröhlich zu sein, wenn es nicht so gut läuft.", 1, 5, 3, key="x42i43")
                    
                    st.markdown("### 2. Facette: Rücksichtnahme (A-Co)")
                    a_co_1 = st.slider("Die Person behandelt andere Leute immer freundlich.", 1, 5, 3, key="x42i02")
                    a_co_2 = st.slider("Die Person versucht zu jedem freundlich zu sein, den sie kennt.", 1, 5, 3, key="x42i26")
                    a_co_3 = st.slider("Die Person versucht immer höflich zu sein, auch zu denen, die ihr gegenüber unfreundlich sind.", 1, 5, 3, key="x42i27")
                    
                    st.markdown("### 3. Facette: Hilfsbereitschaft (A-H)")
                    a_h_1 = st.slider("Es ist der Person eine Freude, anderen mit ihren Problemen zu helfen.", 1, 5, 3, key="x42i12")
                    a_h_2 = st.slider("Die Person hilft anderen Leuten gerne, auch wenn nichts für sie dabei herausspringt.", 1, 5, 3, key="x42i48")
                    a_h_3 = st.slider("Die Person ist immer großzügig, wenn es darum geht, anderen zu helfen.", 1, 5, 3, key="x42i46")
                    
                    st.markdown("## 🎯 Dimension Gewissenhaftigkeit (C)")
                    st.markdown("### 4. Facette: Fleiß (C-Hw)")
                    c_hw_1 = st.slider("Wenn sich die Person zu etwas verpflichtet, führt sie es immer zu Ende aus.", 1, 5, 3, key="x42i05")
                    c_hw_2 = st.slider("Die Person schätzt sich selbst als sehr ausdauernde Arbeiterin ein.", 1, 5, 3, key="x42i30")
                    c_hw_3 = st.slider("Wenn die Person etwas anfängt, arbeitet sie, bis es zu ihrer Zufriedenheit beendet ist.", 1, 5, 3, key="x42i44")
                    
                    st.markdown("### 5. Facette: Organisation (C-O)")
                    c_o_1 = st.slider("Die Person hält ihre persönlichen Sachen gerne ordentlich und organisiert.", 1, 5, 3, key="x42i18")
                    c_o_2 = st.slider("Die Person versucht einen Plan für Aufgaben zu entwickeln und hält sich daran.", 1, 5, 3, key="x42i49")
                    c_o_3 = st.slider("Die Person versucht vollständig vorbereitet zu sein, bevor sie eine Aufgabe anpackt.", 1, 5, 3, key="x42i39")
                    
                    st.markdown("## 📢 Dimension Extraversion (E)")
                    st.markdown("### 6. Facette: Durchsetzungsfähigkeit (E-A)")
                    e_a_1 = st.slider("Die Person spricht lauter, wenn sie meint, einen Beitrag liefern zu können.", 1, 5, 3, key="x42i42")
                    e_a_2 = st.slider("Die Person neigt dazu, in Gruppen die Führung zu übernehmen.", 1, 5, 3, key="x42i35")
                    e_a_3 = st.slider("Die Person hat eine Menge Einfluss auf andere Leute.", 1, 5, 3, key="x42i03")
                    
                    st.markdown("### 7. Facette: Selbstbewusstsein (E-SB)")
                    e_sb_1 = st.slider("Die Person ist eine sehr schüchterne Person. (Invertiert)", 1, 5, 3, key="x42i23")
                    e_sb_2 = st.slider("Die Freunde der Person halten sie für schüchtern. (Invertiert)", 1, 5, 3, key="x42i10")
                    e_sb_3 = st.slider("Die Person fühlt sich nicht wohl, wenn sie im Zentrum der Aufmerksamkeit steht. (Invertiert)", 1, 5, 3, key="x42i22")
                    
                    st.markdown("### 8. Facette: Soziale Aktivität (E-So)")
                    e_so_1 = st.slider("Die Person ist gerne wo viel los ist.", 1, 5, 3, key="x42i40")
                    e_so_2 = st.slider("Die Person gibt sich große Mühe Leute kennenzulernen.", 1, 5, 3, key="x42i32")
                    e_so_3 = st.slider("Die Person mag Partys auf denen viele Leute sind.", 1, 5, 3, key="x42i20")
                    
                    st.markdown("## 🛡️ Dimension Neurotizismus (N)")
                    st.markdown("### 9. Facette: Depression (N-D)")
                    n_d_1 = st.slider("Es gibt Zeiten, in denen sich die Person selbst bedauert.", 1, 5, 3, key="x42i09")
                    n_d_2 = st.slider("Manchmal ist die Person entmutigt und möchte am liebsten aufgeben.", 1, 5, 3, key="x42i19")
                    n_d_3 = st.slider("Die Person fürchtet oft, dass sie ihre Ziele nicht erreichen könnte.", 1, 5, 3, key="x42i37")
                    
                    st.markdown("### 10. Facette: Reizbarkeit (N-Ir)")
                    n_ir_1 = st.slider("Manchmal regt sich die Person so auf, dass es ihr auf den Magen schlägt.", 1, 5, 3, key="x42i11")
                    n_ir_2 = st.slider("Wenn die Person aufgebracht ist, kann sie nicht mehr klar denken.", 1, 5, 3, key="x42i06")
                    n_ir_3 = st.slider("Die Person kann Kritik nicht sehr gut akzeptieren.", 1, 5, 3, key="x42i07")
                    
                    st.markdown("### 11. Facette: Nervosität (N-St)")
                    n_st_1 = st.slider("Die Person fühlt sich oft müde und erschöpft.", 1, 5, 3, key="x42i36")
                    n_st_2 = st.slider("Wenn die Person unter großem Stress steht, ist sie oft kurz davor zusammenzubrechen.", 1, 5, 3, key="x42i45")
                    n_st_3 = st.slider("Die Person ist oft zittrig und angespannt.", 1, 5, 3, key="x42i13")
                    
                    st.markdown("## 💡 Dimension Offenheit (O)")
                    st.markdown("### 12. Facette: Intellekt (O-In)")
                    o_in_1 = st.slider("Die Person mag es, intellektuelle Diskussionen mit Freunden zu führen.", 1, 5, 3, key="x42i38")
                    o_in_2 = st.slider("Die Person findet intellektuelle Themen interessanter als Sport.", 1, 5, 3, key="x42i28")
                    o_in_3 = st.slider("Die Person besitzt ein hohes Maß an intellektueller Neugier.", 1, 5, 3, key="x42i33")
                    
                    st.markdown("### 13. Facette: Reflexion (O-R)")
                    o_r_1 = st.slider("Die Person verbringt viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.", 1, 5, 3, key="x42i21")
                    o_r_2 = st.slider("Die Person verbringt viel Zeit damit, ihre Gefühlswelt zu erkunden.", 1, 5, 3, key="x42i50")
                    o_r_3 = st.slider("Die Person liest gerne Gedichte.", 1, 5, 3, key="x42i41")
                    
                    st.markdown("### 14. Facette: Wissenschaftliches Interesse (O-Sc)")
                    o_sc_1 = st.slider("Die Person hat sich viele Gedanken über den Ursprung des Universums gemacht.", 1, 5, 3, key="x42i01")
                    o_sc_2 = st.slider("Die Person denkt oft über die Wunder der Natur nach.", 1, 5, 3, key="x42i16")
                    o_sc_3 = st.slider("Die Evolutionstheorie fasziniert die Person.", 1, 5, 3, key="x42i25")
                    
                    st.markdown("## 💎 Dimension Ehrlichkeit-Bescheidenheit (HH)")
                    st.markdown("### 15. Facette: Aufrichtigkeit (HH-Si)")
                    hh_si_1 = st.slider("Wenn die Person von jemandem, den sie nicht mag, etwas will, verhält sie sich sehr nett. (Invertiert)", 1, 5, 3, key="x42i47")
                    hh_si_2 = st.slider("Die Person würde keine Schmeicheleien nutzen, um eine Gehaltserhöhung zu bekommen.", 1, 5, 3, key="x42i15")
                    hh_si_3 = st.slider("Wenn die Person von jemandem etwas will, lache sie auch über dessen schlechteste Witze. (Invertiert)", 1, 5, 3, key="x42i04")
                    
                    st.markdown("### 16. Fairness (HH-Fa)")
                    hh_fa_1 = st.slider("Die Person würde in Versuchung geraten, Diebesgut zu kaufen, wenn sie knapp bei Kasse wäre. (Invertiert)", 1, 5, 3, key="x42i31")
                    hh_fa_2 = st.slider("Die Person würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.", 1, 5, 3, key="x42i17")
                    hh_fa_3 = st.slider("Wenn die Person wüsste, dass sie niemals erwischt wird, wäre sie bereit, eine Million zu stehlen. (Invertiert)", 1, 5, 3, key="x42i08")
                    
                    st.markdown("### 17. Bescheidenheit (HH-Mo)")
                    hh_mo_1 = st.slider("Die Person will, dass alle wissen, dass sie eine wichtige angesehene Person ist. (Invertiert)", 1, 5, 3, key="x42i24")
                    hh_mo_2 = st.slider("Die Person ist eine ganz normale Person, die nicht besser ist als andere.", 1, 5, 3, key="x42i34")
                    hh_mo_3 = st.slider("Die Person will nicht, dass andere Leute sie behandeln, als ob sie ihnen überlegen sei.", 1, 5, 3, key="x42i51")

            # --- BEREICH UNTERHALB DER BEIDEN SPALTEN (IMMER NOCH IM FORMULAR) ---
            st.write("---")
            anmerkungen = st.text_area("Gibt es noch sonstige Auffälligkeiten oder Bemerkungen zur Person? (Optional)", max_chars=500)
            
            # Der offizielle Form-Submit-Button erstreckt sich über die volle Breite
            submit_button = st.form_submit_button("Fremdurteil absenden", type="primary", use_container_width=True)
            
            if submit_button:
                with st.spinner("Ihre Antworten werden sicher übertragen..."):
                    
                    # 1. ZEITMESSUNG
                    end_zeitpunkt = datetime.now()
                    start_zeitpunkt = st.session_state.get("start_zeitpunkt", end_zeitpunkt)
                    dauer_sekunden = round((end_zeitpunkt - start_zeitpunkt).total_seconds(), 1)
                    
                    # 2. BERECHNUNGEN (Invertierungen & Facetten)
                    e_sb_rec = ( (6 - e_sb_1) + (6 - e_sb_2) + (6 - e_sb_3) ) / 3
                    hh_si_rec = ( (6 - hh_si_1) + hh_si_2 + (6 - hh_si_3) ) / 3
                    hh_fa_rec = ( (6 - hh_fa_1) + hh_fa_2 + (6 - hh_fa_3) ) / 3
                    hh_mo_rec = ( (6 - hh_mo_1) + hh_mo_2 + hh_mo_3 ) / 3
                    
                    facette_a_fr = (a_fr_1 + a_fr_2 + a_fr_3) / 3
                    facette_a_co = (a_co_1 + a_co_2 + a_co_3) / 3
                    facette_a_h  = (a_h_1 + a_h_2 + a_h_3) / 3
                    facette_c_hw = (c_hw_1 + c_hw_2 + c_hw_3) / 3
                    facette_c_o  = (c_o_1 + c_o_2 + c_o_3) / 3
                    facette_e_a  = (e_a_1 + e_a_2 + e_a_3) / 3
                    facette_e_so = (e_so_1 + e_so_2 + e_so_3) / 3
                    facette_n_d  = (n_d_1 + n_d_2 + n_d_3) / 3
                    facette_n_ir = (n_ir_1 + n_ir_2 + n_ir_3) / 3
                    facette_n_st = (n_st_1 + n_st_2 + n_st_3) / 3
                    facette_o_in = (o_in_1 + o_in_2 + o_in_3) / 3
                    facette_o_r  = (o_r_1 + o_r_2 + o_r_3) / 3
                    facette_o_sc = (o_sc_1 + o_sc_2 + o_sc_3) / 3
                    
                    user_extraversion = (facette_e_a + e_sb_rec + facette_e_so) / 3
                    user_vertraeglichkeit = (facette_a_fr + facette_a_co + facette_a_h) / 3
                    user_gewissenhaftigkeit = (facette_c_hw + facette_c_o) / 2
                    user_neurotizismus = (facette_n_d + facette_n_ir + facette_n_st) / 3
                    user_offenheit = (facette_o_in + facette_o_r + facette_o_sc) / 3

                    st.session_state.user_scores = {
                        "Extraversion": round(user_extraversion, 2),
                        "Verträglichkeit": round(user_vertraeglichkeit, 2),
                        "Gewissenhaftigkeit": round(user_gewissenhaftigkeit, 2),
                        "Neurotizismus": round(user_neurotizismus, 2),
                        "Offenheit": round(user_offenheit, 2)
                    }
                    
                    ergebnis_daten = {
                        "Zeitstempel": end_zeitpunkt.strftime("%Y-%m-%d %H:%M:%S"),
                        "Bearbeitung_Start": start_zeitpunkt.strftime("%Y-%m-%d %H:%M:%S") if st.session_state.start_zeitpunkt else "N/A",
                        "Bearbeitung_Ende": end_zeitpunkt.strftime("%Y-%m-%d %H:%M:%S"),
                        "Bearbeitungsdauer_Sekunden": dauer_sekunden,
                        "Rater_VP_Code": st.session_state.participant_id,      
                        "Rater_Matrikelnummer": st.session_state.matrikelnummer,
                        "Rater_Alter": st.session_state.alter,
                        "Rater_Geschlecht": st.session_state.geschlecht,
                        "Forschungs_Consent": 1 if st.session_state.consent_given else 0,
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_Target_VP_Code": st.session_state.vp_code, 
                        
                        "x42i_a_fr_1": a_fr_1,   "x42i_a_fr_2": a_fr_2,   "x42i_a_fr_3": a_fr_3,
                        "x42i_a_co_1": a_co_1,   "x42i_a_co_2": a_co_2,   "x42i_a_co_3": a_co_3,
                        "x42i_a_h_1": a_h_1,     "x42i_a_h_2": a_h_2,     "x42i_a_h_3": a_h_3,
                        "x42i_c_hw_1": c_hw_1,   "x42i_c_hw_2": c_hw_2,   "x42i_c_hw_3": c_hw_3,
                        "x42i_c_o_1": c_o_1,     "x42i_c_o_2": c_o_2,     "x42i_c_o_3": c_o_3,
                        "x42i_e_a_1": e_a_1,     "x42i_e_a_2": e_a_2,     "x42i_e_a_3": e_a_3,
                        "x42i_e_sb_1": e_sb_1,   "x42i_e_sb_2": e_sb_2,   "x42i_e_sb_3": e_sb_3,
                        "x42i_e_so_1": e_so_1,   "x42i_e_so_2": e_so_2,   "x42i_e_so_3": e_so_3,
                        "x42i_n_d_1": n_d_1,     "x42i_n_d_2": n_d_2,     "x42i_n_d_3": n_d_3,
                        "x42i_n_ir_1": n_ir_1,   "x42i_n_ir_2": n_ir_2,   "x42i_n_ir_3": n_ir_3,
                        "x42i_n_st_1": n_st_1,   "x42i_n_st_2": n_st_2,   "x42i_n_st_3": n_st_3,
                        "x42i_o_in_1": o_in_1,   "x42i_o_in_2": o_in_2,   "x42i_o_in_3": o_in_3,
                        "x42i_o_r_1": o_r_1,     "x42i_o_r_2": o_r_2,     "x42i_o_r_3": o_r_3,
                        "x42i_o_sc_1": o_sc_1,   "x42i_o_sc_2": o_sc_2,   "x42i_o_sc_3": o_sc_3,
                        "x42i_hh_si_1": hh_si_1, "x42i_hh_si_2": hh_si_2, "x42i_hh_si_3": hh_si_3,
                        "x42i_hh_fa_1": hh_fa_1, "x42i_hh_fa_2": hh_fa_2, "x42i_hh_fa_3": hh_fa_3,
                        "x42i_hh_mo_1": hh_mo_1, "x42i_hh_mo_2": hh_mo_2, "x42i_hh_mo_3": hh_mo_3,
                        
                        "USER_Extraversion": st.session_state.user_scores["Extraversion"],
                        "USER_Vertraeglichkeit": st.session_state.user_scores["Verträglichkeit"],
                        "USER_Gewissenhaftigkeit": st.session_state.user_scores["Gewissenhaftigkeit"],
                        "USER_Neurotizismus": st.session_state.user_scores["Neurotizismus"],
                        "USER_Offenheit": st.session_state.user_scores["Offenheit"],
                        "AI_Extraversion": st.session_state.ai_scores.get("Extraversion"),
                        "AI_Vertraeglichkeit": st.session_state.ai_scores.get("Verträglichkeit"),
                        "AI_Gewissenhaftigkeit": st.session_state.ai_scores.get("Gewissenhaftigkeit"),
                        "AI_Neurotizismus": st.session_state.ai_scores.get("Neurotizismus"),
                        "AI_Offenheit": st.session_state.ai_scores.get("Offenheit"),
                        "Freitext_Anmerkungen": anmerkungen.replace("\n", " ")
                    }
                    
                    df = pd.DataFrame([ergebnis_daten])
                    csv_string = df.to_csv(index=False, sep=";")
                    
                    rater_part = f"rater_{st.session_state.participant_id}_{st.session_state.matrikelnummer}"
                    target_clean_id = st.session_state.aktuelles_transkript_file.replace(".json", "")
                    target_part = f"target_{target_clean_id}"
                    
                    finaler_dateiname = f"{rater_part}_{target_part}.csv"
                    
                    try:
                        upload_results_to_nextcloud(finaler_dateiname, csv_string)
                        if st.session_state.preliminary_filename:
                            delete_preliminary_file(st.session_state.preliminary_filename)
                        
                        # ZUERST den Step ändern, damit die App weiß, dass sie die Feedback-Seite zeigen soll!
                        st.session_state.step = "feedback" 
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern: {e}")

# --- FEEDBACK-BILDSCHIRM ---
else:
    st.balloons()
    st.subheader("🎉 Vielen Dank für Ihre Teilnahme!")
    st.write("Ihre Antworten wurden erfolgreich registriert und an Nextcloud übertragen. Schauen Sie sich hier an, wie gut Ihre Fremdeinschätzung im Vergleich zur KI war. Wechseln Sie zwischen den Tabs **Gesamturteil** und **Facettenurteil**")
    st.write("---")
    
    # Aufteilung der Ergebnisse in übersichtliche Tabs
    tab_big5, tab_facetten = st.tabs(["📊 1. Gesamturteil", "🔍 2. Facettenurteil"])
    
    # Extraktion der kompilierten KI-Ergebnisse
    ai_compiled = st.session_state.ai_scores
    ai_dims = ai_compiled.get("dimensions", {})
    ai_facs = ai_compiled.get("facets", {})
    
    # --- TAB 1: BIG FIVE HAUPTEBENE ---
    with tab_big5:
        st.subheader("🤖 Gesamturteil im Vergleich zur KI")
        
        vergleichs_daten = []
        gesamte_abweichung = 0
        
        for dimension in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
            user_val = st.session_state.user_scores.get(dimension, 3)
            ai_val = ai_dims.get(dimension, 3)
            diff = round(abs(user_val - ai_val), 2)
            gesamte_abweichung += diff
            
            if diff <= 0.5: feedback = "🎯 Nahezu identisch!"
            elif diff <= 1.2: feedback = "👍 Sehr nah dran"
            else: feedback = "🔄 Andere Wahrnehmung"
                
            vergleichs_daten.append({
                "Big-Five Dimension": dimension,
                "Ihre Einschätzung (Mittelwert)": user_val,
                "KI-Einschätzung (Mittelwert)": ai_val,
                "Abweichung": diff,
                "Feedback": feedback
            })
            
        df_vergleich = pd.DataFrame(vergleichs_daten)
        st.table(df_vergleich)
        
        gesamte_abweichung = round(gesamte_abweichung, 2)
        st.write("")
        if gesamte_abweichung <= 2.5:
            st.info(f"🧠 **Fazit:** Starke Übereinstimmung auf globaler Ebene! (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        elif gesamte_abweichung <= 5.0:
            st.info(f"📊 **Fazit:** Solide Annäherung auf globaler Ebene. (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        else:
            st.info(f"👥 **Fazit:** Spannende unterschiedliche Wahrnehmungen! (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")

    # --- TAB 2: DETALLIERTE FACETTEN-EBENE ---
    with tab_facetten:
        st.subheader("🔎 Facettenurteil im Vergleich zur KI")
        st.write("Vergleichen Sie Ihre Einschätzung mit der der KI für jede der 17 Persönlichkeitsfacetten:")

        raw_facetten_konfiguration = [
            ("Verträglichkeit (A)", "Freundlichkeit (A-Fr)", (st.session_state.get("x42i29", 3) + st.session_state.get("x42i14", 3) + st.session_state.get("x42i43", 3)) / 3, "A-Fr"),
            ("Verträglichkeit (A)", "Rücksichtnahme (A-Co)", (st.session_state.get("x42i02", 3) + st.session_state.get("x42i26", 3) + st.session_state.get("x42i27", 3)) / 3, "A-Co"),
            ("Verträglichkeit (A)", "Hilfsbereitschaft (A-H)", (st.session_state.get("x42i12", 3) + st.session_state.get("x42i48", 3) + st.session_state.get("x42i46", 3)) / 3, "A-H"),
            
            ("Gewissenhaftigkeit (C)", "Fleiß (C-Hw)", (st.session_state.get("x42i05", 3) + st.session_state.get("x42i30", 3) + st.session_state.get("x42i44", 3)) / 3, "C-Hw"),
            ("Gewissenhaftigkeit (C)", "Organisation (C-O)", (st.session_state.get("x42i18", 3) + st.session_state.get("x42i49", 3) + st.session_state.get("x42i39", 3)) / 3, "C-O"),
            
            ("Extraversion (E)", "Durchsetzungsfähigkeit (E-A)", (st.session_state.get("x42i42", 3) + st.session_state.get("x42i35", 3) + st.session_state.get("x42i03", 3)) / 3, "E-A"),
            ("Extraversion (E)", "Selbstbewusstsein (E-SB)*", ((6 - st.session_state.get("x42i23", 3)) + (6 - st.session_state.get("x42i10", 3)) + (6 - st.session_state.get("x42i22", 3))) / 3, "E-SB"),
            ("Extraversion (E)", "Soziale Aktivität (E-So)", (st.session_state.get("x42i40", 3) + st.session_state.get("x42i32", 3) + st.session_state.get("x42i20", 3)) / 3, "E-So"),
            
            ("Neurotizismus (N)", "Depression (N-D)", (st.session_state.get("x42i09", 3) + st.session_state.get("x42i19", 3) + st.session_state.get("x42i37", 3)) / 3, "N-D"),
            ("Neurotizismus (N)", "Reizbarkeit (N-Ir)", (st.session_state.get("x42i11", 3) + st.session_state.get("x42i06", 3) + st.session_state.get("x42i07", 3)) / 3, "N-Ir"),
            ("Neurotizismus (N)", "Nervosität (N-St)", (st.session_state.get("x42i36", 3) + st.session_state.get("x42i45", 3) + st.session_state.get("x42i13", 3)) / 3, "N-St"),
            
            ("Offenheit (O)", "Intellekt (O-In)", (st.session_state.get("x42i38", 3) + st.session_state.get("x42i28", 3) + st.session_state.get("x42i33", 3)) / 3, "O-In"),
            ("Offenheit (O)", "Reflexion (O-R)", (st.session_state.get("x42i21", 3) + st.session_state.get("x42i50", 3) + st.session_state.get("x42i41", 3)) / 3, "O-R"),
            ("Offenheit (O)", "Wissenschaftl. Interesse (O-Sc)", (st.session_state.get("x42i01", 3) + st.session_state.get("x42i16", 3) + st.session_state.get("x42i25", 3)) / 3, "O-Sc"),
            
            ("Ehrlichkeit-Bescheidenheit (HH)", "Aufrichtigkeit (HH-Si)*", ((6 - st.session_state.get("x42i47", 3)) + st.session_state.get("x42i15", 3) + (6 - st.session_state.get("x42i04", 3))) / 3, "HH-Si"),
            ("Ehrlichkeit-Bescheidenheit (HH)", "Fairness (HH-Fa)*", ((6 - st.session_state.get("x42i31", 3)) + st.session_state.get("x42i17", 3) + (6 - st.session_state.get("x42i08", 3))) / 3, "HH-Fa"),
            ("Ehrlichkeit-Bescheidenheit (HH)", "Bescheidenheit (HH-Mo)*", ((6 - st.session_state.get("x42i24", 3)) + st.session_state.get("x42i34", 3) + st.session_state.get("x42i51", 3)) / 3, "HH-Mo")
        ]
        
        facetten_vergleichs_daten = []
        for dim_label, facet_label, user_calc_val, short_key in raw_facetten_konfiguration:
            u_val = round(user_calc_val, 2)
            a_val = float(ai_facs.get(short_key, 3))
            f_diff = round(abs(u_val - a_val), 2)
            
            if f_diff <= 0.34: f_feedback = "🎯 Identisch"
            elif f_diff <= 1.01: f_feedback = "👍 Ähnlich"
            else: f_feedback = "🔄 Abweichend"
            
            facetten_vergleichs_daten.append({
                "Hauptdimension": dim_label,
                "TSDI Facette": facet_label,
                "Ihr Wert": u_val,
                "KI Wert": a_val,
                "Abweichung": f_diff,
                "Verhältnis": f_feedback
            })
            
        df_facetten = pd.DataFrame(facetten_vergleichs_daten)
        
        st.dataframe(
            df_facetten, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Ihr Wert": st.column_config.NumberColumn(format="%.2f"),
                "KI Wert": st.column_config.NumberColumn(format="%.2f"),
                "Abweichung": st.column_config.NumberColumn(format="%.2f")
            }
        )
        st.caption("* Werte enthalten bereits mathematisch korrekt invertierte Items.")

    st.write("---")
    if st.button("Nächste Teilnahme starten"):
        st.session_state.step = "welcome"
        st.session_state.participant_id = ""
        st.session_state.matrikelnummer = ""
        st.session_state.alter = ""
        st.session_state.geschlecht = "Keine Angabe"
        st.session_state.consent_given = False
        st.session_state.aktuelles_transkript_file = None
        st.session_state.vp_code = ""
        st.session_state.transkript_text = ""
        st.session_state.ai_scores = {}
        st.session_state.user_scores = {}
        st.session_state.preliminary_filename = ""
        st.rerun()

# ==========================================
# 🛠️ ADMIN-BEREICH & DEBUGGING (SIDEBAR & MAIN VIEW)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Admin-Bereich")

admin_password = st.sidebar.text_input("Sicherheitspasswort eingeben", type="password")
ADMIN_PASSWORT_PROV = "DeinSicheresPasswort2026" 

if admin_password == ADMIN_PASSWORT_PROV:
    st.sidebar.success("🔑 Admin-Modus aktiv!")
    
    st.write("---")
    st.header("🛠️ Forschungs-Dashboard (Admin & Debugging View)")
    
    with st.spinner("Lese aktuelle Ordnerstrukturen aus Nextcloud..."):
        nc_analysis = analyze_nextcloud_data()
    
    total_urn = nc_analysis["urne_total"]
    prelim_assigned = nc_analysis["zugelost_preliminary"]
    final_evaluated = nc_analysis["bereits_bewertet_final"]
    
    blockierte_ids = set([t.lower() for t in prelim_assigned + final_evaluated])
    pool_verbleibend = [t for t in total_urn if t.lower() not in blockierte_ids]
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("In Urne (Gesamt)", len(total_urn))
    with col2: st.metric("Zugelost (In Bearbeitung)", len(prelim_assigned))
    with col3: st.metric("Bereits bewertet (Final)", len(final_evaluated))
    with col4: st.metric("Aktuell frei für Ziehung", len(pool_verbleibend))
        
    aktuellt_gezogen = st.session_state.aktuelles_transkript_file
    if aktuellt_gezogen:
        st.info(f"👀 **Dieser Browser testet aktuell:** `{aktuellt_gezogen}`")

    tab1, tab2, tab3 = st.tabs([
        "📋 1. Dateien in der Urne", 
        "⏳ 2. Zugelost (Preliminary)", 
        "✅ 3. Bewertet (Final)"
    ])
    
    with tab1:
        st.subheader("Dateien in der Urne (Forschungsdaten)")
        st.write("Alle validen `.json`-Transkripte (Exklusive reiner Vorab-Versionen):")
        if total_urn:
            df_urn = pd.DataFrame(sorted(total_urn), columns=["Dateiname im Nextcloud-Ordner"])
            st.dataframe(df_urn, use_container_width=True)
        else:
            st.warning("Keine passenden JSON-Paare im Forschungsdaten-Ordner gefunden.")
            
    with tab2:
        st.subheader("Zugelost / Aktuell in Bearbeitung")
        st.write("Erkannt aus `fremdurteil/` anhand des Suffixes `_preliminary.csv` nach dem `_target_`-Block:")
        if prelim_assigned:
            df_prelim = pd.DataFrame(sorted(prelim_assigned), columns=["Gezogene Target-ID (.json Äquivalent)"])
            st.dataframe(df_prelim, use_container_width=True)
        else:
            st.info("Aktuell ist kein Transkript blockiert oder in Bearbeitung.")
            
    with tab3:
        st.subheader("Bereits final bewertete Transkripte")
        st.write("Erkannt aus `fremdurteil/` anhand finaler `.csv`-Dateien (ohne preliminary) nach dem `_target_`-Block:")
        if final_evaluated:
            df_final = pd.DataFrame(sorted(final_evaluated), columns=["Bewertete Target-ID (.json Äquivalent)"])
            st.dataframe(df_final, use_container_width=True)
        else:
            st.info("Bisher wurden keine finalen Bewertungen abgegeben.")

elif admin_password:
    st.sidebar.error("❌ Falsches Passwort.")
