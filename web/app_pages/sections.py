"""Page Sections (en construction : étape E25)."""

import streamlit as st

from mecastruct.ui import state
from mecastruct.ui.formula_panel import formula_panel

state.init()

st.title("Sections")
formula_panel("geometrie")
st.info("Page en construction (étape E25).")
