
import streamlit as st

st.set_page_config(
    page_title="TurtleGuard Sentinel",
    page_icon="🐢",
    layout="wide"
)

st.title("🐢 TurtleGuard Sentinel")
st.subheader("AI-Powered Coastal Intelligence")

st.write(
    "Investigate Florida beaches and prioritize "
    "inspections to help protect nesting sea turtles."
)

beach = st.selectbox(
    "Select a Florida beach",
    [
        "Juno Beach",
        "Jupiter Beach (North)",
        "Coral Cove Park"
    ]
)

hours = st.slider(
    "Available volunteer hours",
    min_value=1,
    max_value=12,
    value=4
)

if st.button("🔎 Launch Investigation"):
    st.info(f"Investigation requested for {beach}.")
    st.write(f"Available volunteer hours: {hours}")
    st.warning("AI analysis will be connected next.")
