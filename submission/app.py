"""Streamlit UI for Vitrious

Provides an interactive demo of the multi-agent stockout resolution system,
including the human approval interrupt.
"""

import os
import sys
import json
from pathlib import Path

# Add project root to path so we can import from tools/domain
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

import streamlit as st
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from submission.graph import build_graph
from submission.state.state import make_initial_state
from submission.config import DEFAULT_TARGET_COVER_DAYS


st.set_page_config(page_title="Vitrious Stockout Resolution", page_icon="📦", layout="wide")


@st.cache_resource
def get_graph():
    """Cache the graph instance (and its in-memory checkpointer) across runs."""
    return build_graph(checkpointer=MemorySaver())


def init_session():
    """Initialise Streamlit session state variables."""
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "current_state" not in st.session_state:
        st.session_state.current_state = None
    if "is_paused" not in st.session_state:
        st.session_state.is_paused = False


def render_approval_ui(graph, thread_id, state_dict):
    """Render the UI for the human approval interrupt."""
    st.warning("⚠️ Human Approval Required")
    
    approval_request = state_dict.get("approval_request", {})
    proposal = approval_request.get("proposal", {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Proposal Details")
        st.write(f"**SKU:** {proposal.get('sku')}")
        st.write(f"**Warehouse:** {proposal.get('warehouse_id')}")
        st.write(f"**Vendor:** {proposal.get('recommended_vendor_id')}")
        st.write(f"**Quantity:** {proposal.get('quantity')}")
        st.write(f"**Total Cost:** ${proposal.get('total_cost', 0):.2f}")
        
    with col2:
        st.subheader("Policy Review")
        st.write(f"**Passed Policy:** {proposal.get('policy_passed')}")
        if proposal.get('policy_violations'):
            st.error("Violations:")
            for v in proposal.get('policy_violations', []):
                st.write(f"- {v}")
    
    st.subheader("Agent Reasoning")
    st.info(proposal.get("recommendation_reasoning", "No reasoning provided."))
    
    with st.form("approval_form"):
        decision = st.radio("Decision", ["APPROVED", "REJECTED"])
        comments = st.text_area("Comments")
        submitted = st.form_submit_button("Submit Decision")
        
        if submitted:
            decision_payload = {
                "decision": decision,
                "approver": "StreamlitUser",
                "comments": comments,
                "proposal_id": proposal.get("proposal_id", "")
            }
            
            with st.spinner(f"Processing {decision}..."):
                # Resume the graph by passing the Command to the human_approval node
                config = {"configurable": {"thread_id": thread_id}}
                graph.invoke(
                    Command(resume=decision_payload),
                    config=config
                )
                
                # Update session state with the new graph state
                st.session_state.current_state = graph.get_state(config).values
                st.session_state.is_paused = False
                st.rerun()


def main():
    init_session()
    graph = get_graph()
    
    st.title("Vitrious — Stockout Resolution System")
    st.write("Demonstrates multi-agent orchestration with LangGraph and human-in-the-loop.")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("New Case")
        with st.form("new_case_form"):
            sku = st.text_input("SKU", value="AC-003")
            warehouse = st.text_input("Warehouse ID", value="DEL-01")
            target_days = st.number_input("Target Cover Days", value=DEFAULT_TARGET_COVER_DAYS, min_value=7, max_value=45)
            
            if st.form_submit_button("Start Investigation"):
                initial_state = make_initial_state(sku, warehouse, target_days)
                st.session_state.thread_id = initial_state["case_id"]
                
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                
                with st.spinner("Agents are investigating..."):
                    try:
                        # Invoke graph; it will run until it hits the interrupt or END
                        final_state = graph.invoke(initial_state, config=config)
                        st.session_state.current_state = final_state
                        st.session_state.is_paused = False
                    except Exception as e:
                        # Check if it stopped due to interrupt
                        current_graph_state = graph.get_state(config)
                        if current_graph_state.next and "human_approval" in current_graph_state.next:
                            st.session_state.current_state = current_graph_state.values
                            st.session_state.is_paused = True
                        else:
                            st.error(f"Execution failed: {str(e)}")
                            st.session_state.current_state = current_graph_state.values
                st.rerun()

    # Main content area
    if not st.session_state.thread_id:
        st.info("👈 Enter SKU details in the sidebar and click 'Start Investigation'")
        return
        
    state = st.session_state.current_state
    if not state:
        return
        
    st.header(f"Case: {state.get('case_id')}")
    
    # Show interrupt UI if paused
    if st.session_state.is_paused:
        render_approval_ui(graph, st.session_state.thread_id, state)
        st.divider()
        
    # Show final outcome if finished
    elif not state.get("next") and state.get("outcome"):
        outcome = state.get("outcome")
        if outcome == "PURCHASE_REQUEST_CREATED":
            st.success(f"Outcome: {outcome}")
        elif outcome in ("NO_ACTION", "AWAITING_APPROVAL"):
            st.info(f"Outcome: {outcome}")
        else:
            st.error(f"Outcome: {outcome}")
            if state.get("error_message"):
                st.write(f"**Error:** {state.get('error_message')}")
        
    # Show tabs with state details
    tab1, tab2, tab3, tab4 = st.tabs(["Investigation", "Sourcing", "Execution", "Audit Log"])
    
    with tab1:
        inv_res = state.get("investigation_result")
        if inv_res:
            st.json(inv_res)
        else:
            st.write("No investigation result.")
            
    with tab2:
        src_res = state.get("sourcing_result")
        if src_res:
            st.json(src_res)
        else:
            st.write("No sourcing result.")
            
    with tab3:
        pr = state.get("purchase_request")
        if pr:
            st.json(pr)
        else:
            st.write("No purchase request.")
            
    with tab4:
        events = state.get("audit_events", [])
        if events:
            st.write(f"**{len(events)} events recorded**")
            for e in events:
                st.code(e)
        else:
            st.write("No audit events.")


if __name__ == "__main__":
    main()
