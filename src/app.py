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
                    st.subheader("Retrieved Hyperedges")
                    for he in result.get("retrieved_hyperedges", [])[:3]:
                        st.markdown(f"**{he.get('function_id', '?')}** ({he['similarity']:.2f})")
                        st.caption(he.get("compression", "")[:120])
                with col2:
                    st.subheader("Candidate Nodes")
                    st.json(result.get("candidate_nodes", {}))
                with col3:
                    st.subheader("Hermes Seed")
                    st.json(result.get("hermes_seed", {}))

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

    if st.button("Regenerate", use_container_width=True):
        result = st.session_state.get("last_result", {})
        if result:
            with st.spinner("Regenerating..."):
                try:
                    new_result = graph.invoke(
                        {
                            "thread_id": st.session_state.thread_id,
                            "user_text": result.get("user_text", ""),
                        },
                        {"configurable": {"thread_id": st.session_state.thread_id}},
                    )
                    new_response = new_result.get("final_response", "")
                    st.chat_message("assistant").write(f"_[regenerated]_ {new_response}")
                    st.session_state.messages.append({"role": "assistant", "content": f"_[regenerated]_ {new_response}"})
                    st.session_state.last_result = new_result
                    st.session_state.last_run_id = new_result.get("pathway_run_id", "")
                    st.rerun()
                except Exception as e:
                    st.error(f"Regeneration failed: {e}")
