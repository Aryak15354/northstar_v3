import streamlit as st
import pandas as pd
import plotly.express as px

# --------------------------
# CONFIG
# --------------------------

st.set_page_config(
    layout="wide",
    page_title="Northstar Terminal",
    initial_sidebar_state="collapsed"
)

# --------------------------
# STYLE
# --------------------------

st.markdown("""
<style>
body { background:#0B0E14; color:#E5E7EB; }
h1,h2,h3 { color:#00FFAA; }
.card {
    background:#111827;
    border-radius:8px;
    padding:12px;
    margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# DATA LOADER
# --------------------------

@st.cache_data(ttl=300)
def load_snapshot():
    df = pd.read_parquet("data/processed/cache/dashboard_snapshot.parquet")
    return df.iloc[0].to_dict()

state = load_snapshot()

# --------------------------
# GLOBAL STATUS BAR
# --------------------------

st.markdown(f"""
<div class="card">
<b>REGIME:</b> {state['market']['macro_regime']} |
<b>RISK:</b> {state['market']['risk_on_probability']:.2f} |
<b>EXPOSURE:</b> {state['market']['allowed_exposure']:.0%} |
<b>DD:</b> {state['performance']['drawdown']:.1%} |
<b>VOL:</b> {state['performance']['vol_20d']:.1%} |
<b>AI:</b> {state['beliefs']['status']} ({state['beliefs']['confidence']:.2f})
</div>
""", unsafe_allow_html=True)

# --------------------------
# MODE SELECTOR
# --------------------------

mode = st.radio("", ["WAR ROOM", "PORTFOLIO", "INTELLIGENCE"], horizontal=True)

# --------------------------
# WAR ROOM
# --------------------------

if mode == "WAR ROOM":

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("<div class='card'><h3>Risk</h3></div>", unsafe_allow_html=True)
        st.metric("Volatility", f"{state['performance']['vol_20d']:.1%}")
        st.metric("Drawdown", f"{state['performance']['drawdown']:.1%}")

    with c2:
        st.markdown("<div class='card'><h3>Exposure</h3></div>", unsafe_allow_html=True)
        st.metric("Allowed", f"{state['market']['allowed_exposure']:.0%}")
        st.metric("Cash", f"{1 - state['market']['allowed_exposure']:.0%}")

    with c3:
        st.markdown("<div class='card'><h3>Status</h3></div>", unsafe_allow_html=True)
        st.metric("AI", state['beliefs']['status'])
        st.metric("Conviction", f"{state['beliefs']['confidence']:.2f}")

# --------------------------
# PORTFOLIO
# --------------------------

elif mode == "PORTFOLIO":

    alloc = pd.DataFrame.from_dict(state["capital"]["allocations"], orient="index", columns=["weight"])
    alloc.reset_index(inplace=True)
    alloc.columns = ["strategy","weight"]

    fig = px.bar(alloc, x="strategy", y="weight", title="Strategy Allocation")

    st.plotly_chart(fig, use_container_width=True)

# --------------------------
# INTELLIGENCE
# --------------------------

else:

    belief = pd.DataFrame(state["beliefs"]["strategies"])
    regret = pd.DataFrame(state["regret"]["strategies"])

    col1, col2 = st.columns(2)

    with col1:
        st.plotly_chart(px.bar(belief, x="strategy", y="skill_prob", title="Bayesian Skill"),
                        use_container_width=True)

    with col2:
        st.plotly_chart(px.bar(regret, x="strategy", y="cum_regret", title="Strategy Regret"),
                        use_container_width=True)