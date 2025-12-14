import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os

# --- PART 1: SETUP (The Database) ---
# We will use a simple file called 'data.json' to store everything.
DB_FILE = 'badminton_data.json'

def load_data():
    if not os.path.exists(DB_FILE):
        # Create empty data if file doesn't exist
        return {"buddies": [], "sessions": []}
    with open(DB_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f)

data = load_data()

# --- PART 2: THE SIDEBAR (Login) ---
st.title("🏸 Badminton Buddies")

# Simple Login System
user_role = st.sidebar.selectbox("Login As:", ["Guest", "Admin", "Reporting User"])
password = ""

if user_role in ["Admin", "Reporting User"]:
    password = st.sidebar.text_input("Password", type="password")

# Check password (In a real app, use a secure system. This is for demo.)
authorized = False
if user_role == "Admin" and password == "admin123":
    authorized = True
elif user_role == "Reporting User" and password == "report123":
    authorized = True
elif user_role != "Guest":
    st.sidebar.error("Wrong password")

# --- PART 3: ADMIN AREA ---
if user_role == "Admin" and authorized:
    st.header("Admin Dashboard")
    
    # A. Manage Buddies
    st.subheader("1. Manage Buddies")
    new_buddy = st.text_input("Add a new Buddy Name:")
    if st.button("Add Buddy"):
        if new_buddy and new_buddy not in data["buddies"]:
            data["buddies"].append(new_buddy)
            save_data(data)
            st.success(f"Added {new_buddy}!")
    
    # Show list to delete
    buddy_to_remove = st.selectbox("Remove a Buddy", ["Select..."] + data["buddies"])
    if st.button("Remove Buddy"):
        if buddy_to_remove != "Select...":
            data["buddies"].remove(buddy_to_remove)
            save_data(data)
            st.experimental_rerun()

    st.write("---")

    # B. Record a Session
    st.subheader("2. Record Sunday Session")
    session_date = st.date_input("Date", datetime.today())
    court_cost = st.number_input("Court Cost (€)", value=13.1, step=0.5)
    
    st.write("Who played today?")
    # Create checkboxes for every buddy
    attendees = []
    for buddy in data["buddies"]:
        if st.checkbox(buddy, key=buddy):
            attendees.append(buddy)
            
    if st.button("Save Session"):
        if len(attendees) > 0:
            # Calculate cost per person strictly for this session
            cost_per_person = court_cost / len(attendees)
            
            new_session = {
                "date": str(session_date),
                "month": session_date.strftime("%Y-%m"), # Saves as "2025-12"
                "total_cost": court_cost,
                "attendees": attendees,
                "cost_per_person": cost_per_person
            }
            data["sessions"].append(new_session)
            save_data(data)
            st.success("Session Saved!")
        else:
            st.error("Select at least one buddy.")

# --- PART 4: REPORTING AREA ---
if (user_role == "Reporting User" or user_role == "Admin") and authorized:
    st.header("💰 Cost Reports")
    
    # Get list of months from the saved sessions
    available_months = sorted(list(set(s['month'] for s in data['sessions'])))
    
    if not available_months:
        st.info("No games played yet.")
    else:
        selected_month = st.selectbox("Select Month", available_months)
        
        if st.button("Generate Report") or selected_month:
            # 1. Filter sessions for that month
            month_sessions = [s for s in data['sessions'] if s['month'] == selected_month]
            
            # 2. Calculate totals per buddy
            report_card = {}
            total_games_count = 0
            
            for session in month_sessions:
                total_games_count += 1
                for player in session['attendees']:
                    if player not in report_card:
                        report_card[player] = {"Games": 0, "Owes (€)": 0.0}
                    
                    report_card[player]["Games"] += 1
                    report_card[player]["Owes (€)"] += session['cost_per_person']
            
            # 3. Display as a clean table
            if report_card:
                df = pd.DataFrame.from_dict(report_card, orient='index')
                df = df.round(2) # Round to 2 decimal places
                st.table(df)
                
                total_month_cost = sum(s['total_cost'] for s in month_sessions)
                st.write(f"**Total Court Fees Paid this month: {total_month_cost}€**")
            else:
                st.write("No games found for this month.")

# --- PART 5: GUEST VIEW ---
if user_role == "Guest":
    st.write("Please log in to view data.")