"""
Page 3: Chat Refinement
Broker chat interface with strategy context awareness.
"""

import streamlit as st
import requests
import base64
import os

st.set_page_config(page_title="Chat Refinement — ClimateNexus", page_icon="💬", layout="wide")

API = st.session_state.get("api_base", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# JLL Logo
# ---------------------------------------------------------------------------

def get_jll_logo_base64():
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "jll_logo.png")
    with open(logo_path, "rb") as f:
        img_data = f.read()
    encoded = base64.b64encode(img_data).decode()
    return f"data:image/png;base64,{encoded}"

JLL_LOGO = get_jll_logo_base64()

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown(f'<img src="{JLL_LOGO}" alt="JLL Logo" style="width: 100px; margin-top: 8px;">', unsafe_allow_html=True)
with col_title:
    st.markdown("# 💬 Chat Refinement")
    st.markdown("Ask follow-up questions to customize the strategy for your client.")
st.markdown("---")


# ---------------------------------------------------------------------------
# Check prereqs
# ---------------------------------------------------------------------------

strategy = st.session_state.get("strategy_response")
if not strategy:
    st.warning("⚠️ No strategy generated yet. Please generate a strategy first.")
    st.page_link("pages/2_📊_Strategy_Agent.py", label="Go to Strategy Agent →", icon="📊")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar context
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 📋 Current Strategy")
    recs = strategy.get("recommendations", [])
    st.markdown(f"**{len(recs)} recommendations**")
    st.markdown(f"**Savings:** ${strategy.get('total_savings_usd', 0):,.0f}/yr")
    st.markdown(f"**Incentives:** ${strategy.get('total_incentives_usd', 0):,.0f}")

    st.markdown("---")
    st.markdown("**Recommendations:**")
    for r in recs:
        priority_icon = {"quick_win": "🟢", "medium_term": "🟡", "capex_heavy": "🔴"}.get(r["priority"], "⚪")
        st.markdown(f"{priority_icon} {r['action']}")

    st.markdown("---")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# ---------------------------------------------------------------------------
# Init chat history
# ---------------------------------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------------------------------------------------------
# Suggested questions
# ---------------------------------------------------------------------------

if not st.session_state.chat_history:
    st.markdown("### 💡 Suggested Questions")
    suggestions = [
        "What IRA tax credits apply to heat pump installations?",
        "How does Local Law 97 affect our NYC properties?",
        "Can you prioritize recommendations by payback period?",
        "What's the total cost for quick-win measures only?",
        "How much would we save by implementing all flood mitigation measures?",
    ]

    cols = st.columns(3)
    for i, q in enumerate(suggestions):
        col = cols[i % 3]
        if col.button(q, key=f"suggest_{i}", use_container_width=True):
            st.session_state._pending_question = q
            st.rerun()

    st.markdown("---")

# ---------------------------------------------------------------------------
# Chat display
# ---------------------------------------------------------------------------

chat_container = st.container()

with chat_container:
    for msg in st.session_state.chat_history:
        role = msg["role"]
        avatar = "🧑‍💼" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

# Handle pending suggestion
pending = st.session_state.pop("_pending_question", None)
user_input = st.chat_input("Ask about the strategy…") or pending

if user_input:
    # Append user message
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with chat_container:
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(user_input)

    # Build strategy context
    strategy_context = {
        "recommendations": strategy.get("recommendations", []),
        "strategy_narrative": strategy.get("strategy_narrative", ""),
        "total_savings_usd": strategy.get("total_savings_usd", 0),
        "total_incentives_usd": strategy.get("total_incentives_usd", 0),
    }

    # Call API
    with chat_container:
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking…"):
                try:
                    r = requests.post(
                        f"{API}/agent/chat",
                        json={
                            "message": user_input,
                            "conversation_history": st.session_state.chat_history[:-1],
                            "strategy_context": strategy_context,
                        },
                        timeout=60,
                    )
                    r.raise_for_status()
                    reply = r.json()["reply"]
                except requests.exceptions.ConnectionError:
                    reply = "❌ Cannot connect to backend. Please check that the API is running."
                except Exception as e:
                    reply = f"❌ Error: {e}"

                st.markdown(reply)

    # Append assistant reply
    st.session_state.chat_history.append({"role": "assistant", "content": reply})
