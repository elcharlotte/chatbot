import streamlit as st
from openai import OpenAI
import json
import requests
import uuid
import threading
import io  
from streamlit_mic_recorder import mic_recorder  

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
        st.session_state.default_id = params.get("caseNumber", f"user_{uuid.uuid4().hex[:8]}")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.interaction_count = 0
        st.session_state.condition = "speech_open"
        st.session_state.mic_test_passed = False

    client = OpenAI(api_key=st.secrets["openai"]["api_key"])

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
        * **Wo werden die Daten gespeichert?** Ihre Daten werden verschlüsselt auf den sicheren Servern der Universität Ulm (**Nextcloud/Cloudstore**) abgelegt.
        * **Wo werden sie NICHT gespeichert?** Es werden keine personenbezogenen Daten auf externen kommerziellen Servern dauerhaft gespeichert.
        * **Anonymisierung**: Die Speicherung erfolgt ausschließlich unter der angegebenen Teilnehmer-ID.
        """)
        
        st.divider()
        
        consent_checked = st.checkbox(
            "Ich habe die Informationen gelesen und stimme der anonymisierten Nutzung und Speicherung meiner Chatdaten zu Forschungszwecken zu."
        )
        
        if st.button("Weiter zum Mikrofon-Test"):
            if consent_checked:
                st.session_state.research_consent = True
                st.session_state.step = "mic_test"
                st.rerun()
            else:
                st.warning("Bitte bestätigen Sie die Einwilligungserklärung, um fortzufahren.")

    # --- NEU - PHASE 2.5: MIKROFON TEST ---
    elif st.session_state.step == "mic_test":
        st.title("🎙️ Mikrofon-Test")
        st.write("Bitte testen Sie Ihr Mikrofon, bevor das Interview startet. Sprechen Sie nach dem Starten der Aufnahme ein paar Worte (z. B. 'Hallo, Test').")
        
        test_recorder = mic_recorder(
            start_prompt="Test-Aufnahme starten",
            stop_prompt="Test-Aufnahme stoppen",
            key="mic_test_recorder"
        )
        
        if test_recorder:
            audio_bytes = test_recorder['bytes']
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "test.wav"
            
            with st.spinner("Prüfe Audio-Eingang..."):
                try:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                    if transcript.text.strip():
                        st.session_state.mic_test_transcript = transcript.text
                        st.session_state.mic_test_passed = True
                    else:
                        st.session_state.mic_test_transcript = "Es wurde kein Text erkannt. Bitte lauter sprechen oder das richtige Eingabegerät in den Browsereinstellungen wählen."
                        st.session_state.mic_test_passed = False
                except Exception as e:
                    st.error(f"Fehler beim Mikrofon-Test: {e}")
        
        # Visuelle Rückmeldung für die Person
        if "mic_test_transcript" in st.session_state:
            st.info(f"**Erkanntes Audio:** „{st.session_state.mic_test_transcript}“")
            
            if st.session_state.mic_test_passed:
                st.success("✅ Mikrofon funktioniert erfolgreich! Sie können das Interview jetzt starten.")
                if st.button("Interview jetzt starten"):
                    st.session_state.step = "chat"
                    st.session_state.messages = [
                        {"role": "system", "content": "Du bist ein psychologischer Interviewer. Analysiere die Big Five. Sei empathisch aber zielgerichtet. Formuliere kurze Sätze. Nach 10 Interaktionen beende das Gespräch höflich."},
                        {"role": "assistant", "content": f"Vielen Dank! Die ID {st.session_state.participant_id} ist registriert und das Mikrofon wurde erfolgreich getestet. Wir beginnen nun mit dem Interview. Erzählen Sie doch mal: Was haben Sie gestern so gemacht?"}
                    ]
                    st.rerun()
            else:
                st.error("❌ Audio-Signal zu schwach oder fehlerhaft. Bitte versuchen Sie es erneut.")

    # --- PHASE 3: CHAT (AUDIO-EINGABE & TEXT-AUSGABE) ---
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
            user_input = None

            st.write("---")
            st.write("🎤 **Antwort einsprechen:**")
            
            recorder_key = f"recorder_{st.session_state.interaction_count}"
            
            audio_record = mic_recorder(
                start_prompt="Aufnahme starten",
                stop_prompt="Aufnahme stoppen",
                key=recorder_key
            )
            
            if audio_record:
                audio_bytes = audio_record['bytes']
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "audio.wav"
                
                with st.spinner("🎧 Ich höre zu... (Sprache wird verarbeitet)"):
                    try:
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1", 
                            file=audio_file
                        )
                        user_input = transcript.text
                    except Exception as e:
                        st.error(f"Spracherkennungs-Fehler: {e}")

            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                
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
                
                if recorder_key in st.session_state:
                    del st.session_state[recorder_key]
                st.rerun()

    # --- PHASE 4: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")
        
        if "data_saved" not in st.session_state:
            st.session_state.data_saved = False

        if "ai_bfi" not in st.session_state:
            with st.spinner("KI Analyse läuft..."):
                try:
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
