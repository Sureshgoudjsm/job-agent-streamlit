import os
import json
import csv
import io
import pandas as pd
import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

# --- 1. Configuration and Setup ---
load_dotenv()
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except (KeyError, TypeError):
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure it is correctly set up in your environment or a .env file.")
    st.stop()

# --- 2. Session State Initialization ---
if 'current_step' not in st.session_state:
    st.session_state['current_step'] = 0 # 0: Start, 1: Profile, 2: JD, 4: Results
if 'profile_data' not in st.session_state:
    st.session_state['profile_data'] = {}
if 'job_details' not in st.session_state:
    st.session_state['job_details'] = ""
if 'applicant_skills' not in st.session_state:
    st.session_state['applicant_skills'] = ""
if 'extracted_data' not in st.session_state:
    st.session_state['extracted_data'] = None

# --- 3. The AI Prompt (Unchanged) ---
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).
You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences.
**JSON Keys:** "date_contacted", "hr_name", "phone_number", "email_id", "role_position", "recruiter_company", "client_company", "location", "job_type", "mode_of_contact", "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details", "ctc_offered_expected", "status", "next_follow_up_date", "review_notes", "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint".
**Input Text:**
***
{text_input}
***
**JSON Output:**
"""

# --- 4. Core Logic & Calendar Functions (Unchanged) ---
def process_recruiter_text(text_to_process: str) -> dict:
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        clean_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_response)
    except json.JSONDecodeError:
        return {"error": f"AI returned invalid JSON. Raw: {response.text}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

def create_ics_file(details: dict) -> str:
    # This function remains unchanged.
    date_str = details.get("interview_scheduled_date")
    if not date_str or date_str == "Not specified": return ""
    try:
        start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10)
        end_date = start_date + datetime.timedelta(hours=1)
        dt_format = "%Y%m%dT%H%M%S"
        summary = f"Interview: {details.get('role_position', 'Job')} @ {details.get('client_company', 'Client')}"
        description = f"Role: {details.get('role_position', 'N/A')}\\nCompany: {details.get('client_company', 'N/A')}"
        ics_content = f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//AI Job Agent//EN\nBEGIN:VEVENT\nUID:{datetime.datetime.now().strftime(dt_format)}-{hash(summary)}\nDTSTAMP:{datetime.datetime.now().strftime(dt_format)}\nDTSTART:{start_date.strftime(dt_format)}\nDTEND:{end_date.strftime(dt_format)}\nSUMMARY:{summary}\nDESCRIPTION:{description}\nEND:VEVENT\nEND:VCALENDAR"
        return ics_content
    except (ValueError, TypeError):
        return ""

# --- 5. Page Rendering Functions ---

def landing_page():
    st.markdown(
        """
        <style>
        .welcome-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding-top: 5rem; /* Add space from the top nav bar */
        }
        .welcome-title {
            font-size: 3rem;
            font-weight: bold;
        }
        .welcome-subtitle {
            font-size: 1.2rem;
            color: #AAAAAA;
            margin-top: -10px;
            margin-bottom: 30px;
        }
        </style>
        <div class="welcome-container">
            <p class="welcome-title">Welcome to the Job Agent</p>
            <p class="welcome-subtitle">One-click analysis for job fit, skill gaps, and interview prep.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Center the start button
    _, col2, _ = st.columns([3, 2, 3])
    with col2:
        if st.button("✨ START ANALYSIS", use_container_width=True):
            st.session_state['current_step'] = 1
            st.rerun()

def step_one_profile():
    st.markdown("## 1. Your Profile 👤")
    st.info("Input your core professional details for personalized analysis.")
    with st.form(key='profile_form'):
        st.session_state['profile_data']['name'] = st.text_input("Name", st.session_state['profile_data'].get('name', ''))
        st.session_state['profile_data']['email'] = st.text_input("Email", st.session_state['profile_data'].get('email', ''))
        st.session_state['applicant_skills'] = st.text_area("Key Skills/Resume Summary (REQUIRED for Match Score):", st.session_state.get('applicant_skills', ''), height=150, placeholder="e.g., Python (5 years), AWS, Terraform, Docker, SQL...")
        if st.form_submit_button("✅ Save Profile & Continue"):
            if not st.session_state['applicant_skills'].strip():
                st.error("Please enter your Key Skills to enable the Match Score.")
            else:
                st.session_state['current_step'] = 2
                st.rerun()

def step_two_job_desc():
    st.markdown("## 2. Job Description 📄")
    st.info("Paste the full Job Description, recruiter email, and any call notes.")
    st.session_state['job_details'] = st.text_area("Job Details, JD, and Recruiter Notes (REQUIRED):", st.session_state.get('job_details', ''), height=300, placeholder="Paste everything here...")
    _, col2 = st.columns(2)
    with col2:
        if st.button("🚀 Analyze & View Match", use_container_width=True):
            if not st.session_state['job_details'].strip():
                st.error("Please paste the Job Description to proceed.")
            else:
                st.session_state['current_step'] = 4
                st.rerun()

def step_three_results():
    st.markdown("## 3. Analysis & Results ✨")
    if st.session_state.get('extracted_data') is None:
        combined_text = f"--- APPLICANT SKILLS ---\n{st.session_state['applicant_skills']}\n\n--- JOB DETAILS ---\n{st.session_state['job_details']}"
        with st.spinner("🧠 AI is running the analysis..."):
            st.session_state['extracted_data'] = process_recruiter_text(combined_text)
    
    data = st.session_state['extracted_data']
    if "error" in data:
        st.error(data["error"])
        return

    st.success("Analysis complete!")
    st.divider()
    # ... [rest of the results display code is unchanged] ...
    st.markdown("### 🎯 Match Summary")
    col_score, col_prep = st.columns(2)
    with col_score:
        st.metric(label="Overall Match Score", value=data.get('match_score', 'N/A'))
    with col_prep:
        st.markdown(f"**Skill Gap:** {data.get('skill_gap_analysis', 'N/A')}")
        st.markdown(f"**Prep Hint:** {data.get('prep_hint', 'N/A')}")
    st.divider()
    st.markdown("### 📋 Full Extracted Data")
    df = pd.DataFrame([data]).T.rename(columns={0: "Extracted Value"})
    st.dataframe(df, use_container_width=True)
    st.divider()
    if st.button("🔄 Start New Analysis"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- 6. Main App Flow Control ---
def main():
    st.set_page_config(layout="centered", page_title="AI Job Agent")

    # Custom CSS for navigation buttons
    st.markdown("""
        <style>
            /* General button style */
            div[data-testid="stHorizontalBlock"] > div .stButton > button {
                background-color: transparent;
                border: 1px solid #333;
                color: #FFF;
                padding: 8px 16px;
                border-radius: 8px;
            }
            /* Style for the ACTIVE button */
            div[data-testid="stHorizontalBlock"] > div .stButton > button.active-nav {
                background-color: #FFF;
                color: #000;
                border: 1px solid #FFF;
            }
        </style>
    """, unsafe_allow_html=True)

    nav_status = {
        0: {"icon": "🏠", "label": "Start"},
        1: {"icon": "👤", "label": "Your Profile"},
        2: {"icon": "📄", "label": "Job Description"},
        4: {"icon": "✨", "label": "Analysis/Results"},
    }

    # Display Navigation Bar
    cols = st.columns(len(nav_status))
    for i, (step, data) in enumerate(nav_status.items()):
        with cols[i]:
            is_active = (st.session_state.current_step == step)
            button_label = f"{data['icon']} {data['label']}"
            # Use a hack to apply a class to the active button
            if is_active:
                st.markdown(f'<button class="active-nav" style="width:100%;">{button_label}</button>', unsafe_allow_html=True)
            else:
                st.button(button_label, key=f"nav_{step}", use_container_width=True)
    st.divider()

    # Page Routing
    if st.session_state['current_step'] == 0:
        landing_page()
    elif st.session_state['current_step'] == 1:
        step_one_profile()
    elif st.session_state['current_step'] == 2:
        step_two_job_desc()
    elif st.session_state['current_step'] == 4:
        step_three_results()

if __name__ == "__main__":
    main()
