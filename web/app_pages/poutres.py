"""Page Poutres (en construction : étape E26)."""

import streamlit as st

from mecastruct.ui import state
from mecastruct.ui.formula_panel import formula_panel

state.init()

st.title("Poutres")
formula_panel("equilibre")
st.info("Page en construction (étape E26).")
