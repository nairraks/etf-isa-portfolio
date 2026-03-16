"""ETF ISA Portfolio Agent — Streamlit chat interface.

Run locally:
    uv run streamlit run agent/app.py

Deploy to Streamlit Community Cloud:
    - Set ANTHROPIC_API_KEY in the Streamlit secrets dashboard
    - Point the app entry point to agent/app.py
"""

import json
import os
import sys
from pathlib import Path

import anthropic
import streamlit as st

# Ensure project root and agent dir are on the path
_AGENT_DIR = Path(__file__).parent
_PROJECT_ROOT = _AGENT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_AGENT_DIR))

from prompts import SYSTEM  # noqa: E402  (after sys.path setup)
from tools import TOOL_SCHEMAS, execute_tool  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 600
MAX_HISTORY_TURNS = 10  # Only last N user+assistant pairs sent to API

DISCLAIMER = (
    "⚠️ **Disclaimer** — This portfolio is documented for **educational purposes only**. "
    "It is NOT investment advice. The author is not a financial adviser. "
    "You can lose money investing. Past performance does not guarantee future results."
)

STARTER_QUESTIONS = [
    "How was this portfolio constructed?",
    "What is the portfolio's current yield?",
    "How are ETFs screened and selected?",
    "Why are bonds a larger cash weight than equities?",
]

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="ETF Portfolio Agent",
    page_icon="📊",
    layout="centered",
)

st.title("📊 ETF ISA Portfolio Agent")
st.caption("Ask questions about how this DIY ETF portfolio was built and how it performs.")
st.warning(DISCLAIMER)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": str, "content": str|list}

# ---------------------------------------------------------------------------
# Render chat history
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    if msg["role"] in ("user", "assistant"):
        content = msg["content"]
        # content may be a string (assistant text) or a list (tool results — skip display)
        if isinstance(content, str):
            with st.chat_message(msg["role"]):
                st.markdown(content)

# ---------------------------------------------------------------------------
# Starter question buttons (only before first message)
# ---------------------------------------------------------------------------

if not st.session_state.messages:
    st.markdown("**Try asking:**")
    cols = st.columns(2)
    for i, question in enumerate(STARTER_QUESTIONS):
        if cols[i % 2].button(question, key=f"starter_{i}", use_container_width=True):
            st.session_state.pending_question = question
            st.rerun()

# Handle button-triggered questions
if "pending_question" in st.session_state:
    user_input = st.session_state.pop("pending_question")
else:
    user_input = st.chat_input("Ask about the portfolio…")

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

if user_input:
    # Display and store user message
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Build truncated history for API call (last N turns)
    history = st.session_state.messages[-(MAX_HISTORY_TURNS * 2):]

    # Initialise Anthropic client (reads ANTHROPIC_API_KEY from env / Streamlit secrets)
    api_key = os.environ.get("ANTHROPIC_API_KEY") or st.secrets.get("ANTHROPIC_API_KEY", None)
    if not api_key:
        st.error("ANTHROPIC_API_KEY not found. Set it in your environment or Streamlit secrets.")
        st.stop()

    client = anthropic.Anthropic(api_key=api_key)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM,
                    tools=TOOL_SCHEMAS,
                    messages=history,
                )

                # Agentic tool-use loop
                while response.stop_reason == "tool_use":
                    tool_uses = [b for b in response.content if b.type == "tool_use"]
                    tool_results = []
                    for tu in tool_uses:
                        result = execute_tool(tu.name, tu.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": json.dumps(result, default=str),
                        })

                    # Append assistant turn (with tool_use blocks) + tool results
                    history = history + [
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results},
                    ]

                    response = client.messages.create(
                        model=MODEL,
                        max_tokens=MAX_TOKENS,
                        system=SYSTEM,
                        tools=TOOL_SCHEMAS,
                        messages=history,
                    )

                # Extract final text
                final_text = next(
                    (b.text for b in response.content if b.type == "text"),
                    "Sorry, I couldn't generate a response. Please try again.",
                )

            except anthropic.AuthenticationError:
                final_text = "❌ Authentication failed. Check your ANTHROPIC_API_KEY."
            except anthropic.RateLimitError:
                final_text = "❌ Rate limit reached. Please wait a moment and try again."
            except anthropic.APIStatusError as e:
                final_text = f"❌ API error ({e.status_code}). Please try again."
            except Exception as e:
                final_text = f"❌ Unexpected error: {e}"

        st.markdown(final_text)

    st.session_state.messages.append({"role": "assistant", "content": final_text})
