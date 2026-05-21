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
                    {"role": "system", "content": "Du bist ein psychologischer Interviewer. Analysiere die Big Five. Sei empathisch aber zielgerichtet. Formuliere kurze Sätze. Nach 10 Interaktionen beende das Gespräch höflich."},
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
