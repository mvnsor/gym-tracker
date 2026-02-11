import streamlit as st
import json
import os
from datetime import datetime, timedelta, date
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

# --- DATA FUNCTIONS ---
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

# --- CALENDAR VISUALIZATION FUNCTION ---
def plot_calendar():
    # 1. Prepare Data
    # Get range for current month view
    today = datetime.now()
    # Find start of this month
    start_of_month = today.replace(day=1)
    # Find end of this month (start of next month - 1 day)
    next_month = (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_of_month = next_month - timedelta(days=1)
    
    # Generate all dates for the month
    date_range = pd.date_range(start=start_of_month, end=end_of_month)
    
    data = []
    for d in date_range:
        d_str = d.strftime("%Y-%m-%d")
        day_log = st.session_state.history.get(d_str)
        
        status = "Missed"
        short_label = ""
        
        if day_log:
            if day_log["type"] == "Rest":
                status = "Rest"
                short_label = "💤"
            else:
                status = "Workout"
                # Get initials (e.g., Anterior A -> Ant A)
                short_label = day_log["type"].replace("Anterior", "Ant").replace("Posterior", "Post")

        data.append({
            "date": d,
            "day_num": d.day,
            "week": d.strftime("%U"), # Week number
            "weekday": d.strftime("%a"), # Mon, Tue...
            "status": status,
            "label": short_label
        })
        
    df = pd.DataFrame(data)

    # 2. Build Chart
    # Base chart
    base = alt.Chart(df).encode(
        x=alt.X("weekday:O", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], title=None),
        y=alt.Y("week:O", axis=None, sort="descending"), # Sort desc so earlier weeks are at top
        tooltip=["date", "status", "label"]
    )

    # Rectangles (The boxes)
    rects = base.mark_rect(stroke="white", strokeWidth=2).encode(
        color=alt.Color("status", 
                        scale=alt.Scale(domain=["Workout", "Rest", "Missed"], 
                                        range=["#2ecc71", "#3498db", "#ecf0f1"]),
                        legend=None)
    )

    # Text (Day Numbers)
    text = base.mark_text(dy=-10, size=10, color="black").encode(
        text="day_num"
    )
    
    # Text (Workout Labels)
    labels = base.mark_text(dy=5, size=9, color="black").encode(
        text="label"
    )

    # Combine
    chart = (rects + text + labels).properties(
        width="container",
        height=300,
        title=f"{today.strftime('%B %Y')} Schedule"
    ).configure_view(strokeWidth=0)

    st.altair_chart(chart, use_container_width=True)


# --- MAIN APP LAYOUT ---
st.set_page_config(page_title="Gym Tracker", page_icon="🏋️", layout="centered")

st.title("🏋️ My Gym Tracker")

# 1. SHOW THE VISUAL CALENDAR
plot_calendar()

st.divider()

# 2. DATA ENTRY SECTION
col1, col2 = st.columns([2, 1])
with col1:
    st.write("### 📅 Edit Log")
    selected_date = st.date_input("Select Date to Edit", datetime.now(), label_visibility="collapsed")
    date_str = selected_date.strftime("%Y-%m-%d")

log = st.session_state.history.get(date_str, None)

if log is None:
    st.info(f"No log for {date_str}")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("💤 Mark Rest Day", use_container_width=True):
            st.session_state.history[date_str] = {"type": "Rest", "exercises": []}
            save_history(st.session_state.history)
            st.rerun()
            
    st.write("Or select a workout:")
    cols = st.columns(2)
    for i, split_name in enumerate(TEMPLATES.keys()):
        with cols[i % 2]:
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
    st.success(f"✅ {log['type']} Logged")
    
    # Table Editor
    df_ex = pd.DataFrame(log['exercises'])
    edited_df = st.data_editor(
        df_ex,
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