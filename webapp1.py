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
    # Ensure this is replaced with your actual key name if different
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except (KeyError, TypeError):
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure it is correctly set up in your environment or a .env file.")
    st.stop()

# --- 2. Session State Initialization ---
if 'current_step' not in st.session_state:
    st.session_state['current_step'] = 0 # 0: Landing, 1: Your Profile, 2: Job Description, 4: Results
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

**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```json.

**JSON Keys to use:**
- "date_contacted": Date HR contacted you or you applied.
- "hr_name": Name of the HR/recruiter.
- "phone_number": HR’s phone number.
- "email_id": HR’s email address.
- "role_position": Job title for the opportunity.
- "recruiter_company": The staffing/recruitment agency name (if applicable).
- "client_company": The company the job is actually for.
- "location": Job location (e.g., city, remote, hybrid).
- "job_type": Permanent, Contract, Internship, or Freelance.
- "mode_of_contact": How you were contacted (e.g., Call, Email, LinkedIn, Naukri).
- "interview_mode": Online, Offline, or Hybrid.
- "interview_scheduled_date": Date of the interview (if scheduled).
- "round_1_details": Details for the first interview round (e.g., "Technical - Scheduled").
- "round_2_details": Details for the second interview round.
- "ctc_offered_expected": Salary discussed or expected range.
- "status": Current status (e.g., "Awaiting JD", "Interview Scheduled", "Selected", "Rejected").
- "next_follow_up_date": When you plan to follow up.
- "review_notes": Your personal comments or notes.
- "extracted_keywords": A comma-separated list of the 5-10 most critical hard skills and technologies required for the role (e.g., Python, AWS, Kubernetes, React, SQL).
- "match_score": A percentage score (e.g., "85%") representing the fit between the job's required skills and the applicant's skills provided in the input.
- "skill_gap_analysis": A brief, one-sentence summary of the main skill gaps (e.g., "Missing experience in Terraform and advanced SQL queries.").
- "prep_hint": A one-sentence, proactive hint based on the extracted status (e.g., if 'Awaiting JD', output: 'Draft a polite follow-up email asking for the JD by tomorrow.'; if 'Interview Scheduled', output: 'Focus on behavioral questions and a deep dive into the extracted keywords.').

**Input Text (Job Details & Applicant Skills):**
***
{text_input}
***

**JSON Output:**
"""

# --- 4. The Core Logic Function (Unchanged) ---
def process_recruiter_text(text_to_process: str) -> dict:
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        clean_response = response.text.strip()
        if clean_response.startswith('```json'):
            clean_response = clean_response[7:].strip()
        if clean_response.endswith('```'):
            clean_response = clean_response[:-3].strip()
        parsed_json = json.loads(clean_response)
        return parsed_json
    except json.JSONDecodeError:
        return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

# --- 5. iCalendar File Generation Function (Unchanged) ---
def create_ics_file(details: dict) -> str:
    date_str = details.get("interview_scheduled_date", "Not specified")
    role = details.get("role_position", "Job Interview")
    client = details.get("client_company", "Client Company")
    recruiter = details.get("hr_name", "Recruiter")
    mode = details.get("interview_mode", "Mode Not Specified")
    try:
        start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
        end_date = start_date + datetime.timedelta(hours=1)
        dt_format = "%Y%m%dT%H%M%S"
        dt_start = start_date.strftime(dt_format)
        dt_end = end_date.strftime(dt_format)
        dt_stamp = datetime.datetime.now().strftime(dt_format)
    except (ValueError, TypeError):
        return ""

    summary = f"Interview: {role} @ {client}"
    description = (
        f"Role: {role}\\n"
        f"Company: {client}\\n"
        f"Recruiter: {recruiter}\\n"
        f"Round 1 Details: {details.get('round_1_details', 'N/A')}\\n"
        f"Mode: {mode}\\n"
        f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
    )

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AI Job Agent//EN
BEGIN:VEVENT
UID:{dt_stamp}-{hash(summary)}
DTSTAMP:{dt_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{summary}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR"""
    return ics_content

# --- 6. Streamlit Page Functions ---

# --- [MODIFIED] This is the new landing page function ---
def landing_page():
    st.markdown(
        """
        <style>
        /* Center the main container vertically */
        .stApp {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        /* Style for the clickable node */
        .central-node {
            border: 2px solid #333;
            border-radius: 15px;
            padding: 40px 60px;
            text-align: center;
            transition: all 0.3s ease;
            cursor: pointer;
            background-color: #1E1E1E; /* Slightly different background */
        }
        .central-node:hover {
            border-color: #007BFF;
            transform: scale(1.05);
            box-shadow: 0 0 15px rgba(0, 123, 255, 0.5);
        }
        .main-title {
            font-size: 3rem;
            font-weight: bold;
            margin-bottom: 10px;
            color: white;
        }
        .tagline {
            font-size: 1.3rem;
            color: #AAAAAA;
        }
        /* This is a trick to make a div clickable in Streamlit */
        /* We make the button itself invisible and cover the whole area */
        div[data-testid="stButton"] > button[kind="secondary"] {
            background-color: transparent;
            border: none;
            padding: 0;
            margin: 0;
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
            z-index: 1; /* Button is clickable */
        }
        .clickable-container {
            position: relative; /* Needed for the button trick */
            display: flex;
            justify-content: center;
            align-items: center;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Use columns to center the clickable element
    _, col_center, _ = st.columns()

    with col_center:
        # This container holds both the visible div and the invisible button
        st.markdown('<div class="clickable-container">', unsafe_allow_html=True)

        # The invisible button that triggers the action
        if st.button(" ", key="start_button"): # The button label is a space
            st.session_state['current_step'] = 1
            st.rerun()

        # The visible HTML content that the user sees and clicks on
        st.markdown(
            """
            <div class="central-node">
                <div class="main-title">Job Agent</div>
                <div class="tagline">Match, Analyze, Prepare</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)


# --- Remaining Page Functions (Unchanged) ---
def step_one_profile():
    st.markdown("## 1. Your Profile 👤")
    st.info("Input your core professional details. This helps the AI personalize the match analysis.")

    with st.form(key='profile_form'):
        st.session_state['profile_data']['name'] = st.text_input("Name", value=st.session_state['profile_data'].get('name', ''))
        st.session_state['profile_data']['email'] = st.text_input("Email", value=st.session_state['profile_data'].get('email', ''))
        st.session_state['profile_data']['linkedin'] = st.text_input("LinkedIn URL (Optional)", value=st.session_state['profile_data'].get('linkedin', ''))
        st.session_state['applicant_skills'] = st.text_area(
            "Key Skills/Resume Summary (REQUIRED for Match Score):",
            value=st.session_state['applicant_skills'],
            height=150,
            placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification."
        )

        st.markdown("---")
        if st.form_submit_button("✅ Save Profile & Go to Job Description"):
            if not st.session_state['applicant_skills'].strip():
                st.error("Please enter your Key Skills/Resume Summary to enable the Match Score.")
            else:
                st.session_state['current_step'] = 2
                st.rerun()

    st.button("⬅️ Back to Start", on_click=lambda: st.session_state.update({'current_step': 0}), key='back1')

def step_two_job_desc():
    st.markdown("## 2. Job Description 📄")
    st.info("Paste the full Job Description, recruiter email, and any call notes here.")

    recruiter_details = st.text_area(
        "Job Details, JD, and Recruiter Notes (REQUIRED):",
        value=st.session_state['job_details'],
        height=300,
        placeholder="Paste the entire Job Description, contact email, and any notes from your recruiter call (e.g., 'Spoke with Jane Doe, Interview set for next week, salary 150k')."
    )

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Back to Profile", key='back2'):
            st.session_state['current_step'] = 1
            st.rerun()
    with col2:
        if st.button("🚀 Analyze & View Match", key='submit_analysis'):
            if not recruiter_details.strip():
                st.error("Please paste the Job Description/Details to proceed.")
            else:
                st.session_state['job_details'] = recruiter_details
                st.session_state['current_step'] = 4
                st.rerun()

def step_three_results():
    st.markdown("## 3. Skill Assessment & Final Analysis ✨")

    if st.session_state.get('extracted_data') is None:
        combined_text = (
            f"--- APPLICANT SKILLS ---\n{st.session_state['applicant_skills']}\n\n"
            f"--- JOB DETAILS ---\n{st.session_state['job_details']}"
        )
        with st.spinner("🧠 The AI is running the match analysis and extracting data..."):
            st.session_state['extracted_data'] = process_recruiter_text(combined_text)

    structured_data_dict = st.session_state['extracted_data']

    if "error" in structured_data_dict:
        st.error(structured_data_dict["error"])
        st.button("↩️ Go Back to Edit Job Details", on_click=lambda: st.session_state.update({'current_step': 2, 'extracted_data': None}), key='back_from_error')
        return

    st.success("Analysis complete! Review your Match Score and extracted job data below.")
    st.divider()

    st.markdown("### 🎯 Match Summary")
    col_score, col_prep = st.columns()
    with col_score:
        score = structured_data_dict.get('match_score', 'N/A')
        st.markdown(f"""
        <div style='text-align: center; border: 3px solid #007BFF; padding: 15px; border-radius: 10px; background-color: #0a1931;'>
            <p style='font-size: 1.2rem; margin: 0; color: #AAAAAA;'>Overall Match Score</p>
            <h1 style='font-size: 3rem; margin: 0; color: #007BFF;'>{score}</h1>
        </div>
        """, unsafe_allow_html=True)

    with col_prep:
        st.markdown(f"**Skill Gap Analysis:** {structured_data_dict.get('skill_gap_analysis', 'No gaps identified.')}")
        st.markdown(f"**Proactive Prep Hint:** {structured_data_dict.get('prep_hint', 'No specific hint available.')}")

    st.divider()
    st.markdown("### 📋 Full Extracted Job Data")
    df_display = pd.DataFrame([structured_data_dict]).T
    df_display.columns = ["Extracted Value"]
    st.dataframe(df_display, use_container_width=True)

    st.divider()
    st.markdown("### 💾 Downloads")
    col_ics, col_csv = st.columns(2)

    if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
        ics_data = create_ics_file(structured_data_dict)
        if ics_data:
            with col_ics:
                st.download_button(
                    label="📅 Download Calendar Event (.ics)",
                    data=ics_data,
                    file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
                    mime="text/calendar"
                )

    output = io.StringIO()
    required_headers = [
        "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
        "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
        "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
        "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
        "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
    ]
    writer = csv.DictWriter(output, fieldnames=required_headers, extrasaction='ignore')
    writer.writeheader()
    row_to_write = {key: structured_data_dict.get(key, "") for key in required_headers}
    writer.writerow(row_to_write)
    csv_data = output.getvalue()

    with col_csv:
        st.download_button(
            label="📄 Download Job Tracker (.csv)",
            data=csv_data,
            file_name="job_details_extracted.csv",
            mime="text/csv"
        )

    st.divider()
    if st.button("🔄 Start New Analysis", key='new_analysis_btn'):
        # Reset all session state variables for a clean start
        st.session_state['current_step'] = 0
        st.session_state['profile_data'] = {}
        st.session_state['job_details'] = ""
        st.session_state['applicant_skills'] = ""
        st.session_state['extracted_data'] = None
        st.rerun()

# --- 7. Main App Flow Control ---
def main():
    st.set_page_config(layout="wide", page_title="AI Job Agent")

    # The navigation bar is only shown after the landing page
    if st.session_state['current_step'] > 0:
        nav_status = {
            0: {"icon": "🏠", "label": "Start"},
            1: {"icon": "👤", "label": "Your Profile"},
            2: {"icon": "📄", "label": "Job Description"},
            4: {"icon": "✨", "label": "Analysis/Results"},
        }
        
        # Use st.columns to create a horizontal navigation bar
        cols = st.columns(len(nav_status))
        for i, (step, data) in enumerate(nav_status.items()):
            with cols[i]:
                # Use a button for navigation
                if st.button(f"{data['icon']} {data['label']}", key=f"nav_{step}", use_container_width=True):
                    # Only allow navigation to previous steps
                    if step < st.session_state['current_step']:
                        st.session_state['current_step'] = step
                        st.session_state['extracted_data'] = None # Clear results if going back
                        st.rerun()
        st.divider()

    # Routing logic based on the session state
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
