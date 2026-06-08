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

# --- TSDI LEITFADEN ---
TSDI_LEITFADEN = """
## DIMENSION: VERTRÄGLICHKEIT (A)
Beschreibung: Misst die zwischenmenschliche Orientierung.
### Facette: Kooperation / Vertrauen (A-Co)
* Item tsdi42_02_A_Co080: Ich behandle andere Leute immer freundlich.
* Item tsdi42_21_A_Co207: Ich versuche zu jedem freundlich zu sein, den ich kenne.
* Item tsdi42_22_A_Co209: Ich versuche immer höflich zu sein, auch zu denen, die mir gegenüber unfreundlich sind.
### Facette: Freundlichkeit / Mitgefühl (A-Fr)
* Item tsdi42_24_A_Fr066: Man hält mich für jemanden mit dem man einfach gut auskommt.
* Item tsdi42_12_A_Fr084: Ich komme mit den meisten Menschen gut zurecht.
* Item tsdi42_36_A_Fr220: Ich versuche auch fröhlich zu sein, wenn es nicht so gut läuft.
### Facette: Hilfsbereitschaft (A-H)
* Item tsdi42_10_A_H064: Es ist mir eine Freude, anderen mit ihren Problemen zu helfen.
* Item tsdi42_40_A_H068: Ich helfe anderen Leuten gerne, auch wenn nichts für mich dabei herausspringt.
* Item tsdi42_39_A_H213: Ich bin immer großzügig, wenn es darum geht, anderen zu helfen.

## DIMENSION: GEWISSENHAFTIGKEIT (C)
Beschreibung: Grad an Selbstkontrolle, Genauigkeit, Zielstrebigkeit und Organisation.
### Facette: Pflichtbewusstsein / Fleiß (C-Hw)
* Item tsdi42_04_C_Hw126: Wenn ich mich zu etwas verpflichte, führe ich es immer zu Ende aus.
* Item tsdi42_25_C_Hw137: Ich würde mich selbst als sehr ausdauernden Arbeiter einschätzen.
* Item tsdi42_37_C_Hw167: Wenn ich etwas anfange, arbeite ich, bis es zu meiner Zufriedenheit beendet ist.
### Facette: Ordnung / Besonnenheit (C-O)
* Item tsdi42_14_C_O0153: Ich halte meine persönlichen Sachen gerne ordentlich und organisiert.
* Item tsdi42_41_C_O0157: Ich versuche einen Plan für Aufgaben zu entwickeln und halte mich daran.
* Item tsdi42_32_C_O0162: Ich versuche vollständig vorbereitet zu sein, bevor ich eine Aufgabe anpacke.

## DIMENSION: EXTRAVERSION (E)
Beschreibung: Aktivität und zwischenmenschliches Verhalten.
### Facette: Aktivität / Durchsetzungsvermögen (E-A)
* Item tsdi42_35_E_A002: Ich spreche lauter, wenn ich meine, einen Beitrag liefern zu können.
* Item tsdi42_28_E_A004: Ich neige dazu, in Gruppen die Führung zu übernehmen.
* Item tsdi42_03_E_A009: Ich habe eine menge Einfluss auf andere Leute.
### Facette: Schüchternheit (E-SB)
* Item tsdi42_19_E_SB010: Ich bin eine sehr schüchterne Person.
* Item tsdi42_08_E_SB014: Meine Freunde halten mich für schüchtern.
* Item tsdi42_18_E_SB026: Ich fühle mich nicht wohl, wenn ich im Zentrum der Aufmerksamkeit stehe.
### Facette: Geselligkeit / Herzlichkeit (E-So)
* Item tsdi42_33_E_So007: Ich bin gerne wo viel los ist.
* Item tsdi42_26_E_So012: Ich gebe mir große Mühe Leute kennen zu lernen.
* Item tsdi42_16_E_So028: Ich mag Partys auf denen viele Leute sind.

## DIMENSION: NEUROTIZISMUS (N)
Beschreibung: Emotionale Labilität vs. Stabilität.
### Facette: Depressivität / Dysthymie (N-D)
* Item tsdi42_07_N_D039: Es gibt Zeiten in denen ich mich selbst bedaure.
* Item tsdi42_15_N_D054: Manchmal bin ich entmutigt und möchte am liebsten aufgeben.
* Item tsdi42_30_N_D055: Ich fürchte oft, dass ich meine Ziele nicht erreichen könnte.
### Facette: Reizbarkeit / Irritierbarkeit (N-Ir)
* Item tsdi42_09_N_Ir034: Manchmal rege ich mich so auf, dass es mir auf den Magen schlägt.
* Item tsdi42_05_N_Ir058: Wenn ich aufgebracht bin, kann ich nicht mehr klar denken.
* Item tsdi42_06_N_Ir070: Ich kann Kritik nicht sehr gut akzeptieren.
### Facette: Stressanfälligkeit / Ängstlichkeit (N-St)
* Item tsdi42_29_N_St037: Ich fühle mich oft müde und erschöpft.
* Item tsdi42_38_N_St040: Wenn ich unter großem Stress stehe, bin ich oft kurz davor zusammenzubrechen.
* Item tsdi42_11_N_St043: Ich bin oft zittrig und angespannt.

## DIMENSION: OFFENHEIT FÜR ERFAHRUNGEN (O)
Beschreibung: Intellektuelle Neugier, Vorliebe für Abwechslung und Phantasie.
### Facette: Intellekt / Ideen (O-In)
* Item tsdi42_31_O_In094: Ich mag es, intellektuelle Diskussionen mit Freunden zu führen.
* Item tsdi42_23_O_In106: Ich finde intellektuelle Themen interessanter als Fußball, Tennis oder Basketball.
* Item tsdi47_27_O_In118: Ich besitze ein hohes Maß an intellektueller Neugier.
### Facette: Reflexion / Phantasie (O-R)
* Item tsdi42_17_O_R100: Ich verbringe viel Zeit damit, die Beweggründe des Verhaltens anderer Leute zu erkunden.
* Item tsdi42_42_O_R117: Ich verbringe viel Zeit damit, meine Gefühlswelt zu erkunden.
* Item tsdi42_34_O_R120: Ich lese gerne Gedichte.
### Facette: wissenschaftliches Interesse (O-Sc)
* Item tsdi42_13_O_Sc103: Ich denke oft über die Wunder der Natur nach.
* Item tsdi42_20_O_Sc114: Die Evolutionstheorie fasziniert mich.
* Item tsdi42_01_O_Sc116: Ich habe mir viele Gedanken über den Ursprung des Universums gemacht.
"""

TOTAL_FACETS = 14 

# Das Wort 'JSON' MUSS im Prompt stehen, damit der response_format Modus funktioniert.
SYSTEM_PROMPT = f"""Du bist ein psychologischer Interviewerin. Dein Ziel ist es, ein strukturiertes Interview zu führen, um die 14 Facetten des TSDI systematisch zu erfassen.

DEINE ANTWORT-STRUKTUR:
Du musst deine Antwort zwingend als ein valides JSON-Objekt formatieren. Das JSON-Objekt muss exakt diese zwei Felder enthalten:
1. "aktuelle_facette": Eine Zahl von 0 bis 14. Gibt an, welche Facette die Testperson mit ihrer LETZTEN Antwort gerade beantwortet hat. Wenn du noch ganz am Anfang (beim Einstieg) bist, ist es 0. Wenn die erste Facette (A-Co) erfolgreich besprochen wurde, wechselst du auf 1, u.s.w.
2. "interviewer_text": Deine Frage oder Antwort an den Nutzer.

INTERVIEW-REGELN:
* Gehe die Facetten streng sequenziell von 1 bis 14 durch.
* Stelle pro Beitrag nur EINE verhaltensnahe Frage.
* Formuliere die Fragen natürlich und flüssig, passend zu einem psychologischen Gespräch. Vermeide hölzerne Abfragen, bleibe aber rein diagnostisch (keine Ratschläge oder Therapieversuche).
* Sprich den Nutzer mit 'Sie' an.
* Wenn du die Antwort auf Facette 14 erhalten hast, verabschiede dich höflich und setze an das Ende deines 'interviewer_text' das Label '[INTERVIEW_FERTIG]'.

LEITFADEN:
{TSDI_LEITFADEN}
"""

def main():
    st.set_page_config(page_title="Persönlichkeits-Diagnostik", page_icon="🧠")
    
    if "step" not in st.session_state:
        params = st.query_params
        st.session_state.default_id = params.get("caseNumber", "")
        st.session_state.step = "welcome"
        st.session_state.messages = []
        st.session_state.condition = "structured-write"
        st.session_state.current_facet_count = 0
        st.session_state.research_consent = False

    # --- PHASE 1: WILLKOMMEN ---
    if st.session_state.step == "welcome":
        st.title("Willkommen zum Interview 🤖")
        st.write("Bitte geben Sie Ihre Daten ein, um mit dem Interview zu beginnen.")
        
        st.markdown("""
        **Anleitung zur Generierung Ihres VP-Codes:**
        * *[PLATZHALTER: Bitte hier die spezifische Anweisung zur Code-Generierung einfügen]*
        """)
        
        vp_code_input = st.text_input("VP-Code (Teilnehmer-Code)", value=st.session_state.default_id, placeholder="z.B. AB12XY")
        matrikel_input = st.text_input("Matrikelnummer", placeholder="z.B. 1234567")
        
        if st.button("Weiter zur Studienbeschreibung"):
            if not vp_code_input.strip() or not matrikel_input.strip():
                st.error("Bitte füllen Sie beide Felder aus.")
            else:
                st.session_state.participant_id = vp_code_input.strip()
                st.session_state.matrikelnummer = matrikel_input.strip()
                st.session_state.step = "consent"
                st.rerun()

    # --- PHASE 2: EINWILLIGUNG ---
    elif st.session_state.step == "consent":
        st.title("Informationen zur Studie & Datenschutz 📝")
        st.markdown("""
        ### Beschreibung & Zweck der Studie
        Dieses KI-gestützte Interview dient der Persönlichkeitsdiagnostik. Am Ende erhalten Sie eine Auswertung Ihrer Big Five.
        * **Verpflichtung:** Die Teilnahme ist Teil der Übungsleistung. Wer nicht teilnimmt, erhält keinen Credit.
        * **Ehrlichkeit:** Keine Pflicht zur Wahrheit, aber fiktive Angaben verfälschen die Auswertung.
        * **Ethikvotum:** Bewilligt unter **[PLATZHALTER: Ethikantrag-ID]**.
        
        ### Datenschutz
        * **OpenAI API:** Daten werden verschlüsselt übertragen, nicht zum Training genutzt und nach 30 Tagen gelöscht.
        * **Speicherung:** Daten landen auf der sicheren Nextcloud der Universität Ulm.
        """)
        
        consent_checked = st.checkbox("Ich habe die oben genannten Informationen gelesen und stimme der anonymisierten Nutzung und Speicherung meiner Chatdaten zu Forschungs- und Lehrzwecken zu.")
        if st.button("Interview starten"):
            if consent_checked:
                st.session_state.research_consent = True
                st.session_state.step = "chat"
                
                init_json = json.dumps({
                    "aktuelle_facette": 0,
                    "interviewer_text": "Vielen Dank für Ihre Teilnahme! Lassen Sie uns direkt beginnen. Wie leicht fällt es Ihnen im Alltag, generell immer freundlich und höflich zu anderen Menschen zu sein – selbst wenn diese Ihnen unhöflich begegnen?"
                })
                
                st.session_state.messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "assistant", "content": init_json}
                ]
                st.rerun()
            else:
                st.warning("Bitte stimmen Sie zu.")

    # --- PHASE 3: CHAT ---
    elif st.session_state.step == "chat":
        st.title("Interview im Dialog 💬")
        
        # Fortschritt exakt aus der letzten Assistant-Nachricht auslesen
        if st.session_state.messages:
            last_ai_msg = [m["content"] for m in st.session_state.messages if m["role"] == "assistant"][-1]
            try:
                msg_data = json.loads(last_ai_msg)
                st.session_state.current_facet_count = min(max(0, int(msg_data.get("aktuelle_facette", 0))), TOTAL_FACETS)
            except:
                pass
            
        progress_percentage = float(st.session_state.current_facet_count) / float(TOTAL_FACETS)
        
        st.markdown(f"**Fortschritt der Diagnostik:** Erfasste Facetten: {st.session_state.current_facet_count} von {TOTAL_FACETS}")
        st.progress(progress_percentage)
        st.divider()
        
        interview_ended = False
        for msg in st.session_state.messages:
            if msg["role"] != "system":
                with st.chat_message(msg["role"]):
                    if msg["role"] == "assistant":
                        try:
                            data = json.loads(msg["content"])
                            text_content = data.get("interviewer_text", "")
                            if "[INTERVIEW_FERTIG]" in text_content:
                                interview_ended = True
                            st.markdown(text_content.replace("[INTERVIEW_FERTIG]", "").strip())
                        except:
                            st.markdown(msg["content"])
                    else:
                        st.markdown(msg["content"])

        if interview_ended:
            st.success("Das Interview wurde erfolgreich beendet.")
            if st.button("Zur Auswertung"):
                st.session_state.step = "results"
                st.rerun()
        else:
            client = OpenAI(api_key=st.secrets["openai"]["api_key"])
            user_input = st.chat_input("Ihre Antwort hier tippen...")

            if user_input:
                st.session_state.messages.append({"role": "user", "content": user_input})
                api_success = False
                
                with st.spinner("🤖 Interviewer überlegt..."):
                    try:
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=st.session_state.messages,
                            response_format={"type": "json_object"}
                        )
                        ai_msg = response.choices[0].message.content
                        st.session_state.messages.append({"role": "assistant", "content": ai_msg})
                        api_success = True
                    except Exception as e:
                        st.error(f"KI Fehler: {e}")
                
                # Cloud-Speicherung nur triggern, wenn API erfolgreich war
                if api_success:
                    full_data = {
                        "participant_id": st.session_state.get("participant_id", "unknown"),
                        "matrikelnummer": st.session_state.get("matrikelnummer", "unknown"),
                        "condition": st.session_state.condition,
                        "research_consent": st.session_state.research_consent,
                        "chat": st.session_state.messages
                    }
                    threading.Thread(target=save_to_nextcloud, args=(st.session_state.participant_id, full_data), daemon=True).start()
                st.rerun()

    # --- PHASE 4: AUSWERTUNG ---
    elif st.session_state.step == "results":
        st.title("Ihre Auswertung 📊")
        if "data_saved" not in st.session_state: st.session_state.data_saved = False

        if "ai_bfi" not in st.session_state:
            with st.spinner("KI Analyse läuft..."):
                try:
                    client = OpenAI(api_key=st.secrets["openai"]["api_key"])
                    
                    clean_messages = []
                    for m in st.session_state.messages:
                        if m["role"] == "system": continue
                        if m["role"] == "assistant":
                            try:
                                clean_messages.append(f"Interviewer: {json.loads(m['content']).get('interviewer_text', '')}")
                            except:
                                clean_messages.append(f"Interviewer: {m['content']}")
                        else:
                            clean_messages.append(f"Teilnehmer: {m['content']}")
                            
                    chat_text = "\n".join(clean_messages)
                    
                    res = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "Analysiere den Chat auf Big Five (1-5). Antworte NUR im JSON-Format mit den exakten Keys: 'Extraversion', 'Verträglichkeit', 'Gewissenhaftigkeit', 'Neurotizismus', 'Offenheit'."},
                            {"role": "user", "content": f"Hier ist der Chatverlauf:\n{chat_text}"}
                        ],
                        response_format={"type": "json_object"}
                    )
                    st.session_state.ai_bfi = json.loads(res.choices[0].message.content)
                except Exception as e:
                    st.error(f"Fehler bei der Analyse: {e}")
                    st.session_state.ai_bfi = {t: 0 for t in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]}

        for t in ["Extraversion", "Verträglichkeit", "Gewissenhaftigkeit", "Neurotizismus", "Offenheit"]:
            ki_wert = st.session_state.ai_bfi.get(t, 0)
            st.metric(f"Geschätzte Ausprägung: {t}", f"{ki_wert} / 5")
            st.progress(float(ki_wert) / 5.0 if ki_wert else 0.0)

        st.divider()

        if not st.session_state.data_saved:
            if st.button("Ergebnisse final speichern & beenden"):
                final_payload = {
                    "id": st.session_state.participant_id,
                    "matrikelnummer": st.session_state.matrikelnummer,
                    "condition": st.session_state.condition,
                    "research_consent": st.session_state.research_consent,
                    "ai_assessment": st.session_state.ai_bfi,
                    "chat": st.session_state.messages
                }
                if save_to_nextcloud(st.session_state.participant_id, final_payload):
                    st.session_state.data_saved = True
                    st.rerun()
                else:
                    st.error("Speicherfehler.")
        else:
            st.success("Daten erfolgreich gespeichert!")
            col_a, col_b = st.columns(2)
            with col_a: st.link_button("Zur Uni-Webseite", "https://www.uni-ulm.de/in/psy-dia/forschung/an-studien-teilnehmen/")
            with col_b: 
                if st.button("🔄 APP RESET"): reset_app()

if __name__ == "__main__":
    main()
