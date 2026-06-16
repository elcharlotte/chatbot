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
    """Liest alle .json Dateien, die auf '_preliminary' enden, via WebDAV PROPFIND aus der Nextcloud."""
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
                # Filtert nur Dateien, die auf "_preliminary.json" enden
                if filename.endswith("_preliminary.json"):
                    files.append(filename)
        return files
    except Exception as e:
        st.error(f"Verbindungsfehler zur Nextcloud: {e}")
        return []

def load_already_assigned_transcripts():
    """
    Liest den Ergebnisordner in Nextcloud aus und prüft anhand der Dateinamen,
    welche Targets/Transkripte bereits bewertet/zugelost wurden.
    Dateiformat: ergebnis_Rater_XXX_Target_DATENAME.json_TIMESTAMP.csv
    """
    url = f"{NC_URL}{ERGEBNIS_ORDNER}/"
    headers = {"Depth": "1"}
    assigned = set()
    try:
        response = requests.request("PROPFIND", url, auth=AUTH, headers=headers)
        if response.status_code in [207, 200]:
            root = ET.fromstring(response.content)
            for response_elem in root.findall(".//{DAV:}response"):
                href_elem = response_elem.find("{DAV:}href")
                if href_elem is not None:
                    filename = href_elem.text.split("/")[-1]
                    # Extrahiere das Transkript-File aus dem Standard-Dateinamen
                    if filename.startswith("ergebnis_Rater_") and "_Target_" in filename:
                        try:
                            # Teilt beim Target auf und isoliert das Transkript (inkl. .json)
                            parts = filename.split("_Target_")[1]
                            # Sucht das Ende des JSON-Namens
                            if ".json" in parts:
                                transcript_file = parts.split(".json")[0] + ".json"
                                assigned.add(transcript_file)
                        except:
                            pass
        return assigned
    except Exception:
        return set()

def calculate_available_urn():
    """
    Berechnet die aktuell verfügbare Urne unter Berücksichtigung aller Nutzer.
    Falls alle Transkripte bereits vergeben wurden (Urne leer), wird von vorne begonnen.
    """
    alle_transkripte = load_transcript_list()
    bereits_vergeben = load_already_assigned_transcripts()
    
    # Filtere alle Transkripte heraus, die schon von IRGENDWEM bearbeitet wurden
    verfuegbar = [t for t in alle_transkripte if t not in bereits_vergeben]
    
    # FALLS MEHR NUTZER ALS TRANSKRIPTE: Runde zurücksetzen (Von vorne beginnen)
    if alle_transkripte and not verfuegbar:
        # Die Urne ist für diese Runde leer -> Wir geben für die neue Runde wieder alle frei
        return alle_transkripte, True
        
    return verfuegbar, False

def read_and_format_json_transcript(filename):
    """Lädt die JSON-Datei, extrahiert ID, Chat und das KI-Assessment."""
    url = f"{NC_URL}{TRANSKRIPT_ORDNER}/{filename}"
    response = requests.get(url, auth=AUTH)
    if response.status_code != 200:
        raise Exception(f"Datei konnte nicht geladen werden (Status {response.status_code})")
        
    data = response.json()
    
    # VP-Code des Interviewten extrahieren
    vp_code = data.get("participant_id", data.get("id", filename.replace(".json", "")))
    
    # KI-Bewertung extrahieren (Fällt auf Standard 3 zurück, falls im JSON nicht vorhanden)
    ai_assessment = data.get("ai_assessment", {
        "Extraversion": 3,
        "Verträglichkeit": 3,
        "Gewissenhaftigkeit": 3,
        "Neurotizismus": 3,
        "Offenheit": 3
    })
    
    # Chat-Verlauf formatieren
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

if 'alter' not in st.session_state:
    st.session_state.alter = ""

if 'geschlecht' not in st.session_state:
    st.session_state.geschlecht = "Keine Angabe"

if 'consent_given' not in st.session_state:
    st.session_state.consent_given = False

# Globale Urne wird jetzt live beim Klicken berechnet, wir initialisieren hier nur einen Platzhalter
if 'urne' not in st.session_state:
    st.session_state.urne = []

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
    * Geben Sie als viertes den Tag Ihrem Geburtstags ein (z.B. 24)

    Ein Versuchspersonencode könnte beispielsweise so aussehen: 04ERNS24
    """)
    
    # Pflichtangaben
    vp_code_input = st.text_input("VP-Code (Dein Teilnehmer-Code)*", placeholder="z.B. 04ERNS24")
    matrikel_input = st.text_input("Matrikelnummer*", placeholder="z.B. 1234567")
    
    st.write("---")
    # Freiwillige Angaben
    st.subheader("Demografische Angaben (Freiwillig)")
    alter_input = st.text_input("Alter (Optional)", placeholder="z.B. 23")
    geschlecht_input = st.selectbox("Geschlecht (Optional)", ["Keine Angabe", "Weiblich", "Männlich", "Divers"])
    
    if st.button("Weiter zur Beschreibung", type="primary"):
        if not vp_code_input.strip() or not matrikel_input.strip():
            st.error("Bitte füllen Sie die Pflichtfelder (*) aus.")
        else:
            st.session_state.participant_id = vp_code_input.strip()
            st.session_state.matrikelnummer = matrikel_input.strip()
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
    * **Verpflichtung:** Diese Fremdbeurteilung ist der zweite Teil der wöchentlichen Übungsleistung.
    """)
    
    # Nicht verpflichtende Checkbox
    consent_checked = st.checkbox("Ich stimme der Nutzung meiner anonymisierten Daten für zusätzliche Forschungszwecke freiwillig zu.")
    
    if st.button("Übungsblock starten & Transkript zulosen", type="primary"):
        st.session_state.consent_given = consent_checked
        st.session_state.step = "evaluation"
        st.rerun()


# --- PHASE 3: EVALUATION (LOSEN, LESEN & FRAGEBOGEN) ---
elif st.session_state.step == "evaluation":
    
    if st.session_state.aktuelles_transkript_file is None:
        st.subheader("Schritt 1: Transkript erhalten")
        st.write("Klicken Sie auf den Button, um ein zufälliges Interview-Transkript aus dem System zugelost zu bekommen.")
        st.write("_Hinweis: Das System stellt sicher, dass Sie ein Transkript bekommen, das von anderen noch nicht oder am seltensten bewertet wurde._")
        
        if st.button("🎲 Transkript zufällig zulosen", type="primary"):
            with st.spinner("Urne wird mit Nextcloud abgeglichen und Transkript geladen..."):
                # LIVE-ABGLEICH: Was ist jetzt noch in der globalen Urne frei?
                aktuelle_urne, von_vorne_begonnen = calculate_available_urn()
                st.session_state.urne = aktuelle_urne
                
                if not st.session_state.urne:
                    st.error("Keine Transkripte im Nextcloud-Ordner gefunden.")
                else:
                    if von_vorne_begonnen:
                        st.toast("🔄 Info: Alle Transkripte wurden bereits einmal verteilt! Eine neue Runde startet von vorne.", icon="ℹ️")
                    
                    # Zufällige Ziehung aus den verbleibenden
                    gezogenes_file = random.choice(st.session_state.urne)
                    
                    try:
                        vp_code, text, ai_scores = read_and_format_json_transcript(gezogenes_file)
                        st.session_state.aktuelles_transkript_file = gezogenes_file
                        st.session_state.vp_code = vp_code
                        st.session_state.transkript_text = text
                        st.session_state.ai_scores = ai_scores
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Laden der Datei: {e}")

    elif not st.session_state.user_scores:
        st.success("Ihnen wurde erfolgreich ein Interview-Transkript zugelost!")
        
        st.subheader("Schritt 2: Transkript lesen")
        
        html_transkript = st.session_state.transkript_text.replace("\n", "<br>")
        st.markdown(
            f"""
            <div style="background-color: #f9f9f9; color: #111111; padding: 20px; border-radius: 8px;
                        border: 1px solid #e0e0e0; height: 450px; overflow-y: scroll;
                        font-family: monospace; font-size: 14px; line-height: 1.6;">
                {html_transkript}
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        st.write("---")
        
        st.subheader("Schritt 3: TSDI-Persönlichkeitseinschätzung")
        st.write("Bitte schätzen Sie die Person hinsichtlich ihrer Persönlichkeit ein (1 = trifft gar nicht zu, 5 = trifft vollkommen zu). Falls Sie zu einer Aussage keine Aussage treffen können, fällen Sie ihr Urteil anhand der gegeben Informationen:")

        with st.form("fragebogen_form"):
            
            # ==========================================
            # 🤝 DIMENSION VERTRÄGLICHKEIT (A)
            # ==========================================
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
            
            st.write("---")

            # ==========================================
            # 🎯 DIMENSION GEWISSENHAFTIGKEIT (C)
            # ==========================================
            st.markdown("## 🎯 Dimension Gewissenhaftigkeit (C)")
            
            st.markdown("### 4. Facette: Fleiß (C-Hw)")
            c_hw_1 = st.slider("Wenn sich die Person zu etwas verpflichtet, führt sie es immer zu Ende aus.", 1, 5, 3, key="x42i05")
            c_hw_2 = st.slider("Die Person schätzt sich selbst als sehr ausdauernde Arbeiterin ein.", 1, 5, 3, key="x42i30")
            c_hw_3 = st.slider("Wenn die Person etwas anfängt, arbeitet sie, bis es zu ihrer Zufriedenheit beendet ist.", 1, 5, 3, key="x42i44")
            
            st.markdown("### 5. Facette: Organisation (C-O)")
            c_o_1 = st.slider("Die Person hält ihre persönlichen Sachen gerne ordentlich und organisiert.", 1, 5, 3, key="x42i18")
            c_o_2 = st.slider("Die Person versucht einen Plan für Aufgaben zu entwickeln und hält sich daran.", 1, 5, 3, key="x42i49")
            c_o_3 = st.slider("Die Person versucht vollständig vorbereitet zu sein, bevor sie eine Aufgabe anpackt.", 1, 5, 3, key="x42i39")
            
            st.write("---")

            # ==========================================
            # 📢 DIMENSION EXTRAVERSION (E)
            # ==========================================
            st.markdown("## 📢 Dimension Extraversion (E)")
            
            st.markdown("### 6. Facette: Durchsetzungsfähigkeit (E-A)")
            e_a_1 = st.slider("Die Person spricht lauter, wenn sie meint, einen Beitrag liefern zu können.", 1, 5, 3, key="x42i42")
            e_a_2 = st.slider("Die Person neigt dazu, in Gruppen die Führung zu übernehmen.", 1, 5, 3, key="x42i35")
            e_a_3 = st.slider("Die Person hat eine Menge Einfluss auf andere Leute.", 1, 5, 3, key="x42i03")
            
            st.markdown("### 7. Facette: Selbstbewusstsein (E-SB)")
            e_sb_1 = st.slider("Die Person ist eine sehr schüchterne Person. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i23")
            e_sb_2 = st.slider("Die Freunde der Person halten sie für schüchtern. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i10")
            e_sb_3 = st.slider("Die Person fühlt sich nicht wohl, wenn sie im Zentrum der Aufmerksamkeit steht. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i22")
            
            st.markdown("### 8. Facette: Soziale Aktivität (E-So)")
            e_so_1 = st.slider("Die Person ist gerne wo viel los ist.", 1, 5, 3, key="x42i40")
            e_so_2 = st.slider("Die Person gibt sich große Mühe Leute kennenzulernen.", 1, 5, 3, key="x42i32")
            e_so_3 = st.slider("Die Person mag Partys auf denen viele Leute sind.", 1, 5, 3, key="x42i20")
            
            st.write("---")

            # ==========================================
            # 🛡️ DIMENSION NEUROTIZISMUS (N)
            # ==========================================
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
            
            st.write("---")

            # ==========================================
            # 💡 DIMENSION OFFENHEIT (O)
            # ==========================================
            st.markdown("## 💡 Dimension Offenheit (O)")
            
            st.markdown("### 12. Facette: Intellekt (O-In)")
            o_in_1 = st.slider("Die Person mag es, intellektuelle Diskussionen mit Freunden zu führen.", 1, 5, 3, key="x42i38")
            o_in_2 = st.slider("Die Person findet intellektuelle Themen interessanter als Sport (z.B. Fußball, Tennis).", 1, 5, 3, key="x42i28")
            o_in_3 = st.slider("Die Person besitzt ein hohes Maß an intellektueller Neugier.", 1, 5, 3, key="x42i33")
            
            st.markdown("### 13. Facette: Reflexion (O-R)")
            o_r_1 = st.slider("Die Person verbringt viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.", 1, 5, 3, key="x42i21")
            o_r_2 = st.slider("Die Person verbringt viel Zeit damit, ihre Gefühlswelt zu erkunden.", 1, 5, 3, key="x42i50")
            o_r_3 = st.slider("Die Person liest gerne Gedichte.", 1, 5, 3, key="x42i41")
            
            st.markdown("### 14. Facette: Wissenschaftliches Interesse (O-Sc)")
            o_sc_1 = st.slider("Die Person hat sich viele Gedanken über den Ursprung des Universums gemacht.", 1, 5, 3, key="x42i01")
            o_sc_2 = st.slider("Die Person denkt oft über die Wunder der Natur nach.", 1, 5, 3, key="x42i16")
            o_sc_3 = st.slider("Die Evolutionstheorie fasziniert die Person.", 1, 5, 3, key="x42i25")
            
            st.write("---")

            # ==========================================
            # 💎 DIMENSION EHRLICHKEIT-BESCHEIDENHEIT (HH)
            # ==========================================
            st.markdown("## 💎 Dimension Ehrlichkeit-Bescheidenheit (HH)")
            
            st.markdown("### 15. Facette: Aufrichtigkeit (HH-Si)")
            hh_si_1 = st.slider("Wenn die Person von jemandem, den sie nicht mag, etwas will, verhält sie sich sehr nett. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i47")
            hh_si_2 = st.slider("Die Person würde keine Schmeicheleien nutzen, um eine Gehaltserhöhung zu bekommen.", 1, 5, 3, key="x42i15")
            hh_si_3 = st.slider("Wenn die Person von jemandem etwas will, lache sie auch über dessen schlechteste Witze. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i04")
            
            st.markdown("### 16. Fairness (HH-Fa)")
            hh_fa_1 = st.slider("Die Person würde in Versuchung geraten, Diebesgut zu kaufen, wenn sie knapp bei Kasse wäre. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i31")
            hh_fa_2 = st.slider("Die Person würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.", 1, 5, 3, key="x42i17")
            hh_fa_3 = st.slider("Wenn die Person wüsste, dass sie niemals erwischt wird, wäre sie bereit, eine Million zu stehlen. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i08")
            
            st.markdown("### 17. Bescheidenheit (HH-Mo)")
            hh_mo_1 = st.slider("Die Person will, dass alle wissen, dass sie eine wichtige angesehene Person ist. *(Achtung: Invertiert)*", 1, 5, 3, key="x42i24")
            hh_mo_2 = st.slider("Die Person ist eine ganz normale Person, die nicht besser ist als andere.", 1, 5, 3, key="x42i34")
            hh_mo_3 = st.slider("Die Person will nicht, dass andere Leute sie behandeln, als ob sie ihnen überlegen sei.", 1, 5, 3, key="x42i51")
            
            st.write("")
            anmerkungen = st.text_area("Gibt es noch sonstige Auffälligkeiten oder Bemerkungen zur Person? (Optional)", max_chars=500)
            
            submit_button = st.form_submit_button("Formular absenden", type="primary")
                 
            if submit_button:
                with st.spinner("Ihre Antworten werden sicher übertragen..."):
                    
                    # 1. Invertierte Items umpolen
                    e_sb_rec = ( (6 - e_sb_1) + (6 - e_sb_2) + (6 - e_sb_3) ) / 3
                    hh_si_rec = ( (6 - hh_si_1) + hh_si_2 + (6 - hh_si_3) ) / 3
                    hh_fa_rec = ( (6 - hh_fa_1) + hh_fa_2 + (6 - hh_fa_3) ) / 3
                    hh_mo_rec = ( (6 - hh_mo_1) + hh_mo_2 + hh_mo_3 ) / 3
                    
                    # Normal laufende Facetten aggregieren
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
                    
                    # 2. Globale Dimensionen berechnen
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
                    
                    # 3. CSV-Datenstruktur zusammenstellen
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Rater_VP_Code": st.session_state.participant_id,      
                        "Rater_Matrikelnummer": st.session_state.matrikelnummer, 
                        "Rater_Alter": st.session_state.alter,
                        "Rater_Geschlecht": st.session_state.geschlecht,
                        "Forschungs_Consent": 1 if st.session_state.consent_given else 0,
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_Target_VP_Code": st.session_state.vp_code, 
                        
                        # Rohdaten der Items
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
                        
                        # Aggregierte Globale Werte
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
                    
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_target_name = "".join(x for x in st.session_state.vp_code if x.isalnum() or x in "._-").strip()
                    clean_rater_name = "".join(x for x in st.session_state.participant_id if x.isalnum() or x in "._-").strip()
                    dateiname = f"ergebnis_Rater_{clean_rater_name}_Target_{clean_target_name}_{timestamp_str}.csv"
                    
                    try:
                        upload_results_to_nextcloud(dateiname, csv_string)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Fehler beim Speichern: {e}")

    # Feedback-Bildschirm
    else:
        st.balloons()
        st.subheader("🎉 Vielen Dank für Ihre Teilnahme!")
        st.write("Ihre Antworten wurden erfolgreich registriert.")
        
        st.write("---")
        st.subheader("🤖 Ihr Urteil im Vergleich zur KI-Bewertung")
        st.write("Hier sehen Sie Ihre berechneten Dimensionen im Vergleich zu den globalen KI-Werten:")
        
        vergleichs_daten = []
        gesamte_abweichung = 0
        
        for dimension in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
            user_val = st.session_state.user_scores.get(dimension, 3)
            ai_val = st.session_state.ai_scores.get(dimension, 3)
            diff = round(abs(user_val - ai_val), 2)
            gesamte_abweichung += diff
            
            if diff <= 0.5:
                feedback = "🎯 Nahezu identisch!"
            elif diff <= 1.2:
                feedback = "👍 Sehr nah dran"
            else:
                feedback = "🔄 Andere Wahrnehmung"
                
            vergleichs_daten.append({
                "Big-Five Dimension": dimension,
                "Ihre Einschätzung (Mittelwert)": user_val,
                "KI-Einschätzung": ai_val,
                "Abweichung": diff,
                "Feedback": feedback
            })
            
        df_vergleich = pd.DataFrame(vergleichs_daten)
        st.table(df_vergleich)
        
        gesamte_abweichung = round(gesamte_abweichung, 2)
        st.write("")
        if gesamte_abweichung <= 2.5:
            st.info(f"🧠 **Fazit:** Starke Übereinstimmung! Ihre berechneten Skalenwerte spiegeln das KI-Profil bemerkenswert präzise wider (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        elif gesamte_abweichung <= 5.0:
            st.info(f"📊 **Fazit:** Solide Annäherung. Sie haben die Tendenzen der Person im Kern ähnlich bewertet wie die KI (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        else:
            st.info(f"👥 **Fazit:** Spannende Nuancen! Ihre menschliche Fremdbeurteilung weicht punktuell von den mathematischen KI-Scores ab (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")

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
            st.rerun()

# ==========================================
# 🛠️ ADMIN-BEREICH (IM HINTERGRUND / SIDEBAR)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Admin-Bereich")

admin_password = st.sidebar.text_input("Sicherheitspasswort eingeben", type="password")
ADMIN_PASSWORT_PROV = "DeinSicheresPasswort2026" 

if admin_password == ADMIN_PASSWORT_PROV:
    st.sidebar.success("🔑 Admin-Modus aktiv!")
    
    st.write("---")
    st.header("🛠️ Forschungs-Dashboard (Admin-Ansicht)")
    
    # 1. Metriken live abfragen
    alle_dateien = load_transcript_list()
    bereits_vergeben = load_already_assigned_transcripts()
    verbleibend_in_urne, _ = calculate_available_urn()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gesamtanzahl Nextcloud", len(alle_dateien))
    with col2:
        st.metric("Noch frei (in aktueller Runde)", len(verbleibend_in_urne))
    with col3:
        st.metric("Bereits zugeteilt (Historie)", len(bereits_vergeben))
        
    aktuell_gezogen = st.session_state.aktuelles_transkript_file
    if aktuell_gezogen:
        st.info(f"👀 **Aktuell in Bearbeitung:** `{aktuell_gezogen}` (Rater: `{st.session_state.participant_id}`)")

    # 2. Detailtabellen anzeigen
    tab1, tab2 = st.tabs(["📋 Freie Transkripte", "✅ Bereits vergeben (Historie)"])
    
    with tab1:
        st.subheader("Verfügbare Dateien im aktuellen Pool")
        if verbleibend_in_urne:
            df_frei = pd.DataFrame(verbleibend_in_urne, columns=["Dateiname (Noch im Topf)"])
            st.dataframe(df_frei, use_container_width=True)
        else:
            st.warning("Die Urne ist komplett leer! Beim nächsten Klick startet automatisch eine neue Runde.")
            
    with tab2:
        st.subheader("Ausgelesene Zuweisungen aus Nextcloud-Ergebnissen")
        if bereits_vergeben:
            df_gezogen = pd.DataFrame(list(bereits_vergeben), columns=["Dateiname (Bereits bewertet)"])
            st.dataframe(df_gezogen, use_container_width=True)
        else:
            st.info("Bisher wurden laut Nextcloud-Ergebnisordner noch keine Transkripte final bewertet.")

elif admin_password:
    st.sidebar.error("❌ Falsches Passwort.")
