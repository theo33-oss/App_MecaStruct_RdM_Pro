"""Page Base de données (en construction : étape E24)."""

import streamlit as st

from mecastruct.ui import state
from mecastruct.ui.formula_panel import formula_panel

state.init()

st.title("Base de données")
formula_panel("materiaux")
st.info("Page en construction (étape E24).")
