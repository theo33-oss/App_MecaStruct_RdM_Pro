"""Page Sollicitations (en construction : étape E28)."""

import streamlit as st

from mecastruct.ui import state
from mecastruct.ui.formula_panel import formula_panel

state.init()

st.title("Sollicitations")
formula_panel("traction")
st.info("Page en construction (étape E28).")
