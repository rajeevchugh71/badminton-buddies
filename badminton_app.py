import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- PART 1: SETUP (Google Sheets Connection) ---
# We use the "Secrets" we saved in Streamlit Cloud
# This function connects to the sheet safely.
def get_db():
    # 1. Access the secrets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["gcp_service_account"]) # Reads the secret you saved
    except Exception as e:
        st.error("Google Cloud credentials not found. Please set up the secrets correctly.")
        st.stop()

    # 2. Create the connection
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
    except Exception as e:
        st.error("Failed to authorize Google Sheets client. Check your credentials.")
        st.stop()

   
    # 3. Open the sheet
    # Make sure your Google Sheet is named EXACTLY "Badminton DB"
    try:
        sheet = client.open("Badminton DB").sheet1 
    except Exception as e:
        st.error("Could not find the Google Sheet named 'Badminton DB'. Please create it and share access with the bot email.")
        st.stop()

    return sheet

# Helper to read data safely
def load_data():
    sheet = get_db()
    # We expect the data in the first cell as a giant text blob (simplest way to migrate)
    # Ideally, we would use rows/cols, but to keep your code logic same, 
    # we will store the JSON string in Cell A1.
    
    try:
        raw_data = sheet.acell('A1').value
        if not raw_data:
            # If empty, return default structure
            return {"buddies": [], "sessions": []}
        return json.loads(raw_data)
    except Exception as e:
        return {"buddies": [], "sessions": []}

# Helper to save data
def save_data(data):
    sheet = get_db()
    # Convert our data back to text and save in Cell A1
    json_str = json.dumps(data, ensure_ascii=False)
    sheet.update_acell('A1', json_str)

# Load data once at the start
try:
    data = load_data()
except Exception as e:
    st.error("Could not connect to Google Sheet. Did you share 'Badminton DB' with the bot email?")
    st.stop()

# --- PART 2: THE SIDEBAR (Login) ---
st.title("🏸 Badminton Buddies")

user_role = st.sidebar.selectbox("Login As:", ["Guest", "Admin", "Reporting User"])
password = ""

if user_role in ["Admin", "Reporting User"]:
    password = st.sidebar.text_input("Password", type="password")

# Check password
authorized = False
if user_role == "Admin" and password == "admin123":
    authorized = True
elif user_role == "Reporting User" and password == "report123":
    authorized = True
elif user_role != "Guest":
    st.sidebar.error("Wrong password")

# --- PART 3: ADMIN AREA (Record/Edit) ---
if user_role == "Admin" and authorized:
    st.header("Admin Dashboard")
    
    # A. Manage Buddies
    with st.expander("Manage Buddy List"):
        st.write("### Add Buddy")
        new_buddy = st.text_input("Enter Name:").strip()
        
        if st.button("Add Buddy"):
            if not new_buddy:
                st.error("Name cannot be empty.")
            elif new_buddy in data["buddies"]:
                st.error(f"⚠️ '{new_buddy}' is already in the list!")
            else:
                data["buddies"].append(new_buddy)
                save_data(data)
                st.success(f"Added {new_buddy}!")
        
        st.write("---")
        st.write("### Remove Buddy")
        buddy_to_remove = st.selectbox("Select Buddy to Remove", ["Select..."] + data["buddies"])
        
        if buddy_to_remove != "Select...":
            games_played = 0
            for s in data["sessions"]:
                if buddy_to_remove in s["attendees"]:
                    games_played += 1
            
            if games_played > 0:
                st.warning(f"⚠️ Warning: {buddy_to_remove} is recorded in {games_played} past sessions.")
            
            if st.button(f"Confirm Delete '{buddy_to_remove}'"):
                data["buddies"].remove(buddy_to_remove)
                save_data(data)
                st.success(f"Removed {buddy_to_remove}")
                st.rerun()

    st.write("---")

    # B. Record or Edit a Session
    st.subheader("Record / Edit Session")
    
    session_date = st.date_input("Select Date", datetime.today())
    date_str = str(session_date)

    existing_session = next((s for s in data["sessions"] if s["date"] == date_str), None)

    if existing_session:
        st.info(f"📅 Editing record for {date_str}.")
        default_cost = float(existing_session["total_cost"])
        default_attendees = existing_session["attendees"]
        button_label = "Update Session"
    else:
        st.write(f"🆕 Creating NEW session for {date_str}.")
        default_cost = 13.10
        default_attendees = []
        button_label = "Save Session"

    court_cost = st.number_input("Court Cost (€)", value=default_cost, step=0.5)
    
    st.write("Who played?")
    attendees = []
    
    cols = st.columns(2)
    for index, buddy in enumerate(data["buddies"]):
        is_checked = buddy in default_attendees
        unique_key = f"{date_str}_{buddy}"
        
        with cols[index % 2]:
            if st.checkbox(buddy, key=unique_key, value=is_checked):
                attendees.append(buddy)
            
    if st.button(button_label):
        if len(attendees) > 0:
            if existing_session:
                data["sessions"].remove(existing_session)

            cost_per_person = court_cost / len(attendees)
            
            new_session = {
                "date": date_str,
                "month": session_date.strftime("%Y-%m"),
                "total_cost": court_cost,
                "attendees": attendees,
                "cost_per_person": cost_per_person
            }
            
            data["sessions"].append(new_session)
            data["sessions"] = sorted(data["sessions"], key=lambda x: x['date'])
            
            save_data(data)
            st.success(f"Session for {date_str} saved to Google Sheets!")
            st.rerun()
        else:
            st.error("Select at least one buddy.")

# --- PART 4: REPORTING AREA ---
if (user_role == "Reporting User" or user_role == "Admin") and authorized:
    st.write("---")
    st.header("💰 Cost Reports")
    
    available_months = sorted(list(set(s['month'] for s in data['sessions'])), reverse=True)
    
    if not available_months:
        st.info("No games played yet.")
    else:
        selected_month = st.selectbox("Select Month", available_months)
        month_sessions = [s for s in data['sessions'] if s['month'] == selected_month]
        
        if month_sessions:
            st.subheader(f"Summary for {selected_month}")
            report_card = {}
            
            for session in month_sessions:
                for player in session['attendees']:
                    if player not in report_card:
                        report_card[player] = {"Games": 0, "Owes (€)": 0.0}
                    report_card[player]["Games"] += 1
                    report_card[player]["Owes (€)"] += session['cost_per_person']
            
            df_summary = pd.DataFrame.from_dict(report_card, orient='index')
            df_summary = df_summary.round(2)
            st.table(df_summary)
            
            total_month_cost = sum(s['total_cost'] for s in month_sessions)
            st.caption(f"Total Court Fees Paid this month: {total_month_cost}€")

            st.write("---")
            with st.expander("View Detailed Session History", expanded=False):
                history_data = []
                for session in month_sessions:
                    history_data.append({
                        "Date": session["date"],
                        "Total Cost (€)": session["total_cost"],
                        "Cost/Person (€)": round(session["cost_per_person"], 2),
                        "Attendees": ", ".join(session["attendees"])
                    })
                
                df_history = pd.DataFrame(history_data)
                st.table(df_history)
        else:
            st.warning("No data found for this month.")

if user_role == "Guest":
    st.write("Please log in to view data.")