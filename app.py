import streamlit as st
import json
import os
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import altair as alt

# --- CONFIGURATION ---
USER_DB_FILE = "users.json"

TEMPLATES = {
    "Anterior A": ["Incline Chest Press (DB)", "Butterfly", "Lateral Raises (Cable)", "Overhead Extension", "Rope Pushdown", "Hack Squat", "Leg Extension", "Crunches"],
    "Anterior B": ["Flat Chest Press", "Incline Chest Press (Mach)", "Lateral Raises (Cable)", "Overhead Extension", "Rope Pushdown", "Hack Squat", "Leg Extension", "Crunches"],
    "Posterior A": ["Lat Pulldown", "Seated Row", "T-Bar Row", "Preacher Curl", "Hammer Curl", "Wrist Curl", "Back Delts", "RDL", "Leg Curls"],
    "Posterior B": ["Lat Pulldown", "Seated Row", "T-Bar Row", "Incline Bi Curl", "Hammer Curl", "Reverse Curls", "Back Delts", "RDL", "Leg Curls"]
}

# --- AUTHENTICATION & DATA ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def load_users():
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USER_DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

def authenticate(username, password):
    users = load_users()
    if username in users and users[username] == hash_password(password):
        return True
    return False

def register_user(username, password):
    users = load_users()
    if username in users: return False
    users[username] = hash_password(password)
    save_users(users)
    return True

# --- HISTORY MANAGEMENT ---
def get_user_history_file(username):
    return f"history_{username}.json"

def load_history(username):
    filename = get_user_history_file(username)
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_history(username, history):
    filename = get_user_history_file(username)
    with open(filename, "w") as f:
        json.dump(history, f, indent=4)

# --- LEADERBOARD LOGIC ---
def get_leaderboard_data():
    """Scans all history files to count workout days for each user."""
    users = load_users()
    leaderboard = []
    
    for user in users.keys():
        hist = load_history(user)
        # Count only 'Workout' days (ignore Rest/Missed)
        workout_count = sum(1 for log in hist.values() if log.get("type") != "Rest")
        leaderboard.append({"User": user, "Workouts": workout_count})
        
    # Sort by Workouts (Highest first)
    return sorted(leaderboard, key=lambda x: x["Workouts"], reverse=True)

# --- VISUALIZATION ---
def plot_calendar(history):
    today = datetime.now()
    start_of_month = today.replace(day=1)
    next_month = (start_of_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_of_month = next_month - timedelta(days=1)
    
    date_range = pd.date_range(start=start_of_month, end=end_of_month)
    data = []
    
    for d in date_range:
        d_str = d.strftime("%Y-%m-%d")
        day_log = history.get(d_str)
        status = "Missed"
        label = ""
        
        if day_log:
            if day_log["type"] == "Rest":
                status = "Rest"; label = "💤"
            else:
                status = "Workout"; label = day_log["type"].replace("Anterior", "Ant").replace("Posterior", "Post")

        data.append({"date": d, "day": d.day, "week": d.strftime("%U"), "weekday": d.strftime("%a"), "status": status, "label": label})
        
    base = alt.Chart(pd.DataFrame(data)).encode(
        x=alt.X("weekday:O", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], title=None),
        y=alt.Y("week:O", axis=None, sort="descending")
    )
    rects = base.mark_rect(stroke="white").encode(
        color=alt.Color("status", scale=alt.Scale(domain=["Workout", "Rest", "Missed"], range=["#2ecc71", "#3498db", "#ecf0f1"]), legend=None)
    )
    text = base.mark_text(dy=-10, size=10).encode(text="day")
    labels = base.mark_text(dy=5, size=9).encode(text="label")
    st.altair_chart((rects + text + labels).properties(height=300, title=f"{today.strftime('%B')} Schedule"), use_container_width=True)


# --- MAIN APP ---
st.set_page_config(page_title="Gym Tracker", page_icon="🏋️", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# --- LOGIN / LEADERBOARD PAGE ---
if not st.session_state.logged_in:
    st.title("🔒 Gym Tracker Login")
    
    # LEADERBOARD SECTION
    st.subheader("🏆 Consistency Leaderboard")
    leader_data = get_leaderboard_data()
    
    if leader_data:
        # Display top 5 as a nice dataframe
        df_leader = pd.DataFrame(leader_data).head(5)
        # Add a rank column (1, 2, 3...)
        df_leader.index = df_leader.index + 1
        st.dataframe(df_leader, use_container_width=True)
    else:
        st.info("No users yet. Be the first!")

    st.divider()

    # LOGIN TABS
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        login_user = st.text_input("Username", key="login_user")
        login_pass = st.text_input("Password", type="password", key="login_pass")
        if st.button("Login"):
            if authenticate(login_user, login_pass):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.toast(f"Welcome, {login_user}!")
                st.rerun()
            else:
                st.error("Invalid credentials")

    with tab2:
        new_user = st.text_input("New Username", key="new_user")
        new_pass = st.text_input("New Password", type="password", key="new_pass")
        if st.button("Create Account"):
            if register_user(new_user, new_pass):
                st.success("Account created! Login now.")
            else:
                st.error("Username taken.")

# --- DASHBOARD (LOGGED IN) ---
else:
    user = st.session_state.username
    history = load_history(user)
    
    col1, col2 = st.columns([3, 1])
    with col1: st.title(f"🏋️ {user}'s Tracker")
    with col2: 
        if st.button("Logout"):
            st.session_state.logged_in = False; st.rerun()

    plot_calendar(history)
    st.divider()

    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("### 📅 Log Workout")
        selected_date = st.date_input("Select Date", datetime.now(), label_visibility="collapsed")
        date_str = selected_date.strftime("%Y-%m-%d")

    log = history.get(date_str, None)

    if log is None:
        c1, c2 = st.columns(2)
        if c1.button("💤 Mark Rest"):
            history[date_str] = {"type": "Rest", "exercises": []}
            save_history(user, history)
            st.rerun()
        
        st.write("Or select routine:")
        cols = st.columns(2)
        for i, split in enumerate(TEMPLATES.keys()):
            with cols[i % 2]:
                if st.button(f"💪 {split}", use_container_width=True):
                    exs = [{"name": n, "sets": 3, "reps": 10, "weight": 10.0} for n in TEMPLATES[split]]
                    history[date_str] = {"type": split, "exercises": exs}
                    save_history(user, history)
                    st.rerun()

    elif log["type"] == "Rest":
        st.success("Rest Day.")
        if st.button("Delete"): del history[date_str]; save_history(user, history); st.rerun()

    else:
        st.success(f"✅ {log['type']}")
        df_ex = pd.DataFrame(log['exercises'])
        edited_df = st.data_editor(
            df_ex,
            column_config={
                "name": "Exercise",
                "sets": st.column_config.NumberColumn("Sets", min_value=1, max_value=10),
                "reps": st.column_config.NumberColumn("Reps", min_value=1, max_value=100),
                "weight": st.column_config.NumberColumn("Kg", min_value=0.0, max_value=500.0, step=2.5)
            },
            hide_index=True, use_container_width=True
        )
        if st.button("💾 Save"):
            history[date_str]["exercises"] = edited_df.to_dict('records')
            save_history(user, history)
            st.toast("Saved!")
        
        if st.button("Delete"): del history[date_str]; save_history(user, history); st.rerun()