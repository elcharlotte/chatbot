import streamlit as st
from openai import OpenAI
import json
import requests
import uuid

# --- KONFIGURATION & HELPER ---
def save_to_nextcloud(participant_id, data_dict):
    try:
        # Pfad zu deinem Nextcloud-Ordner
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
    """Löscht den Session State und startet die App neu."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- UI KOMPONENTEN ---
def main():
    st.set_page_config(page_title="Persönlichkeits-Diagnostik", page_icon="🧠")
    
    # Initialisierung des Session State
    if "participant_id" not in st.session_state:
        params = st.query_params
        st.session_state.participant_id = params.get("caseNumber", f"user_{uuid.uuid4().hex[:8]}")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.bfi_self = {}
        st.session_state.interaction_count = 0

    # --- PHASE 1: WILLKOMMEN ---
    if st.session_state.step == "welcome":
        st.title("Willkommen zum Interview 🤖")
        st.write("Bitte geben Sie zunächst ein paar Basisdaten an.")
        
        col1, col2 = st.columns(2)
        with col1:
            age = st.number_input("Alter", min_value=14, max_value=100, value=25)
        with col2:
            gender = st.selectbox("Geschlecht", ["weiblich", "männlich", "divers", "keine Angabe"])
        
        if st.button("Weiter zum Fragebogen"):
            st.session_state.user_data = {"age": age, "gender": gender}
            st.session_state.step = "questionnaire"
            st.rerun()

    # --- PHASE 2: BFI-10 FRAGEBOGEN ---
    elif st.session_state.step == "questionnaire":
        st.title("Kurzfragebogen 📝")
        st.write("Wie sehr treffen die folgenden Aussagen auf Sie zu? (1 = gar nicht, 5 = voll und ganz)")
        
        items = [
            {"id": 1, "text": "Ich bin eher zurückhaltend, reserviert.", "trait": "Extraversion", "pos": False},
            {"id": 2, "text": "Ich schenke anderen leicht Vertrauen, glaube an das Gute im Menschen.", "trait": "Verträglichkeit", "pos": True},
            {"id": 3, "text": "Ich bin bequem, neige zur Faulheit.", "trait": "Gewissenhaftigkeit", "pos": False},
            {"id": 4, "text": "Ich bin entspannt, lasse mich durch Stress nicht aus der Ruhe bringen.", "trait": "Neurotizismus", "pos": False},
            {"id": 5, "text": "Ich habe nur wenig künstlerisches Interesse.", "trait": "Offenheit", "pos": False},
            {"id": 6, "text": "Ich gehe aus mir heraus, bin gesellig.", "trait": "Extraversion", "pos": True},
            {"id": 7, "text": "Ich neige dazu, andere zu kritisieren.", "trait": "Verträglichkeit", "pos": False},
            {"id": 8, "text": "Ich erledige Aufgaben gründlich.", "trait": "Gewissenhaftigkeit", "pos": True},
            {"id": 9, "text": "Ich werde leicht nervös und unsicher.", "trait": "Neurotizismus", "pos": True},
            {"id": 10, "text": "Ich habe eine aktive Vorstellungskraft, bin fantasievoll.", "trait": "Offenheit", "pos": True},
        ]
        
        raw_responses = {}
        for item in items:
            raw_responses[item["id"]] = st.select_slider(
                f"{item['id']}. {item['text']}",
                options=[1, 2, 3, 4, 5],
                value=3,
                key=f"item_{item['id']}"
            )
        
        if st.button("Interview starten"):
            scores = {}
            for trait in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
                trait_items = [i for i in items if i["trait"] == trait]
                vals = []
                for ti in trait_items:
                    val = raw_responses[ti["id"]]
                    if not ti["pos"]: 
                        val = 6 - val
                    vals.append(val)
                scores[trait] = sum(vals) / len(vals)
            
            st.session_state.bfi_self = scores
            st.session_state.step = "chat"
            st.session_state.messages = [
                {"role": "system", "content": "Du bist ein psychologischer Interviewer. Analysiere die Big Five. Sei empathisch aber zielgerichtet. Formuliere kurze Sätze. Nach 10 Interaktionen beende das Gespräch höflich."},
                {"role": "assistant", "content": "Vielen Dank! Wir beginnen nun mit dem Interview. Erzählen Sie doch mal: Was haben Sie gestern so gemacht?"}
            ]
            st.rerun()

    # --- PHASE 3: CHAT ---
    elif st.session_state.step == "chat":
        st.title("Interview im Dialog 💬")
        user_msgs = [m for m in st.session_state.messages if m["role"] == "user"]
        st.session_state.interaction_count = len(user_msgs)
        st.info(f"Interaktion {st.session_state.interaction_count} von 10")
        
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
            if prompt := st.chat_input("Ihre Antwort..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                
                client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=st.session_state.messages
                )
                msg = response.choices[0].message.content
                st.session_state.messages.append({"role": "assistant", "content": msg})
                
                # Zwischenspeichern nach jeder Nachricht
                full_data = {"info": st.session_state.user_data, "self": st.session_state.bfi_self, "chat": st.session_state.messages}
                save_to_nextcloud(st.session_state.participant_id, full_data)
                st.rerun()

# --- PHASE 4: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")
        
        # Initialisierung des Speicher-Status
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

        # Ergebnisse anzeigen
        traits = ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]
        for t in traits:
            st.subheader(t)
            col1, col2 = st.columns(2)
            ki_wert = st.session_state.ai_bfi.get(t, 0)
            selbst_wert = st.session_state.bfi_self.get(t, 0)
            col1.metric("Selbstbild", round(selbst_wert, 1))
            col2.metric("KI-Bild", ki_wert)
            st.progress(float(ki_wert) / 5.0 if ki_wert else 0.0)

        st.divider()

        # Speichern & Abschlussbereich
        if not st.session_state.data_saved:
            st.subheader("Abschluss")
            consent = st.checkbox("Ich stimme der anonymisierten Datennutzung zu.")
            if st.button("Ergebnisse final speichern & beenden"):
                final_payload = {
                    "info": st.session_state.user_data,
                    "self_assessment": st.session_state.bfi_self,
                    "ai_assessment": st.session_state.ai_bfi,
                    "chat": st.session_state.messages,
                    "research_consent": consent,
                    "id": st.session_state.participant_id
                }
                if save_to_nextcloud(st.session_state.participant_id, final_payload):
                    st.session_state.data_saved = True
                    st.rerun() # Seite neu laden, um den "Speichern"-Button auszublenden
                else:
                    st.error("Speicherfehler.")
        else:
            # Dieser Bereich wird angezeigt, sobald data_saved = True ist
            st.success("Daten erfolgreich gespeichert! Das Fenster kann nun geschlossen oder für die nächste Person vorbereitet werden.")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.link_button("Zur Uni-Webseite", "https://www.uni-ulm.de/in/psy-dia/forschung/an-studien-teilnehmen/")
            with col_b:
                if st.button("🔄 APP RESET (Nächste Person)"):
                    reset_app()

if __name__ == "__main__":
    main()