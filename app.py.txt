import streamlit as st
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import altair as alt

# --- CONFIGURATION ---
HISTORY_FILE = "gym_history.json"

TEMPLATES = {
    "Anterior A": ["Incline Chest Press (DB)", "Butterfly", "Lateral Raises (Cable)", "Overhead Extension", "Rope Pushdown", "Hack Squat", "Leg Extension", "Crunches"],
    "Anterior B": ["Flat Chest Press", "Incline Chest Press (Mach)", "Lateral Raises (Cable)", "Overhead Extension", "Rope Pushdown", "Hack Squat", "Leg Extension", "Crunches"],
    "Posterior A": ["Lat Pulldown", "Seated Row", "T-Bar Row", "Preacher Curl", "Hammer Curl", "Wrist Curl", "Back Delts", "RDL", "Leg Curls"],
    "Posterior B": ["Lat Pulldown", "Seated Row", "T-Bar Row", "Incline Bi Curl", "Hammer Curl", "Reverse Curls", "Back Delts", "RDL", "Leg Curls"]
}

# --- DATA MANAGEMENT ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

if 'history' not in st.session_state:
    st.session_state.history = load_history()

# --- UI LAYOUT ---
st.set_page_config(page_title="Gym Tracker", page_icon="🏋️", layout="centered")

st.title("🏋️ My Gym Tracker")

col1, col2 = st.columns([2, 1])
with col1:
    selected_date = st.date_input("Select Date", datetime.now())
    date_str = selected_date.strftime("%Y-%m-%d")

log = st.session_state.history.get(date_str, None)

st.divider()

if log is None:
    st.info(f"No log for {date_str}")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("💤 Mark Rest Day", use_container_width=True):
            st.session_state.history[date_str] = {"type": "Rest", "exercises": []}
            save_history(st.session_state.history)
            st.rerun()
            
    st.write("Or select a workout:")
    for split_name in TEMPLATES.keys():
        if st.button(f"💪 {split_name}", use_container_width=True):
            exercises = [{"name": n, "sets": 3, "reps": 10, "weight": 10.0} for n in TEMPLATES[split_name]]
            st.session_state.history[date_str] = {"type": split_name, "exercises": exercises}
            save_history(st.session_state.history)
            st.rerun()

elif log["type"] == "Rest":
    st.success("💤 This is a REST DAY.")
    if st.button("Delete Log", type="primary"):
        del st.session_state.history[date_str]
        save_history(st.session_state.history)
        st.rerun()

else:
    st.subheader(f"{log['type']}")
    df = pd.DataFrame(log['exercises'])
    edited_df = st.data_editor(
        df,
        column_config={
            "name": "Exercise",
            "sets": st.column_config.NumberColumn("Sets", min_value=1, max_value=10, step=1),
            "reps": st.column_config.NumberColumn("Reps", min_value=1, max_value=100, step=1),
            "weight": st.column_config.NumberColumn("Kg", min_value=0.0, max_value=500.0, step=2.5)
        },
        hide_index=True,
        use_container_width=True
    )

    if st.button("💾 Save Changes", type="primary", use_container_width=True):
        updated_exercises = edited_df.to_dict('records')
        st.session_state.history[date_str]["exercises"] = updated_exercises
        save_history(st.session_state.history)
        st.toast("Workout Saved!")

    if st.button("Delete Day Log"):
        del st.session_state.history[date_str]
        save_history(st.session_state.history)
        st.rerun()

st.divider()
st.subheader("📊 Consistency Stats")

if st.session_state.history:
    dates = sorted(st.session_state.history.keys())
    start_date = datetime.strptime(dates[0], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    total_days = (end_date - start_date).days + 1
    counts = {"Workouts": 0, "Rest": 0, "Missed": 0}
    
    current = start_date
    while current <= end_date:
        d_s = current.strftime("%Y-%m-%d")
        l = st.session_state.history.get(d_s)
        if l:
            if l["type"] == "Rest": counts["Rest"] += 1
            else: counts["Workouts"] += 1
        else:
            counts["Missed"] += 1
        current += timedelta(days=1)
        
    source = pd.DataFrame({'Category': list(counts.keys()), 'Value': list(counts.values())})
    c = alt.Chart(source).mark_arc(innerRadius=50).encode(
        theta=alt.Theta("Value", stack=True),
        color=alt.Color("Category", scale=alt.Scale(domain=['Workouts', 'Rest', 'Missed'], range=['#2ecc71', '#3498db', '#95a5a6'])),
        tooltip=["Category", "Value"]
    )
    st.altair_chart(c, use_container_width=True)
    st.write(f"**Total Days Tracked:** {total_days}")
    st.write(f"Workouts: {counts['Workouts']} | Rest: {counts['Rest']} | Missed: {counts['Missed']}")
else:
    st.write("Log your first workout to see stats!")