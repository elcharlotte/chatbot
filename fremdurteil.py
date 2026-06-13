import streamlit as st

# Zugriff auf die Secrets
nc_url = st.secrets["nextcloud"]["url"]
nc_user = st.secrets["nextcloud"]["username"]
nc_password = st.secrets["nextcloud"]["password"]
