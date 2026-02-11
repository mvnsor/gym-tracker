import streamlit as st
import json
import hashlib
from datetime import datetime, timedelta
import pandas as pd
import altair as alt
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
SHEET_URL = st.secrets["private_gsheets_url"] # We will set this in Step 4

TEMPLATES = {
    "Anterior A": ["Incline Chest Press (DB)", "Butterfly", "Lateral Raises (Cable)", "Overhead Extension", "Rope Pushdown", "Hack Squat", "Leg Extension", "Crunches"],
    "Anterior B": ["Flat Chest Press", "Incline Chest Press (Mach)", "Lateral Raises (Cable)", "Overhead Extension", "Rope Pushdown", "Hack Squat", "Leg Extension", "Crunches"],
    "Posterior A": ["Lat Pulldown", "Seated Row", "T-Bar Row", "Preacher Curl", "Hammer Curl", "Wrist Curl", "Back Delts", "RDL", "Leg Curls"],
    "Posterior B": ["Lat Pulldown", "Seated Row", "T-Bar Row", "Incline Bi Curl", "Hammer Curl", "Reverse Curls", "Back Delts", "RDL", "Leg Curls"]
}

# --- GOOGLE SHEETS CONNECTION ---
# Cache the connection so we don't reconnect on every click
@st.cache_resource
def get_gspread_client():
    # Load credentials from Streamlit secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def get_db():
    client = get_gspread_client()
    return client.open_by_url(SHEET_URL)

# --- USER MANAGEMENT ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def get_all_users():
    sh = get_db()
    ws = sh.worksheet("Users")
    records = ws.get_all_records() # Returns list of dicts: [{'Username': 'Ali', 'Password': '...'}, ...]
    # Convert to simple dict {username: password_hash}
    return {r['Username']: str(r['Password']) for r in records}

def register_user(username, password):
    users = get_all_users()
    if username in users:
        return False
    
    sh = get_db()
    ws = sh.worksheet("Users")
    ws.append_row([username, hash_password(password)])
    return True

def authenticate(username, password):
    users = get_all_users()
    if username in users and users[username] == hash_password(password):
        return True
    return False

# --- HISTORY MANAGEMENT (READ/WRITE) ---
def load_history_from_sheet():
    """Loads ALL logs for ALL users (needed for leaderboard)"""
    sh = get_db()
    ws = sh.worksheet("Logs")
    return ws.get_all_records()

def get_user_history(username):
    """Filters global history for specific user"""
    all_logs = load_history_from_sheet()
    user_history = {}
    
    for row in all_logs:
        if row['Username'] == username:
            date_str = str(row['Date'])
            try:
                # The data column is stored as a JSON string
                exercises = json.loads(row['Data'])
                user_history[date_str] = {
                    "type": row['Type'],
                    "exercises": exercises
                }
            except:
                continue # Skip corrupted rows
    return user_history

def save_log_to_sheet(username, date_str, log_type, exercises):
    sh = get_db()
    ws = sh.worksheet("Logs")
    
    # 1. Check if log exists to update it (instead of duplicating)
    cell = ws.find(username) # Optimization: Find user first
    
    # Simple strategy: Delete old row for this date/user and append new one
    # (Real databases do 'UPDATE', but this is safer for Sheets API)
    
    # Find all rows, identify index to delete
    all_values = ws.get_all_values() # List of lists
    row_to_delete = None
    
    # Skip header (index 0), start checking from index 1 (Row 2)
    for i, row in enumerate(all_values[1:], start=2):
        if row[0] == username and str(row[1]) == date_str:
            row_to_delete = i
            break
            
    if row_to_delete:
        ws.delete_rows(row_to_delete)
        
    # Append new data
    json_data = json.dumps(exercises)
    ws.append_row([username, date_str, log_type, json_data])

def delete_log_from_sheet(username, date_str):
    sh = get_db()
    ws = sh.worksheet("Logs")
    all_values = ws.get_all_values()
    
    for i, row in enumerate(all_values[1:], start=2):
        if row[0] == username and str(row[1]) == date_str:
            ws.delete_rows(i)
            return

# --- LEADERBOARD LOGIC ---
def get_leaderboard_data():
    all_logs = load_history_from_sheet()
    user_counts = {}
    
    for row in all_logs:
        u = row['Username']
        t = row['Type']
        if t != "Rest":
            user_counts[u] = user_counts.get(u, 0) + 1
            
    leaderboard = [{"User": k, "Days": v} for k, v in user_counts.items()]
    return sorted(leaderboard, key=lambda x: x["Days"], reverse=True)


# --- VISUALIZATION (UNCHANGED) ---
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
        
    base = alt.Chart(pd.DataFrame(data)).encode(x=alt.X("weekday:O", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], title=None), y=alt.Y("week:O", axis=None, sort="descending"))
    rects = base.mark_rect(stroke="white", strokeWidth=2).encode(color=alt.Color("status", scale=alt.Scale(domain=["Workout", "Rest", "Missed"], range=["#27ae60", "#2980b9", "#ecf0f1"]), legend=None))
    text = base.mark_text(dx=-12, dy=-12, size=8, align='left').encode(text="day")
    labels = base.mark_text(size=10, fontWeight="bold", color="white").encode(text="label")
    st.altair_chart((rects + text + labels).properties(height=350, title=f"📅 {today.strftime('%B %Y')}"), use_container_width=True)

def plot_consistency(history):
    if not history:
        st.info("Start working out to see your chart!")
        return
    dates = sorted(history.keys())
    start_date = datetime.strptime(dates[0], "%Y-%m-%d")
    end_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    total_days = (end_date - start_date).days + 1
    counts = {"Workouts": 0, "Rest": 0, "Missed": 0}
    current = start_date
    while current <= end_date:
        d_s = current.strftime("%Y-%m-%d")
        l = history.get(d_s)
        if l:
            if l["type"] == "Rest": counts["Rest"] += 1
            else: counts["Workouts"] += 1
        else:
            counts["Missed"] += 1
        current += timedelta(days=1)
    source = pd.DataFrame({'Category': list(counts.keys()), 'Value': list(counts.values())})
    chart = alt.Chart(source).mark_arc(innerRadius=60).encode(theta=alt.Theta("Value", stack=True), color=alt.Color("Category", scale=alt.Scale(domain=['Workouts', 'Rest', 'Missed'], range=['#27ae60', '#2980b9', '#bdc3c7'])), order=alt.Order("Value", sort="descending"))
    st.altair_chart(chart, use_container_width=True)
    st.caption(f"Tracking {total_days} days")


# --- MAIN APP ---
st.set_page_config(page_title="Gym Tracker", page_icon="🏋️", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("🔒 Login (Cloud)")
    
    st.subheader("🏆 Leaderboard")
    try:
        leader_data = get_leaderboard_data()
        if leader_data:
            df_leader = pd.DataFrame(leader_data)
            df_leader.index = df_leader.index + 1
            st.dataframe(df_leader, use_container_width=True)
    except Exception as e:
        st.warning("Could not load leaderboard. Check DB connection.")

    st.divider()

    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        u = st.text_input("User", key="l_u")
        p = st.text_input("Pass", type="password", key="l_p")
        if st.button("Login"):
            if authenticate(u, p):
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("Invalid")
    with tab2:
        nu = st.text_input("New User", key="n_u")
        np = st.text_input("New Pass", type="password", key="n_p")
        if st.button("Create Account"):
            if register_user(nu, np):
                st.success("Created! Login now.")
            else:
                st.error("User exists.")

else:
    user = st.session_state.username
    # Load data freshly from Google Sheets
    history = get_user_history(user)
    
    c1, c2 = st.columns([3, 1])
    with c1: st.title(f"🏋️ {user}")
    with c2: 
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.rerun()

    plot_calendar(history)
    st.divider()

    c1, c2 = st.columns([2, 1])
    with c1:
        st.write("### 📝 Edit Log")
        sel_date = st.date_input("Date", datetime.now(), label_visibility="collapsed")
        d_str = sel_date.strftime("%Y-%m-%d")

    log = history.get(d_str)

    if not log:
        if st.button("💤 Mark Rest"):
            save_log_to_sheet(user, d_str, "Rest", [])
            st.rerun()
        st.write("Or Workout:")
        cols = st.columns(2)
        for i, split in enumerate(TEMPLATES.keys()):
            with cols[i % 2]:
                if st.button(f"💪 {split}", use_container_width=True):
                    exs = [{"name": n, "sets": 3, "reps": 10, "weight": 10.0} for n in TEMPLATES[split]]
                    save_log_to_sheet(user, d_str, split, exs)
                    st.rerun()
    elif log["type"] == "Rest":
        st.info("Rest Day")
        if st.button("Delete"):
            delete_log_from_sheet(user, d_str)
            st.rerun()
    else:
        st.success(f"✅ {log['type']}")
        df = pd.DataFrame(log['exercises'])
        edited = st.data_editor(df, hide_index=True, use_container_width=True)
        if st.button("💾 Save"):
            save_log_to_sheet(user, d_str, log['type'], edited.to_dict('records'))
            st.toast("Saved to Cloud!")
        if st.button("Delete"):
            delete_log_from_sheet(user, d_str)
            st.rerun()

    st.divider()
    plot_consistency(history)