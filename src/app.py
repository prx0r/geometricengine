import streamlit as st
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from src.graph import graph
from src.weights import apply_feedback

DB_PATH = "data/engine.sqlite"

st.set_page_config(page_title="HXRMXS UNO Engine", layout="wide")
st.title("HXRMXS UNO Engine")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = "local-test-1"
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

user_text = st.chat_input("Talk to the graph...")

if user_text:
    st.chat_message("user").write(user_text)
    st.session_state.messages.append({"role": "user", "content": user_text})

    with st.spinner("Thinking..."):
        try:
            result = graph.invoke(
                {"thread_id": st.session_state.thread_id, "user_text": user_text},
                {"configurable": {"thread_id": st.session_state.thread_id}},
            )

            response_text = result.get("final_response", "")
            st.chat_message("assistant").write(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
            st.session_state.last_result = result

            with st.expander("Trace"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.subheader("Classification")
                    st.json(result.get("classification", {}))
                    st.subheader("Selected Pathway")
                    st.json(result.get("selected_pathway", {}))
                with col2:
                    st.subheader("Graph MyThought")
                    st.json(result.get("graph_mythought", {}))
                with col3:
                    st.subheader("Pathway Candidates")
                    candidates = result.get("pathway_candidates", [])
                    for c in candidates[:3]:
                        st.markdown(f"**{c.get('function_id', '?')}** score={c.get('score', 0):.3f}")
                    st.subheader("Response Form")
                    st.write(result.get("response_form", ""))
                    st.subheader("Retrieved")
                    for he in result.get("retrieved_hyperedges", [])[:3]:
                        st.markdown(f"**{he.get('function_id', '?')}** ({he.get('similarity', 0):.2f})")
                        st.caption(he.get("mythought_text", "")[:120])

            st.session_state.last_run_id = result.get("pathway_run_id", "")

        except Exception as e:
            st.error(f"Error: {e}")

if "last_run_id" in st.session_state and st.session_state.last_run_id:
    st.divider()
    st.write("Rate last response:")
    cols = st.columns(5)
    for col, score in zip(cols, [-2, -1, 0, 1, 2]):
        label = {2: "Excellent", 1: "Good", 0: "Neutral", -1: "Bad", -2: "Terrible"}[score]
        if col.button(f"{score} - {label}", use_container_width=True):
            apply_feedback(DB_PATH, st.session_state.last_run_id, score)
            st.success(f"Saved feedback {score}")
            st.rerun()
