import pandas as pd
import streamlit as st

from agent import EXAMPLE_INQUIRIES, EXAMPLE_REQUESTS, PROPERTIES, draft_reply, triage_request

st.set_page_config(page_title="Property Management AI Agent", page_icon="🏠", layout="wide")


def esc(text):
    """Streamlit markdown treats paired $ signs as LaTeX, so escape them."""
    return text.replace("$", "\\$")


st.title("Property Management AI Agent")
st.write(
    "Two of the daily jobs from your list, working end to end: qualifying a new rental inquiry and "
    "replying to it, and triaging a maintenance request and notifying the right vendor."
)

with st.expander("Properties the agent knows about (mock Tenant Cloud data)"):
    st.dataframe(pd.DataFrame(PROPERTIES), width="stretch", hide_index=True)

tab1, tab2 = st.tabs(["1. Leads and messaging", "2. Maintenance requests"])

with tab1:
    choice = st.selectbox("Pick an example inquiry, or write your own", list(EXAMPLE_INQUIRIES) + ["Write my own"])
    text = st.text_area("Inquiry arriving from Zillow / Furnished Finder / Airbnb",
                        value="" if choice == "Write my own" else EXAMPLE_INQUIRIES[choice], height=90, key=f"inq_{choice}")
    if text.strip():
        q, reply = draft_reply(text)
        c1, c2, c3 = st.columns(3)
        c1.metric("Lead quality", q["label"].upper())
        c2.metric("Matched property", q["match"]["name"] if q["match"] else "none yet")
        c3.metric("Flag team", "YES" if q["flag_team"] else "no")
        st.markdown("**Why this rating**")
        for r in q["reasons"]:
            st.markdown(f"- {esc(r)}")
        st.markdown("**Drafted reply**")
        st.info(esc(reply))
        with st.expander("Facts extracted from the message"):
            st.json(q["facts"])

with tab2:
    choice2 = st.selectbox("Pick an example request, or write your own", list(EXAMPLE_REQUESTS) + ["Write my own"])
    text2 = st.text_area("Maintenance request from a tenant",
                         value="" if choice2 == "Write my own" else EXAMPLE_REQUESTS[choice2], height=90, key=f"req_{choice2}")
    if text2.strip():
        r = triage_request(text2)
        c1, c2, c3 = st.columns(3)
        c1.metric("Category", r["category"])
        c2.metric("Urgency", r["urgency"].upper())
        c3.metric("Vendor notified", r["vendor"])
        if r["escalate_to_owner"]:
            st.error("Emergency: the owner is alerted by text at the same time as the vendor.")
        st.markdown("**Auto-reply to tenant**")
        st.info(esc(r["reply"]))
        st.markdown("**Message sent to vendor**")
        st.code(r["vendor_message"], language=None)

st.caption(
    "Mock property data and rule-based logic, so it runs with no keys. In production the same steps run behind "
    "Tenant Cloud webhooks (via Zapier or Make), with an LLM reading free-form messages and these rules kept as guardrails."
)
