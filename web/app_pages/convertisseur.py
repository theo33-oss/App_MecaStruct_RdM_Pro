"""Page Convertisseur (en construction : étape E24)."""

import streamlit as st

from mecastruct.ui import state
from mecastruct.ui.formula_panel import formula_panel

state.init()

st.title("Convertisseur")
formula_panel(None)
st.info("Page en construction (étape E24).")
