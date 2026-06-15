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
    
    * **Ihre Aufgabe:** Lesen Sie das Transkript aufmerksam durch. Schätzen Sie die interviewte Person im Anschluss auf den 17 TSDI-Persönlichkeitsfacetten ein.
    * **Verpflichtung:** Diese Fremdbeurteilung ist der zweite Teil der wöchentlichen Übungsleistung.
    """)
    
    consent_checked = st.checkbox("Ich habe die oben genannten Informationen gelesen und stimme der Nutzung zu.")
    
    if st.button("Studie starten & Transkript zulosen", type="primary"):
        if consent_checked:
            st.session_state.step = "evaluation"
            st.rerun()
        else:
            st.warning("Bitte stimmen Sie den Datenschutzbestimmungen zu, um fortzufahren.")


# --- PHASE 3: EVALUATION (LOSEN, LESEN & FRAGEBOGEN) ---
elif st.session_state.step == "evaluation":
    
    if st.session_state.aktuelles_transkript_file is None:
        st.subheader("Schritt 1: Transkript erhalten")
        st.write("Klicken Sie auf den Button, um ein zufälliges Interview-Transkript aus dem System zugelost zu bekommen.")
        
        if not st.session_state.urne:
            st.warning("Keine Transkripte im Nextcloud-Ordner gefunden oder Urne leer.")
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

    elif not st.session_state.user_scores:
        st.success("Ihnen wurde erfolgreich ein Interview-Transkript zugelost!")
        
        st.subheader("Schritt 2: Transkript lesen")
        
        # Kontrastreicher HTML-Scroll-Container für das Transkript
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
        st.write("Bitte schätzen Sie die Person im Interview auf den 17 Facetten ein (1 = trifft gar nicht zu, 5 = trifft vollkommen zu). Falls Sie zu einer Aussage keine Aussage treffen können, fällen Sie ihr Urteil anhand der gegeben Informationen:")
        
        with st.form("fragebogen_form"):
            
            # ==========================================
            # 🤝 DIMENSION VERTRÄGLICHKEIT (A)
            # ==========================================
            st.markdown("### 🤝 Dimension Verträglichkeit (A)")
            
            st.markdown("**Facette: Freundlichkeit (A-Fr)**")
            st.caption("* *Die Person gilt als jemand, mit dem man einfach gut auskommt.* \n"
                       "* *Die Person kommt mit den meisten Menschen gut zurecht.* \n"
                       "* *Die Person versucht auch fröhlich zu sein, wenn es nicht so gut läuft.* ")
            a_fr = st.slider("Deine Einschätzung zu **Freundlichkeit**:", 1, 5, 3, key="s_a_fr")
            
            st.markdown("**Facette: Rücksichtnahme (A-Co)**")
            st.caption("* *Die Person behandelt andere Leute immer freundlich.* \n"
                       "* *Die Person versucht zu jedem freundlich zu sein, den sie kennt.* \n"
                       "* *Die Person versucht immer höflich zu sein, auch zu denen, die ihr gegenüber unfreundlich sind.* ")
            a_co = st.slider("Deine Einschätzung zu **Rücksichtnahme**:", 1, 5, 3, key="s_a_co")
            
            st.markdown("**Facette: Hilfsbereitschaft (A-H)**")
            st.caption("* *Es ist der Person eine Freude, anderen mit ihren Problemen zu helfen.* \n"
                       "* *Die Person hilft anderen Leuten gerne, auch wenn nichts für sie dabei herausspringt.* \n"
                       "* *Die Person ist immer großzügig, wenn es darum geht, anderen zu helfen.* ")
            a_h = st.slider("Deine Einschätzung zu **Hilfsbereitschaft**:", 1, 5, 3, key="s_a_h")
            
            st.write("---")

            # ==========================================
            # 🎯 DIMENSION GEWISSENHAFTIGKEIT (C)
            # ==========================================
            st.markdown("### 🎯 Dimension Gewissenhaftigkeit (C)")
            
            st.markdown("**Facette: Fleiß (C-Hw)**")
            st.caption("* *Wenn sich die Person zu etwas verpflichtet, führt sie es immer zu Ende aus.* \n"
                       "* *Die Person schätzt sich selbst als sehr ausdauernde Arbeiterin ein.* \n"
                       "* *Wenn die Person etwas anfängt, arbeitet sie, bis es zu ihrer Zufriedenheit beendet ist.* ")
            c_hw = st.slider("Deine Einschätzung zu **Fleiß**:", 1, 5, 3, key="s_c_hw")
            
            st.markdown("**Facette: Organisation (C-O)**")
            st.caption("* *Die Person hält ihre persönlichen Sachen gerne ordentlich und organisiert.* \n"
                       "* *Die Person versucht einen Plan für Aufgaben zu entwickeln und hält sich daran.* \n"
                       "* *Die Person versucht vollständig vorbereitet zu sein, bevor sie eine Aufgabe anpacke.* ")
            c_o = st.slider("Deine Einschätzung zu **Organisation**:", 1, 5, 3, key="s_c_o")
            
            st.write("---")

            # ==========================================
            # 📢 DIMENSION EXTRAVERSION (E)
            # ==========================================
            st.markdown("### 📢 Dimension Extraversion (E)")
            
            st.markdown("**Facette: Durchsetzungsfähigkeit (E-A)**")
            st.caption("* *Die Person spricht lauter, wenn sie meint, einen Beitrag liefern zu können.* \n"
                       "* *Die Person neigt dazu, in Gruppen die Führung zu übernehmen.* \n"
                       "* *Die Person hat eine Menge Einfluss auf andere Leute.* ")
            e_a = st.slider("Deine Einschätzung zu **Durchsetzungsfähigkeit**:", 1, 5, 3, key="s_e_a")
            
            st.markdown("**Facette: Selbstbewusstsein (E-SB)**")
            st.caption("* *Die Person ist eine sehr schüchterne Person.* \n"
                       "* *Die Freunde der Person halten sie für schüchtern.* \n"
                       "* *Die Person fühlt sich nicht wohl, wenn sie im Zentrum der Aufmerksamkeit steht.* ")
            e_sb = st.slider("Deine Einschätzung zu **Selbstbewusstsein**:", 1, 5, 3, key="s_e_sb")
            
            st.markdown("**Facette: Soziale Aktivität (E-So)**")
            st.caption("* *Die Person ist gerne wo viel los ist.* \n"
                       "* *Die Person gibt sich große Mühe Leute kennenzulernen.*\n"
                       "* *Die Person mag Partys auf denen viele Leute sind.* ")
            e_so = st.slider("Deine Einschätzung zu **Soziale Aktivität**:", 1, 5, 3, key="s_e_so")
            
            st.write("---")

            # ==========================================
            # 🛡️ DIMENSION NEUROTIZISMUS (N)
            # ==========================================
            st.markdown("### 🛡️ Dimension Neurotizismus (N)")
            
            st.markdown("**Facette: Depression (N-D)**")
            st.caption("* *Es gibt Zeiten, in denen sich die Person selbst bedauert.* \n"
                       "* *Manchmal ist die Person entmutigt und möchte am liebsten aufgeben.* \n"
                       "* *Die Person fürchtet oft, dass sie ihre Ziele nicht erreichen könnte.* ")
            n_d = st.slider("Deine Einschätzung zu **Depression**:", 1, 5, 3, key="s_n_d")
            
            st.markdown("**Facette: Reizbarkeit (N-Ir)**")
            st.caption("* *Manchmal regt sich die Person so auf, dass es ihr auf den Magen schlägt.* \n"
                       "* *Wenn die Person aufgebracht ist, kann sie nicht mehr klar denken.* \n"
                       "* *Die Person kann Kritik nicht sehr gut akzeptieren.* ")
            n_ir = st.slider("Deine Einschätzung zu **Reizbarkeit**:", 1, 5, 3, key="s_n_ir")
            
            st.markdown("**Facette: Nervosität (N-St)**")
            st.caption("* *Die Person fühlt sich oft müde und erschöpft.* \n"
                       "* *Wenn die Person unter großem Stress steht, ist sie oft kurz davor zusammenzubebraten.* \n"
                       "* *Die Person ist oft zittrig und angespannt.* ")
            n_st = st.slider("Deine Einschätzung zu **Nervosität**:", 1, 5, 3, key="s_n_st")
            
            st.write("---")

            # ==========================================
            # 💡 DIMENSION OFFENHEIT (O)
            # ==========================================
            st.markdown("### 💡 Dimension Offenheit (O)")
            
            st.markdown("**Facette: Intellekt (O-In)**")
            st.caption("* *Die Person mag es, intellektuelle Diskussionen mit Freunden zu führen.* \n"
                       "* *Die Person findet intellektuelle Themen interessanter als Sport (z.B. Fußball, Tennis).* \n"
                       "* *Die Person besitzt ein hohes Maß an intellektueller Neugier.* ")
            o_in = st.slider("Deine Einschätzung zu **Intellekt**:", 1, 5, 3, key="s_o_in")
            
            st.markdown("**Facette: Reflexion (O-R)**")
            st.caption("* *Die Person verbringt viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.* \n"
                       "* *Die Person verbringt viel Zeit damit, ihre Gefühlswelt zu erkunden.* \n"
                       "* *Die Person liest gerne Gedichte.* ")
            o_r = st.slider("Deine Einschätzung zu **Reflexion**:", 1, 5, 3, key="s_o_r")
            
            st.markdown("**Facette: Wissenschaftliches Interesse (O-Sc)**")
            st.caption("* *Die Person hat sich viele Gedanken über den Ursprung des Universums gemacht.*\n"
                       "* *Die Person denkt oft über die Wunder der Natur nach.* \n"
                       "* *Die Evolutionstheorie fasziniert die Person.*")
            o_sc = st.slider("Deine Einschätzung zu **Wissenschaftliches Interesse**:", 1, 5, 3, key="s_o_sc")
            
            st.write("---")

            # ==========================================
            # 💎 DIMENSION EHRLICHKEIT-BESCHEIDENHEIT (HH)
            # ==========================================
            st.markdown("### 💎 Dimension Ehrlichkeit-Bescheidenheit (HH)")
            
            st.markdown("**Facette: Aufrichtigkeit (HH-Si)**")
            st.caption("* *Wenn die Person von jemandem, den sie nicht mag, etwas will, verhält sie sich sehr nett.* \n"
                       "* *Die Person würde keine Schmeicheleien nutzen, um eine Gehaltserhöhung zu bekommen.* \n"
                       "* *Wenn die Person von jemandem etwas will, lacht sie auch über dessen schlechteste Witze.* ")
            hh_si = st.slider("Deine Einschätzung zu **Aufrichtigkeit**:", 1, 5, 3, key="s_hh_si")
            
            st.markdown("**Facette: Fairness (HH-Fa)**")
            st.caption("* *Die Person würde in Versuchung geraten, Diebesgut zu kaufen, wenn sie knapp bei Kasse wäre.*\n"
                       "* *Die Person würde niemals Bestechungsgeld annehmen, auch wenn es sehr viel wäre.*\n"
                       "* *Wenn die Person wüsste, dass sie niemals erwischt wird, wäre sie bereit, eine Million zu stehlen.*")
            hh_fa = st.slider("Deine Einschätzung zu **Fairness**:", 1, 5, 3, key="s_hh_fa")
            
            st.markdown("**Facette: Bescheidenheit (HH-Mo)**")
            st.caption("* *Die Person will, dass alle wissen, dass sie eine wichtige angesehene Person ist.*\n"
                       "* *Die Person ist eine ganz normale Person, die nicht besser ist als andere.*\n"
                       "* *Die Person will nicht, dass andere Leute sie behandeln, als ob sie ihnen überlegen sei.*")
            hh_mo = st.slider("Deine Einschätzung zu **Bescheidenheit**:", 1, 5, 3, key="s_hh_mo")
            
            st.write("")
            anmerkungen = st.text_area("Gibt es noch sonstige Auffälligkeiten oder Bemerkungen zur Person? (Optional)", max_chars=500)
            
            submit_button = st.form_submit_button("Formular absenden", type="primary")
                 
            if submit_button:
                with st.spinner("Ihre Antworten werden sicher übertragen..."):
                    
                    # 1. Globale Dimensionen für das Feedback aggregieren (Mittelwerte der Facetten)
                    user_extraversion = (e_a + e_sb + e_so) / 3
                    user_vertraeglichkeit = (a_fr + a_co + a_h) / 3
                    user_gewissenhaftigkeit = (c_hw + c_o) / 3
                    user_neurotizismus = (n_d + n_ir + n_st) / 3
                    user_offenheit = (o_in + o_r + o_sc) / 3
                    
                    st.session_state.user_scores = {
                        "Extraversion": round(user_extraversion, 2),
                        "Verträglichkeit": round(user_vertraeglichkeit, 2),
                        "Gewissenhaftigkeit": round(user_gewissenhaftigkeit, 2),
                        "Neurotizismus": round(user_neurotizismus, 2),
                        "Offenheit": round(user_offenheit, 2)
                    }
                    
                    # 2. Daten für die CSV strukturieren (Alle 17 Facetten einzeln erfassen!)
                    ergebnis_daten = {
                        "Zeitstempel": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Rater_VP_Code": st.session_state.participant_id,      
                        "Rater_Matrikelnummer": st.session_state.matrikelnummer, 
                        "Zugeordneter_Transkript_File": st.session_state.aktuelles_transkript_file,
                        "Bewerteter_Target_VP_Code": st.session_state.vp_code, 
                        
                        # Einzelfacetten des Raters
                        "FACETTE_A_Fr": a_fr, "FACETTE_A_Co": a_co, "FACETTE_A_H": a_h,
                        "FACETTE_C_Hw": c_hw, "FACETTE_C_O": c_o,
                        "FACETTE_E_A": e_a, "FACETTE_E_SB": e_sb, "FACETTE_E_So": e_so,
                        "FACETTE_N_D": n_d, "FACETTE_N_Ir": n_ir, "FACETTE_N_St": n_st,
                        "FACETTE_O_In": o_in, "FACETTE_O_R": o_r, "FACETTE_O_Sc": o_sc,
                        "FACETTE_HH_Si": hh_si, "FACETTE_HH_Fa": hh_fa, "FACETTE_HH_Mo": hh_mo,
                        
                        # Globale berechnete Dimensionen des Raters
                        "USER_Extraversion": st.session_state.user_scores["Extraversion"],
                        "USER_Vertraeglichkeit": st.session_state.user_scores["Verträglichkeit"],
                        "USER_Gewissenhaftigkeit": st.session_state.user_scores["Gewissenhaftigkeit"],
                        "USER_Neurotizismus": st.session_state.user_scores["Neurotizismus"],
                        "USER_Offenheit": st.session_state.user_scores["Offenheit"],
                        
                        # Zum direkten Vergleich: Globale KI-Werte aus der JSON
                        "AI_Extraversion": st.secrets.get(f"ai_assessment", {}).get("Extraversion", st.session_state.ai_scores.get("Extraversion")),
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

    # Unterphase C: Abgesendet -> Feedback-Bildschirm anzeigen
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
                "Deine Einschätzung (Mittelwert)": user_val,
                "KI-Einschätzung": ai_val,
                "Abweichung": diff,
                "Feedback": feedback
            })
            
        df_vergleich = pd.DataFrame(vergleichs_daten)
        st.table(df_vergleich)
        
        # Fazit berechnen
        gesamte_abweichung = round(gesamte_abweichung, 2)
        st.write("")
        if gesamte_abweichung <= 2.5:
            st.info(f"🧠 **Fazit:** Starke Übereinstimmung! Deine berechneten Skalenwerte spiegeln das KI-Profil bemerkenswert präzise wider (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        elif gesamte_abweichung <= 5.0:
            st.info(f"📊 **Fazit:** Solide Annäherung. Du hast die Tendenzen der Person im Kern ähnlich bewertet wie die KI (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")
        else:
            st.info(f"👥 **Fazit:** Spannende Nuancen! Deine menschliche Fremdbeurteilung weicht punktuell von den mathematischen KI-Scores ab (Gesamtabweichung: **{gesamte_abweichung}** Punkte).")

        st.write("---")
        
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
