"""Page Tenseurs & critères (en construction : étape E29)."""

import streamlit as st

from mecastruct.ui import state
from mecastruct.ui.formula_panel import formula_panel

state.init()

st.title("Tenseurs & critères")
formula_panel("tenseurs")
st.info("Page en construction (étape E29).")
