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
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

# --- 2. Session State Initialization ---
# This simulates the multi-step navigation of your mind map
if 'current_step' not in st.session_state:
    st.session_state['current_step'] = 0 # 0: Landing, 1: Your Profile, 2: Job Description, 3: Skill Assessment/Submit, 4: Results
if 'profile_data' not in st.session_state:
    st.session_state['profile_data'] = {}
if 'job_details' not in st.session_state:
    st.session_state['job_details'] = ""
if 'applicant_skills' not in st.session_state:
    st.session_state['applicant_skills'] = ""
if 'extracted_data' not in st.session_state:
    st.session_state['extracted_data'] = None

# --- 3. The AI Prompt (Unchanged) ---
# NOTE: The combined text input structure for the model is designed to use all stored data.
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```

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
        # Clean response: remove surrounding code fences that AI sometimes adds despite instructions
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
    # Function body remains the same as your original code
    date_str = details.get("interview_scheduled_date", "Not specified")
    role = details.get("role_position", "Job Interview")
    client = details.get("client_company", "Client Company")
    recruiter = details.get("hr_name", "Recruiter")
    mode = details.get("interview_mode", "Mode Not Specified")
    try:
        # Assuming date_str is in YYYY-MM-DD format as per prompt instruction
        start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
        end_date = start_date + datetime.timedelta(hours=1)
        dt_format = "%Y%m%dT%H%M%S"
        dt_start = start_date.strftime(dt_format)
        dt_end = end_date.strftime(dt_format)
        dt_stamp = datetime.datetime.now().strftime(dt_format)
    except ValueError:
        return ""

    summary = f"Interview: {role} @ {client}"
    description = (
        f"Role: {role}\n"
        f"Company: {client}\n"
        f"Recruiter: {recruiter}\n"
        f"Round 1 Details: {details.get('round_1_details', 'N/A')}\n"
        f"Mode: {mode}\n"
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
    return ics_content.replace('\n', '\r\n')

# --- 6. Streamlit Page Functions (Simulating Mind Map Nodes) ---

def landing_page():
    st.markdown(
        """
        <style>
        .center-content-top {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start; /* Align to the top */
            height: 30vh; /* Adjust height to control vertical position */
            text-align: center;
            padding-top: 5vh; /* Push content down slightly from the very top */
        }
        .mind-map-node {
            font-size: 2.5em;
            font-weight: 700;
            padding: 20px 40px;
            border-radius: 15px;
            color: white;
            background-color: #4CAF50; /* Green Node */
            cursor: pointer;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            transition: all 0.3s ease;
        }
        .mind-map-node:hover {
            background-color: #45a049;
            transform: scale(1.05);
        }
        </style>
        <div class="center-content-top">
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("## 🤖 Welcome to the Job Agent")
    st.markdown("One-click analysis for job fit, skill gaps, and interview prep.")

    # Using a centered button to simulate the initial "Job Agent" node
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("✨ START ANALYSIS", key='start_btn', help="Click to expand the main Job Agent Node"):
            st.session_state['current_step'] = 1
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

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

    st.button("⬅️ Back to Start", on_click=lambda: st.session_state.update({'current_step': 0, 'extracted_data': None}), key='back1')

def step_two_job_desc():
    st.markdown("## 2. Job Description 📄")
    st.info("Paste the full Job Description, recruiter email, and any call notes here.")

    # Combine the input for simplicity, matching the original combined_text logic
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
            st.session_state['extracted_data'] = None
            st.rerun()
    with col2:
        if st.button("🚀 Analyze & View Match", key='submit_analysis'):
            if not recruiter_details.strip():
                st.error("Please paste the Job Description/Details to proceed.")
            else:
                st.session_state['job_details'] = recruiter_details
                st.session_state['current_step'] = 4 # Skip "Skill Assessment" (Step 3) since it's now automated.
                st.rerun()

# This function combines the old skill assessment (which was automated) and the final results display.
def step_three_results():
    st.markdown("## 3. Skill Assessment & Final Analysis ✨")
    
    # 1. Generate Analysis if not already done
    if st.session_state['extracted_data'] is None:
        # Combine all necessary data for the AI call
        combined_text = (
            f"--- APPLICANT SKILLS ---\n{st.session_state['applicant_skills']}\n\n"
            f"--- JOB DETAILS ---\n{st.session_state['job_details']}"
        )
        
        with st.spinner("🧠 The AI is running the match analysis and extracting data..."):
            st.session_state['extracted_data'] = structured_data_dict = process_recruiter_text(combined_text)
    
    structured_data_dict = st.session_state['extracted_data']

    if "error" in structured_data_dict:
        st.error(structured_data_dict["error"])
        st.button("↩️ Go Back to Edit Job Details", on_click=lambda: st.session_state.update({'current_step': 2}), key='back_from_error')
        return

    st.success("Analysis complete! Review your Match Score and extracted job data below.")
    st.divider()

    # --- Side-by-Side Layout for Final Output ---
    st.markdown("### 🎯 Match Summary")
    
    col_score, col_prep = st.columns([1, 2])
    
    with col_score:
        score = structured_data_dict.get('match_score', 'N/A')
        # Use HTML/Markdown for a prominent score display
        st.markdown(f"""
        <div style='text-align: center; border: 3px solid #007BFF; padding: 15px; border-radius: 10px; background-color: #e9f5ff;'>
            <p style='font-size: 1.2rem; margin: 0;'>Overall Match Score</p>
            <h1 style='font-size: 3rem; margin: 0; color: #007BFF;'>{score}</h1>
        </div>
        """, unsafe_allow_html=True)

    with col_prep:
        st.markdown(f"**Skill Gap Analysis:** {structured_data_dict.get('skill_gap_analysis', 'No gaps identified.')}")
        st.markdown(f"**Proactive Prep Hint:** {structured_data_dict.get('prep_hint', 'No specific hint available.')}")
    
    st.divider()

    st.markdown("### 📋 Full Extracted Job Data")

    # Display Results in a DataFrame
    df_display = pd.DataFrame([structured_data_dict]).T
    df_display.columns = ["Extracted Value"]
    st.dataframe(df_display, use_container_width=True)

    # --- Download Section ---
    st.divider()
    st.markdown("### 💾 Downloads")
    col_ics, col_csv = st.columns(2)

    # iCalendar Download Button
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

    # CSV Download Button
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
    # Reset button
    if st.button("🔄 Start New Analysis", key='new_analysis_btn'):
        st.session_state['current_step'] = 0
        st.session_state['extracted_data'] = None
        st.rerun()

# --- 7. Main App Flow Control ---
def main():
    # Force a cleaner look
    st.set_page_config(layout="centered", page_title="Job Agent")
    
    # Navigation Display (Mimicking the Mind Map Nodes)
    nav_status = {
        0: {"icon": "🏠", "label": "Start", "color": "#007BFF"},
        1: {"icon": "👤", "label": "Your Profile", "color": "#28A745"},
        2: {"icon": "📄", "label": "Job Description", "color": "#FFC107"},
        4: {"icon": "✨", "label": "Analysis/Results", "color": "#DC3545"},
    }

    # Display Nav bar horizontally
    cols = st.columns(len(nav_status))
    for i, (step, data) in enumerate(nav_status.items()):
        current = st.session_state['current_step']
        # The color logic here needs to be slightly smarter to show active vs. completed steps
        if current == step:
            color = data['color'] # Active step
        elif current > step:
            color = "#6c757d" # Completed step (a subdued grey)
        else:
            color = "#AAAAAA" # Future step
        
        with cols[i]:
            # Only allow clicking on steps that are current or completed to prevent skipping ahead
            if step <= current: # Allow navigating back to completed/current steps
                if st.button(f"{data['icon']} {data['label']}", key=f'nav_btn_{step}'):
                    st.session_state['current_step'] = step
                    st.session_state['extracted_data'] = None # Clear results if navigating back
                    st.rerun()
            else:
                 # Display non-clickable text for future steps
                 st.markdown(f"<p style='color:{color}; text-align:center;'>{data['icon']} {data['label']}</p>", unsafe_allow_html=True)
                 
    st.divider()

    # Routing logic based on the session state
    if st.session_state['current_step'] == 0:
        landing_page()
    elif st.session_state['current_step'] == 1:
        step_one_profile()
    elif st.session_state['current_step'] == 2:
        step_two_job_desc()
    elif st.session_state['current_step'] == 4:
        # Step 3 (Skill Assessment) is now the automatic calculation/display in Step 4.
        step_three_results()

if __name__ == "__main__":
    main()

# -------------------------------------------------------------------------------------------------------------------

# import os
# import json
# import csv
# import io
# import pandas as pd
# import datetime
# from dotenv import load_dotenv
# import google.generativeai as genai
# import streamlit as st

# # --- 1. Configuration and Setup (Unchanged) ---
# load_dotenv()
# try:
#     # Ensure this is replaced with your actual key name if different
#     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# except KeyError:
#     st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
#     st.stop()

# # --- 2. Session State Initialization (Unchanged) ---
# if 'current_step' not in st.session_state:
#     st.session_state['current_step'] = 0 # 0: Landing, 1: Your Profile, 2: Job Description, 3: Skill Assessment/Submit, 4: Results
# if 'profile_data' not in st.session_state:
#     st.session_state['profile_data'] = {}
# if 'job_details' not in st.session_state:
#     st.session_state['job_details'] = ""
# if 'applicant_skills' not in st.session_state:
#     st.session_state['applicant_skills'] = ""
# if 'extracted_data' not in st.session_state:
#     st.session_state['extracted_data'] = None

# # --- 3. The AI Prompt (Unchanged) ---
# EXTRACTION_PROMPT = """
# You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

# **CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```

# **JSON Keys to use:**
# - "date_contacted": Date HR contacted you or you applied.
# - "hr_name": Name of the HR/recruiter.
# - "phone_number": HR’s phone number.
# - "email_id": HR’s email address.
# - "role_position": Job title for the opportunity.
# - "recruiter_company": The staffing/recruitment agency name (if applicable).
# - "client_company": The company the job is actually for.
# - "location": Job location (e.g., city, remote, hybrid).
# - "job_type": Permanent, Contract, Internship, or Freelance.
# - "mode_of_contact": How you were contacted (e.g., Call, Email, LinkedIn, Naukri).
# - "interview_mode": Online, Offline, or Hybrid.
# - "interview_scheduled_date": Date of the interview (if scheduled).
# - "round_1_details": Details for the first interview round (e.g., "Technical - Scheduled").
# - "round_2_details": Details for the second interview round.
# - "ctc_offered_expected": Salary discussed or expected range.
# - "status": Current status (e.g., "Awaiting JD", "Interview Scheduled", "Selected", "Rejected").
# - "next_follow_up_date": When you plan to follow up.
# - "review_notes": Your personal comments or notes.
# - "extracted_keywords": A comma-separated list of the 5-10 most critical hard skills and technologies required for the role (e.g., Python, AWS, Kubernetes, React, SQL).
# - "match_score": A percentage score (e.g., "85%") representing the fit between the job's required skills and the applicant's skills provided in the input.
# - "skill_gap_analysis": A brief, one-sentence summary of the main skill gaps (e.g., "Missing experience in Terraform and advanced SQL queries.").
# - "prep_hint": A one-sentence, proactive hint based on the extracted status (e.g., if 'Awaiting JD', output: 'Draft a polite follow-up email asking for the JD by tomorrow.'; if 'Interview Scheduled', output: 'Focus on behavioral questions and a deep dive into the extracted keywords.').

# **Input Text (Job Details & Applicant Skills):**
# ***
# {text_input}
# ***

# **JSON Output:**
# """

# # --- 4. The Core Logic Function (Unchanged) ---
# def process_recruiter_text(text_to_process: str) -> dict:
#     model = genai.GenerativeModel('gemini-2.5-flash')
#     prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
#     try:
#         response = model.generate_content(prompt_with_input)
#         # Clean response: remove surrounding code fences that AI sometimes adds despite instructions
#         clean_response = response.text.strip()
#         if clean_response.startswith('```json'):
#             clean_response = clean_response[7:].strip()
#         if clean_response.endswith('```'):
#             clean_response = clean_response[:-3].strip()
                                                      
#         parsed_json = json.loads(clean_response)
#         return parsed_json
#     except json.JSONDecodeError:
#         return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
#     except Exception as e:
#         return {"error": f"An error occurred: {e}"}

# # --- 5. iCalendar File Generation Function (Unchanged) ---
# def create_ics_file(details: dict) -> str:
#     # Function body remains the same as your original code
#     date_str = details.get("interview_scheduled_date", "Not specified")
#     role = details.get("role_position", "Job Interview")
#     client = details.get("client_company", "Client Company")
#     recruiter = details.get("hr_name", "Recruiter")
#     mode = details.get("interview_mode", "Mode Not Specified")
#     try:
#         # Assuming date_str is in YYYY-MM-DD format as per prompt instruction
#         start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
#         end_date = start_date + datetime.timedelta(hours=1)
#         dt_format = "%Y%m%dT%H%M%S"
#         dt_start = start_date.strftime(dt_format)
#         dt_end = end_date.strftime(dt_format)
#         dt_stamp = datetime.datetime.now().strftime(dt_format)
#     except ValueError:
#         return ""

#     summary = f"Interview: {role} @ {client}"
#     description = (
#         f"Role: {role}\n"
#         f"Company: {client}\n"
#         f"Recruiter: {recruiter}\n"
#         f"Round 1 Details: {details.get('round_1_details', 'N/A')}\n"
#         f"Mode: {mode}\n"
#         f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
#     )

#     ics_content = f"""BEGIN:VCALENDAR
# VERSION:2.0
# PRODID:-//AI Job Agent//EN
# BEGIN:VEVENT
# UID:{dt_stamp}-{hash(summary)}
# DTSTAMP:{dt_stamp}
# DTSTART:{dt_start}
# DTEND:{dt_end}
# SUMMARY:{summary}
# DESCRIPTION:{description}
# END:VEVENT
# END:VCALENDAR"""
#     return ics_content.replace('\n', '\r\n')

# # --- 6. Streamlit Page Functions (Simulating Mind Map Nodes) ---

# def landing_page():
#     st.markdown(
#         """
#         <style>
#         .center-text-full {
#             display: flex;
#             flex-direction: column;
#             align-items: center;
#             justify-content: center;
#             height: 60vh; /* Adjust height to use the space better */
#             text-align: center;
#         }
#         /* Style for the central element in the red circle area */
#         .central-job-agent {
#             font-size: 5em; /* Large icon size */
#             color: #007BFF; /* Primary color */
#             margin-bottom: 20px;
#             animation: pulse 2s infinite; /* Gentle animation to draw attention */
#         }
#         .central-tagline {
#             font-size: 1.5rem;
#             color: #AAAAAA;
#             margin-bottom: 40px;
#         }
#         @keyframes pulse {
#             0% { transform: scale(1); }
#             50% { transform: scale(1.05); }
#             100% { transform: scale(1); }
#         }
#         </style>
#         <div class="center-text-full">
#             <div class="central-job-agent">
#                 🤖
#             </div>
#             <div class="central-tagline">
#                 AI Job Agent: Match, Analyze, Prepare.
#             </div>
#         """,
#         unsafe_allow_html=True
#     )
    
#     # Place the main heading and start button below the central icon
#     st.markdown("## Welcome to the Job Agent")
#     st.markdown("One-click analysis for job fit, skill gaps, and interview prep.")

#     # Using a centered button
#     col1, col2, col3 = st.columns([1, 1, 1])
#     with col2:
#         if st.button("✨ START ANALYSIS", key='start_btn', help="Click to expand the main Job Agent Node", use_container_width=True):
#             st.session_state['current_step'] = 1
#             st.rerun()

#     st.markdown("</div>", unsafe_allow_html=True)


# # --- Remaining Page Functions (Unchanged) ---
# def step_one_profile():
#     st.markdown("## 1. Your Profile 👤")
#     st.info("Input your core professional details. This helps the AI personalize the match analysis.")

#     with st.form(key='profile_form'):
#         st.session_state['profile_data']['name'] = st.text_input("Name", value=st.session_state['profile_data'].get('name', ''))
#         st.session_state['profile_data']['email'] = st.text_input("Email", value=st.session_state['profile_data'].get('email', ''))
#         st.session_state['profile_data']['linkedin'] = st.text_input("LinkedIn URL (Optional)", value=st.session_state['profile_data'].get('linkedin', ''))
#         st.session_state['applicant_skills'] = st.text_area(
#             "Key Skills/Resume Summary (REQUIRED for Match Score):", 
#             value=st.session_state['applicant_skills'], 
#             height=150,
#             placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification."
#         )

#         st.markdown("---")
#         if st.form_submit_button("✅ Save Profile & Go to Job Description"):
#             if not st.session_state['applicant_skills'].strip():
#                 st.error("Please enter your Key Skills/Resume Summary to enable the Match Score.")
#             else:
#                 st.session_state['current_step'] = 2
#                 st.rerun()

#     st.button("⬅️ Back to Start", on_click=lambda: st.session_state.update({'current_step': 0}), key='back1')

# def step_two_job_desc():
#     st.markdown("## 2. Job Description 📄")
#     st.info("Paste the full Job Description, recruiter email, and any call notes here.")

#     # Combine the input for simplicity, matching the original combined_text logic
#     recruiter_details = st.text_area(
#         "Job Details, JD, and Recruiter Notes (REQUIRED):",
#         value=st.session_state['job_details'],
#         height=300,
#         placeholder="Paste the entire Job Description, contact email, and any notes from your recruiter call (e.g., 'Spoke with Jane Doe, Interview set for next week, salary 150k')."
#     )

#     st.markdown("---")
    
#     col1, col2 = st.columns(2)
#     with col1:
#         if st.button("⬅️ Back to Profile", key='back2'):
#             st.session_state['current_step'] = 1
#             st.rerun()
#     with col2:
#         if st.button("🚀 Analyze & View Match", key='submit_analysis'):
#             if not recruiter_details.strip():
#                 st.error("Please paste the Job Description/Details to proceed.")
#             else:
#                 st.session_state['job_details'] = recruiter_details
#                 st.session_state['current_step'] = 4 # Skip "Skill Assessment" (Step 3) since it's now automated.
#                 st.rerun()

# def step_three_results():
#     st.markdown("## 3. Skill Assessment & Final Analysis ✨")
    
#     # 1. Generate Analysis if not already done
#     if st.session_state['extracted_data'] is None:
#         # Combine all necessary data for the AI call
#         combined_text = (
#             f"--- APPLICANT SKILLS ---\n{st.session_state['applicant_skills']}\n\n"
#             f"--- JOB DETAILS ---\n{st.session_state['job_details']}"
#         )
        
#         with st.spinner("🧠 The AI is running the match analysis and extracting data..."):
#             st.session_state['extracted_data'] = structured_data_dict = process_recruiter_text(combined_text)
    
#     structured_data_dict = st.session_state['extracted_data']

#     if "error" in structured_data_dict:
#         st.error(structured_data_dict["error"])
#         st.button("↩️ Go Back to Edit Job Details", on_click=lambda: st.session_state.update({'current_step': 2}), key='back_from_error')
#         return

#     st.success("Analysis complete! Review your Match Score and extracted job data below.")
#     st.divider()

#     # --- Side-by-Side Layout for Final Output ---
#     st.markdown("### 🎯 Match Summary")
    
#     col_score, col_prep = st.columns([1, 2])
    
#     with col_score:
#         score = structured_data_dict.get('match_score', 'N/A')
#         # Use HTML/Markdown for a prominent score display
#         st.markdown(f"""
#         <div style='text-align: center; border: 3px solid #007BFF; padding: 15px; border-radius: 10px; background-color: #e9f5ff;'>
#             <p style='font-size: 1.2rem; margin: 0;'>Overall Match Score</p>
#             <h1 style='font-size: 3rem; margin: 0; color: #007BFF;'>{score}</h1>
#         </div>
#         """, unsafe_allow_html=True)

#     with col_prep:
#         st.markdown(f"**Skill Gap Analysis:** {structured_data_dict.get('skill_gap_analysis', 'No gaps identified.')}")
#         st.markdown(f"**Proactive Prep Hint:** {structured_data_dict.get('prep_hint', 'No specific hint available.')}")
    
#     st.divider()

#     st.markdown("### 📋 Full Extracted Job Data")

#     # Display Results in a DataFrame
#     df_display = pd.DataFrame([structured_data_dict]).T
#     df_display.columns = ["Extracted Value"]
#     st.dataframe(df_display, use_container_width=True)

#     # --- Download Section ---
#     st.divider()
#     st.markdown("### 💾 Downloads")
#     col_ics, col_csv = st.columns(2)

#     # iCalendar Download Button
#     if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
#         ics_data = create_ics_file(structured_data_dict)
#         if ics_data:
#             with col_ics:
#                 st.download_button(
#                     label="📅 Download Calendar Event (.ics)",
#                     data=ics_data,
#                     file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
#                     mime="text/calendar"
#                 )

#     # CSV Download Button
#     output = io.StringIO()
#     required_headers = [
#         "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
#         "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
#         "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
#         "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
#         "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
#     ]
#     writer = csv.DictWriter(output, fieldnames=required_headers, extrasaction='ignore')
#     writer.writeheader()
#     row_to_write = {key: structured_data_dict.get(key, "") for key in required_headers}
#     writer.writerow(row_to_write)
#     csv_data = output.getvalue()
    
#     with col_csv:
#         st.download_button(
#             label="📄 Download Job Tracker (.csv)",
#             data=csv_data,
#             file_name="job_details_extracted.csv",
#             mime="text/csv"
#         )
    
#     st.divider()
#     # Reset button
#     if st.button("🔄 Start New Analysis", key='new_analysis_btn'):
#         st.session_state['current_step'] = 0
#         st.session_state['extracted_data'] = None
#         st.rerun()

# # --- 7. Main App Flow Control (Unchanged) ---
# def main():
#     # Force a cleaner look
#     st.set_page_config(layout="centered", page_title="Job Agent")
    
#     # Navigation Display (Mimicking the Mind Map Nodes)
#     nav_status = {
#         0: {"icon": "🏠", "label": "Start", "color": "#007BFF"},
#         1: {"icon": "👤", "label": "Your Profile", "color": "#28A745"},
#         2: {"icon": "📄", "label": "Job Description", "color": "#FFC107"},
#         4: {"icon": "✨", "label": "Analysis/Results", "color": "#DC3545"},
#     }

#     # Display Nav bar horizontally
#     cols = st.columns(len(nav_status))
#     for i, (step, data) in enumerate(nav_status.items()):
#         current = st.session_state['current_step']
#         color = data['color'] if current == step else ("#28A745" if current > step else "#AAAAAA")
        
#         with cols[i]:
#             if step <= current:
#                 if st.button(f"{data['icon']} {data['label']}", key=f'nav_btn_{step}'):
#                     st.session_state['current_step'] = step
#                     st.session_state['extracted_data'] = None # Clear results if navigating back
#                     st.rerun()
#             else:
#                  st.markdown(f"<p style='color:{color}; text-align:center;'>{data['icon']} {data['label']}</p>", unsafe_allow_html=True)
                 
#     st.divider()

#     # Routing logic based on the session state
#     if st.session_state['current_step'] == 0:
#         landing_page()
#     elif st.session_state['current_step'] == 1:
#         step_one_profile()
#     elif st.session_state['current_step'] == 2:
#         step_two_job_desc()
#     elif st.session_state['current_step'] == 4:
#         # Step 3 (Skill Assessment) is now the automatic calculation/display in Step 4.
#         step_three_results()

# if __name__ == "__main__":
#     main()






# ------------------------------------------------------------------------------------------------------------------------------------

# import os
# import json
# import csv
# import io
# import pandas as pd
# import datetime
# from dotenv import load_dotenv
# import google.generativeai as genai
# import streamlit as st

# # --- 1. Configuration and Setup ---
# load_dotenv()
# try:
#     # Ensure this is replaced with your actual key name if different
#     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# except KeyError:
#     st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
#     st.stop()

# # --- 2. Session State Initialization ---
# # This simulates the multi-step navigation of your mind map
# if 'current_step' not in st.session_state:
#     st.session_state['current_step'] = 0 # 0: Landing, 1: Your Profile, 2: Job Description, 3: Skill Assessment/Submit, 4: Results
# if 'profile_data' not in st.session_state:
#     st.session_state['profile_data'] = {}
# if 'job_details' not in st.session_state:
#     st.session_state['job_details'] = ""
# if 'applicant_skills' not in st.session_state:
#     st.session_state['applicant_skills'] = ""
# if 'extracted_data' not in st.session_state:
#     st.session_state['extracted_data'] = None

# # --- 3. The AI Prompt (Unchanged) ---
# # NOTE: The combined text input structure for the model is designed to use all stored data.
# EXTRACTION_PROMPT = """
# You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

# **CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```

# **JSON Keys to use:**
# - "date_contacted": Date HR contacted you or you applied.
# - "hr_name": Name of the HR/recruiter.
# - "phone_number": HR’s phone number.
# - "email_id": HR’s email address.
# - "role_position": Job title for the opportunity.
# - "recruiter_company": The staffing/recruitment agency name (if applicable).
# - "client_company": The company the job is actually for.
# - "location": Job location (e.g., city, remote, hybrid).
# - "job_type": Permanent, Contract, Internship, or Freelance.
# - "mode_of_contact": How you were contacted (e.g., Call, Email, LinkedIn, Naukri).
# - "interview_mode": Online, Offline, or Hybrid.
# - "interview_scheduled_date": Date of the interview (if scheduled).
# - "round_1_details": Details for the first interview round (e.g., "Technical - Scheduled").
# - "round_2_details": Details for the second interview round.
# - "ctc_offered_expected": Salary discussed or expected range.
# - "status": Current status (e.g., "Awaiting JD", "Interview Scheduled", "Selected", "Rejected").
# - "next_follow_up_date": When you plan to follow up.
# - "review_notes": Your personal comments or notes.
# - "extracted_keywords": A comma-separated list of the 5-10 most critical hard skills and technologies required for the role (e.g., Python, AWS, Kubernetes, React, SQL).
# - "match_score": A percentage score (e.g., "85%") representing the fit between the job's required skills and the applicant's skills provided in the input.
# - "skill_gap_analysis": A brief, one-sentence summary of the main skill gaps (e.g., "Missing experience in Terraform and advanced SQL queries.").
# - "prep_hint": A one-sentence, proactive hint based on the extracted status (e.g., if 'Awaiting JD', output: 'Draft a polite follow-up email asking for the JD by tomorrow.'; if 'Interview Scheduled', output: 'Focus on behavioral questions and a deep dive into the extracted keywords.').

# **Input Text (Job Details & Applicant Skills):**
# ***
# {text_input}
# ***

# **JSON Output:**
# """

# # --- 4. The Core Logic Function (Unchanged) ---
# def process_recruiter_text(text_to_process: str) -> dict:
#     model = genai.GenerativeModel('gemini-2.5-flash')
#     prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
#     try:
#         response = model.generate_content(prompt_with_input)
#         # Clean response: remove surrounding code fences that AI sometimes adds despite instructions
#         clean_response = response.text.strip()
#         if clean_response.startswith('```json'):
#             clean_response = clean_response[7:].strip()
#         if clean_response.endswith('```'):
#             clean_response = clean_response[:-3].strip()
                                                      
#         parsed_json = json.loads(clean_response)
#         return parsed_json
#     except json.JSONDecodeError:
#         return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
#     except Exception as e:
#         return {"error": f"An error occurred: {e}"}

# # --- 5. iCalendar File Generation Function (Unchanged) ---
# def create_ics_file(details: dict) -> str:
#     # Function body remains the same as your original code
#     date_str = details.get("interview_scheduled_date", "Not specified")
#     role = details.get("role_position", "Job Interview")
#     client = details.get("client_company", "Client Company")
#     recruiter = details.get("hr_name", "Recruiter")
#     mode = details.get("interview_mode", "Mode Not Specified")
#     try:
#         # Assuming date_str is in YYYY-MM-DD format as per prompt instruction
#         start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
#         end_date = start_date + datetime.timedelta(hours=1)
#         dt_format = "%Y%m%dT%H%M%S"
#         dt_start = start_date.strftime(dt_format)
#         dt_end = end_date.strftime(dt_format)
#         dt_stamp = datetime.datetime.now().strftime(dt_format)
#     except ValueError:
#         return ""

#     summary = f"Interview: {role} @ {client}"
#     description = (
#         f"Role: {role}\n"
#         f"Company: {client}\n"
#         f"Recruiter: {recruiter}\n"
#         f"Round 1 Details: {details.get('round_1_details', 'N/A')}\n"
#         f"Mode: {mode}\n"
#         f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
#     )

#     ics_content = f"""BEGIN:VCALENDAR
# VERSION:2.0
# PRODID:-//AI Job Agent//EN
# BEGIN:VEVENT
# UID:{dt_stamp}-{hash(summary)}
# DTSTAMP:{dt_stamp}
# DTSTART:{dt_start}
# DTEND:{dt_end}
# SUMMARY:{summary}
# DESCRIPTION:{description}
# END:VEVENT
# END:VCALENDAR"""
#     return ics_content.replace('\n', '\r\n')

# # --- 6. Streamlit Page Functions (Simulating Mind Map Nodes) ---

# def landing_page():
#     st.markdown(
#         """
#         <style>
#         .center-text {
#             display: flex;
#             flex-direction: column;
#             align-items: center;
#             justify-content: center;
#             height: 50vh; /* Vertical centering */
#             text-align: center;
#         }
#         .mind-map-node {
#             font-size: 2.5em;
#             font-weight: 700;
#             padding: 20px 40px;
#             border-radius: 15px;
#             color: white;
#             background-color: #4CAF50; /* Green Node */
#             cursor: pointer;
#             box-shadow: 0 4px 8px rgba(0,0,0,0.2);
#             transition: all 0.3s ease;
#         }
#         .mind-map-node:hover {
#             background-color: #45a049;
#             transform: scale(1.05);
#         }
#         </style>
#         <div class="center-text">
#         """,
#         unsafe_allow_html=True
#     )
    
#     st.markdown("## 🤖 Welcome to the Job Agent")
#     st.markdown("One-click analysis for job fit, skill gaps, and interview prep.")

#     # Using a centered button to simulate the initial "Job Agent" node
#     col1, col2, col3 = st.columns([1, 1, 1])
#     with col2:
#         if st.button("✨ START ANALYSIS", key='start_btn', help="Click to expand the main Job Agent Node"):
#             st.session_state['current_step'] = 1
#             st.rerun()

#     st.markdown("</div>", unsafe_allow_html=True)

# def step_one_profile():
#     st.markdown("## 1. Your Profile 👤")
#     st.info("Input your core professional details. This helps the AI personalize the match analysis.")

#     with st.form(key='profile_form'):
#         st.session_state['profile_data']['name'] = st.text_input("Name", value=st.session_state['profile_data'].get('name', ''))
#         st.session_state['profile_data']['email'] = st.text_input("Email", value=st.session_state['profile_data'].get('email', ''))
#         st.session_state['profile_data']['linkedin'] = st.text_input("LinkedIn URL (Optional)", value=st.session_state['profile_data'].get('linkedin', ''))
#         st.session_state['applicant_skills'] = st.text_area(
#             "Key Skills/Resume Summary (REQUIRED for Match Score):", 
#             value=st.session_state['applicant_skills'], 
#             height=150,
#             placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification."
#         )

#         st.markdown("---")
#         if st.form_submit_button("✅ Save Profile & Go to Job Description"):
#             if not st.session_state['applicant_skills'].strip():
#                 st.error("Please enter your Key Skills/Resume Summary to enable the Match Score.")
#             else:
#                 st.session_state['current_step'] = 2
#                 st.rerun()

#     st.button("⬅️ Back to Start", on_click=lambda: st.session_state.update({'current_step': 0}), key='back1')

# def step_two_job_desc():
#     st.markdown("## 2. Job Description 📄")
#     st.info("Paste the full Job Description, recruiter email, and any call notes here.")

#     # Combine the input for simplicity, matching the original combined_text logic
#     recruiter_details = st.text_area(
#         "Job Details, JD, and Recruiter Notes (REQUIRED):",
#         value=st.session_state['job_details'],
#         height=300,
#         placeholder="Paste the entire Job Description, contact email, and any notes from your recruiter call (e.g., 'Spoke with Jane Doe, Interview set for next week, salary 150k')."
#     )

#     st.markdown("---")
    
#     col1, col2 = st.columns(2)
#     with col1:
#         if st.button("⬅️ Back to Profile", key='back2'):
#             st.session_state['current_step'] = 1
#             st.rerun()
#     with col2:
#         if st.button("🚀 Analyze & View Match", key='submit_analysis'):
#             if not recruiter_details.strip():
#                 st.error("Please paste the Job Description/Details to proceed.")
#             else:
#                 st.session_state['job_details'] = recruiter_details
#                 st.session_state['current_step'] = 4 # Skip "Skill Assessment" (Step 3) since it's now automated.
#                 st.rerun()

# # This function combines the old skill assessment (which was automated) and the final results display.
# def step_three_results():
#     st.markdown("## 3. Skill Assessment & Final Analysis ✨")
    
#     # 1. Generate Analysis if not already done
#     if st.session_state['extracted_data'] is None:
#         # Combine all necessary data for the AI call
#         combined_text = (
#             f"--- APPLICANT SKILLS ---\n{st.session_state['applicant_skills']}\n\n"
#             f"--- JOB DETAILS ---\n{st.session_state['job_details']}"
#         )
        
#         with st.spinner("🧠 The AI is running the match analysis and extracting data..."):
#             st.session_state['extracted_data'] = structured_data_dict = process_recruiter_text(combined_text)
    
#     structured_data_dict = st.session_state['extracted_data']

#     if "error" in structured_data_dict:
#         st.error(structured_data_dict["error"])
#         st.button("↩️ Go Back to Edit Job Details", on_click=lambda: st.session_state.update({'current_step': 2}), key='back_from_error')
#         return

#     st.success("Analysis complete! Review your Match Score and extracted job data below.")
#     st.divider()

#     # --- Side-by-Side Layout for Final Output ---
#     st.markdown("### 🎯 Match Summary")
    
#     col_score, col_prep = st.columns([1, 2])
    
#     with col_score:
#         score = structured_data_dict.get('match_score', 'N/A')
#         # Use HTML/Markdown for a prominent score display
#         st.markdown(f"""
#         <div style='text-align: center; border: 3px solid #007BFF; padding: 15px; border-radius: 10px; background-color: #e9f5ff;'>
#             <p style='font-size: 1.2rem; margin: 0;'>Overall Match Score</p>
#             <h1 style='font-size: 3rem; margin: 0; color: #007BFF;'>{score}</h1>
#         </div>
#         """, unsafe_allow_html=True)

#     with col_prep:
#         st.markdown(f"**Skill Gap Analysis:** {structured_data_dict.get('skill_gap_analysis', 'No gaps identified.')}")
#         st.markdown(f"**Proactive Prep Hint:** {structured_data_dict.get('prep_hint', 'No specific hint available.')}")
    
#     st.divider()

#     st.markdown("### 📋 Full Extracted Job Data")

#     # Display Results in a DataFrame
#     df_display = pd.DataFrame([structured_data_dict]).T
#     df_display.columns = ["Extracted Value"]
#     st.dataframe(df_display, use_container_width=True)

#     # --- Download Section ---
#     st.divider()
#     st.markdown("### 💾 Downloads")
#     col_ics, col_csv = st.columns(2)

#     # iCalendar Download Button
#     if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
#         ics_data = create_ics_file(structured_data_dict)
#         if ics_data:
#             with col_ics:
#                 st.download_button(
#                     label="📅 Download Calendar Event (.ics)",
#                     data=ics_data,
#                     file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
#                     mime="text/calendar"
#                 )

#     # CSV Download Button
#     output = io.StringIO()
#     required_headers = [
#         "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
#         "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
#         "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
#         "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
#         "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
#     ]
#     writer = csv.DictWriter(output, fieldnames=required_headers, extrasaction='ignore')
#     writer.writeheader()
#     row_to_write = {key: structured_data_dict.get(key, "") for key in required_headers}
#     writer.writerow(row_to_write)
#     csv_data = output.getvalue()
    
#     with col_csv:
#         st.download_button(
#             label="📄 Download Job Tracker (.csv)",
#             data=csv_data,
#             file_name="job_details_extracted.csv",
#             mime="text/csv"
#         )
    
#     st.divider()
#     # Reset button
#     if st.button("🔄 Start New Analysis", key='new_analysis_btn'):
#         st.session_state['current_step'] = 0
#         st.session_state['extracted_data'] = None
#         st.rerun()

# # --- 7. Main App Flow Control ---
# def main():
#     # Force a cleaner look
#     st.set_page_config(layout="centered", page_title="Job Agent")
    
#     # Navigation Display (Mimicking the Mind Map Nodes)
#     nav_status = {
#         0: {"icon": "🏠", "label": "Start", "color": "#007BFF"},
#         1: {"icon": "👤", "label": "Your Profile", "color": "#28A745"},
#         2: {"icon": "📄", "label": "Job Description", "color": "#FFC107"},
#         4: {"icon": "✨", "label": "Analysis/Results", "color": "#DC3545"},
#     }

#     # Display Nav bar horizontally
#     cols = st.columns(len(nav_status))
#     for i, (step, data) in enumerate(nav_status.items()):
#         current = st.session_state['current_step']
#         color = data['color'] if current == step else ("#28A745" if current > step else "#AAAAAA")
        
#         with cols[i]:
#             if step <= current:
#                 if st.button(f"{data['icon']} {data['label']}", key=f'nav_btn_{step}'):
#                     st.session_state['current_step'] = step
#                     st.session_state['extracted_data'] = None # Clear results if navigating back
#                     st.rerun()
#             else:
#                  st.markdown(f"<p style='color:{color}; text-align:center;'>{data['icon']} {data['label']}</p>", unsafe_allow_html=True)
                 
#     st.divider()

#     # Routing logic based on the session state
#     if st.session_state['current_step'] == 0:
#         landing_page()
#     elif st.session_state['current_step'] == 1:
#         step_one_profile()
#     elif st.session_state['current_step'] == 2:
#         step_two_job_desc()
#     elif st.session_state['current_step'] == 4:
#         # Step 3 (Skill Assessment) is now the automatic calculation/display in Step 4.
#         step_three_results()

# if __name__ == "__main__":
#     main()
# -----------------------------------------------------------------------------------------------------------------------------------------------------

# import os
# import json
# import csv
# import io
# import pandas as pd
# import datetime
# from dotenv import load_dotenv
# import google.generativeai as genai
# import streamlit as st

# # --- 1. Configuration and Setup ---
# load_dotenv()
# try:
#     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# except KeyError:
#     st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
#     st.stop()

# # --- 2. The AI Prompt (FINAL MODIFIED) ---
# EXTRACTION_PROMPT = """
# You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

# **CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```

# **JSON Keys to use:**
# - "date_contacted": Date HR contacted you or you applied.
# - "hr_name": Name of the HR/recruiter.
# - "phone_number": HR’s phone number.
# - "email_id": HR’s email address.
# - "role_position": Job title for the opportunity.
# - "recruiter_company": The staffing/recruitment agency name (if applicable).
# - "client_company": The company the job is actually for.
# - "location": Job location (e.g., city, remote, hybrid).
# - "job_type": Permanent, Contract, Internship, or Freelance.
# - "mode_of_contact": How you were contacted (e.g., Call, Email, LinkedIn, Naukri).
# - "interview_mode": Online, Offline, or Hybrid.
# - "interview_scheduled_date": Date of the interview (if scheduled).
# - "round_1_details": Details for the first interview round (e.g., "Technical - Scheduled").
# - "round_2_details": Details for the second interview round.
# - "ctc_offered_expected": Salary discussed or expected range.
# - "status": Current status (e.g., "Awaiting JD", "Interview Scheduled", "Selected", "Rejected").
# - "next_follow_up_date": When you plan to follow up.
# - "review_notes": Your personal comments or notes.
# - "extracted_keywords": A comma-separated list of the 5-10 most critical hard skills and technologies required for the role (e.g., Python, AWS, Kubernetes, React, SQL).
# - "match_score": A percentage score (e.g., "85%") representing the fit between the job's required skills and the applicant's skills provided in the input.
# - "skill_gap_analysis": A brief, one-sentence summary of the main skill gaps (e.g., "Missing experience in Terraform and advanced SQL queries.").
# - "prep_hint": A one-sentence, proactive hint based on the extracted status (e.g., if 'Awaiting JD', output: 'Draft a polite follow-up email asking for the JD by tomorrow.'; if 'Interview Scheduled', output: 'Focus on behavioral questions and a deep dive into the extracted keywords.').

# **Input Text (Job Details & Applicant Skills):**
# ***
# {text_input}
# ***

# **JSON Output:**
# """

# # --- 3. The Core Logic Function (Unchanged) ---
# def process_recruiter_text(text_to_process: str) -> dict:
#     model = genai.GenerativeModel('gemini-2.5-flash')
#     prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
#     try:
#         response = model.generate_content(prompt_with_input)
#         # Clean response: remove surrounding code fences that AI sometimes adds despite instructions
#         clean_response = response.text.strip()
#         if clean_response.startswith('```json'):
#             clean_response = clean_response[7:].strip()
#         if clean_response.endswith('```'):
#             clean_response = clean_response[:-3].strip()
                                                    
#         parsed_json = json.loads(clean_response)
#         return parsed_json
#     except json.JSONDecodeError:
#         return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
#     except Exception as e:
#         return {"error": f"An error occurred: {e}"}

# # --- 4. iCalendar File Generation Function (Unchanged) ---
# def create_ics_file(details: dict) -> str:
#     date_str = details.get("interview_scheduled_date", "Not specified")
#     role = details.get("role_position", "Job Interview")
#     client = details.get("client_company", "Client Company")
#     recruiter = details.get("hr_name", "Recruiter")
#     mode = details.get("interview_mode", "Mode Not Specified")
#     try:
#         # Assuming date_str is in YYYY-MM-DD format as per prompt instruction
#         start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
#         end_date = start_date + datetime.timedelta(hours=1)
#         dt_format = "%Y%m%dT%H%M%S"
#         dt_start = start_date.strftime(dt_format)
#         dt_end = end_date.strftime(dt_format)
#         dt_stamp = datetime.datetime.now().strftime(dt_format)
#     except ValueError:
#         return ""

#     summary = f"Interview: {role} @ {client}"
#     description = (
#         f"Role: {role}\n"
#         f"Company: {client}\n"
#         f"Recruiter: {recruiter}\n"
#         f"Round 1 Details: {details.get('round_1_details', 'N/A')}\n"
#         f"Mode: {mode}\n"
#         f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
#     )

#     ics_content = f"""BEGIN:VCALENDAR
# VERSION:2.0
# PRODID:-//AI Job Agent//EN
# BEGIN:VEVENT
# UID:{dt_stamp}-{hash(summary)}
# DTSTAMP:{dt_stamp}
# DTSTART:{dt_start}
# DTEND:{dt_end}
# SUMMARY:{summary}
# DESCRIPTION:{description}
# END:VEVENT
# END:VCALENDAR"""
#     return ics_content.replace('\n', '\r\n')

# # --- 5. Building the Streamlit Web Interface (Modified for Centering and Layout) ---

# # --- Centered Header Block ---
# st.markdown(
#     """
#     <style>
#     /* Custom styling to ensure the header is centered */
#     .center-content {
#         text-align: center;
#         width: 100%;
#         margin-bottom: 2rem; /* Add some space below the header block */
#     }
#     .title-text {
#         font-size: 2.5rem;
#         font-weight: 700;
#         margin-bottom: 0.25rem;
#     }
#     .subtitle-text {
#         font-size: 1.1rem;
#         color: #555;
#         margin-top: 0;
#     }
#     </style>
    
#     <div class="center-content">
#         <h1 class="title-text">Testing</h1>
#         <p class="subtitle-text">Analyze job details and your own skills simultaneously to generate a match score and tracking data.</p>
#     </div>
#     """, 
#     unsafe_allow_html=True
# )
# # --- End Centered Header Block ---

# # <h1 class="title-text">🤖 AI Job Agent</h1>
# # Help Section
# with st.expander("❓ How This Works & Expected Fields", expanded=False):
#     st.markdown("""
#         The AI analyzes the Job Details and your skills to pull 22 key data points, including a **Match Score** and **Proactive Prep Hint**.

#         **New Fields:** `match_score`, `skill_gap_analysis`, and `prep_hint`.

#         **Tip:** For best results, put your resume/skills in the first section, and the full Job Description in the third section.
#     """)

# # Form with Expanders for Each Section
# with st.form(key='data_extraction_form'):
    
#     # 2. Recruiter Call Summary (Expanded by default for immediate input)
#     st.subheader("📞 1. Recruiter Call Summary")
#     with st.expander("Summarize your conversation with the recruiter:", expanded=True):
#         call_details = st.text_input(
#             "Call Details Input:",
#             placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k.",
#             key='call_details',
#             label_visibility="collapsed" # Hide redundant label
#         )

#     # 3. Full Job Description Text (Expanded by default for immediate input)
#     st.subheader("📄 2. Full Job Description Text")
#     with st.expander("Paste the full Job Description, email, or message here:", expanded=True):
#         recruiter_text = st.text_area(
#             "Recruiter Text Input:",
#             height=150, # Set to user's desired height
#             placeholder="E.g., Dear [Name], We are looking for a Senior Full Stack Developer (React/Node.js) for our client, Acme Corp. in Bangalore (Hybrid)...",
#             key='recruiter_text',
#             label_visibility="collapsed" # Hide redundant label
#         )

#     # 1. Applicant Skills (Expanded by default for immediate input)
#     st.subheader("🧠 3. Applicant Skills (For Match Score)")
#     with st.expander("Paste your key skills, technologies, and experience here.", expanded=True):
#         applicant_skills = st.text_area(
#             "Applicant Skills Input:",
#             height=20, # Set to user's desired height
#             placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification.",
#             key='applicant_skills',
#             label_visibility="collapsed" # Hide redundant label
#         )

#     st.markdown("---") # Separator before the submit button

#     submitted = st.form_submit_button("✨ Extract, Score, and Prepare Files")

# # --- 6. Processing Logic (Unchanged) ---
# if submitted:
#     # Combining inputs for the AI prompt
#     combined_text = (
#         f"--- APPLICANT SKILLS ---\n{applicant_skills}\n\n"
#         f"--- JOB DETAILS ---\n"
#         f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
#     )

#     if call_details.strip() or recruiter_text.strip() or applicant_skills.strip():
#         with st.spinner("🧠 The AI is analyzing and scoring the fit..."):
#             structured_data_dict = process_recruiter_text(combined_text)

#             if "error" in structured_data_dict:
#                 st.error(structured_data_dict["error"])
#             else:
#                 st.success("Extraction and scoring complete! Review results and download your files below.")
#                 st.subheader("✅ Extracted Information Review")

#                 # Display Results in a DataFrame
#                 df_display = pd.DataFrame([structured_data_dict]).T
#                 df_display.columns = ["Extracted Value"]
#                 st.dataframe(df_display, use_container_width=True)

#                 st.divider()

#                 # iCalendar Download Button
#                 if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
#                     ics_data = create_ics_file(structured_data_dict)
#                     if ics_data:
#                         st.download_button(
#                             label="📅 Download Calendar Event (.ics)",
#                             data=ics_data,
#                             file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
#                             mime="text/calendar"
#                         )

#                 # CSV Download Button
#                 output = io.StringIO()
#                 headers = list(structured_data_dict.keys()) # Use extracted keys dynamically
                
#                 # Check if all required headers are present, if not, use the full list as fallback
#                 required_headers = [
#                     "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
#                     "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
#                     "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
#                     "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
#                     "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
#                 ]
#                 # Ensure the CSV writer uses the full header list to avoid missing columns
#                 final_headers = required_headers

#                 writer = csv.DictWriter(output, fieldnames=final_headers, extrasaction='ignore')
#                 writer.writeheader()
                
#                 # Ensure all missing keys in the dictionary are filled with "" to prevent DictWriter errors
#                 row_to_write = {key: structured_data_dict.get(key, "") for key in final_headers}
#                 writer.writerow(row_to_write)
                
#                 csv_data = output.getvalue()

#                 st.download_button(
#                     label="📄 Download Job Tracker (.csv)",
#                     data=csv_data,
#                     file_name="job_details.csv",
#                     mime="text/csv"
#                 )
#     else:
#         st.warning("Please provide some information in at least one of the input sections.")




# # import os
# # import json
# # import csv
# # import io
# # import pandas as pd
# # import datetime
# # from dotenv import load_dotenv
# # import google.generativeai as genai
# # import streamlit as st

# # # --- 1. Configuration and Setup ---
# # load_dotenv()
# # try:
# #     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# # except KeyError:
# #     st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
# #     st.stop()

# # # --- 2. The AI Prompt (FINAL MODIFIED) ---
# # EXTRACTION_PROMPT = """
# # You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

# # **CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```

# # **JSON Keys to use:**
# # - "date_contacted": Date HR contacted you or you applied.
# # - "hr_name": Name of the HR/recruiter.
# # - "phone_number": HR’s phone number.
# # - "email_id": HR’s email address.
# # - "role_position": Job title for the opportunity.
# # - "recruiter_company": The staffing/recruitment agency name (if applicable).
# # - "client_company": The company the job is actually for.
# # - "location": Job location (e.g., city, remote, hybrid).
# # - "job_type": Permanent, Contract, Internship, or Freelance.
# # - "mode_of_contact": How you were contacted (e.g., Call, Email, LinkedIn, Naukri).
# # - "interview_mode": Online, Offline, or Hybrid.
# # - "interview_scheduled_date": Date of the interview (if scheduled).
# # - "round_1_details": Details for the first interview round (e.g., "Technical - Scheduled").
# # - "round_2_details": Details for the second interview round.
# # - "ctc_offered_expected": Salary discussed or expected range.
# # - "status": Current status (e.g., "Awaiting JD", "Interview Scheduled", "Selected", "Rejected").
# # - "next_follow_up_date": When you plan to follow up.
# # - "review_notes": Your personal comments or notes.
# # - "extracted_keywords": A comma-separated list of the 5-10 most critical hard skills and technologies required for the role (e.g., Python, AWS, Kubernetes, React, SQL).
# # - "match_score": A percentage score (e.g., "85%") representing the fit between the job's required skills and the applicant's skills provided in the input.
# # - "skill_gap_analysis": A brief, one-sentence summary of the main skill gaps (e.g., "Missing experience in Terraform and advanced SQL queries.").
# # - "prep_hint": A one-sentence, proactive hint based on the extracted status (e.g., if 'Awaiting JD', output: 'Draft a polite follow-up email asking for the JD by tomorrow.'; if 'Interview Scheduled', output: 'Focus on behavioral questions and a deep dive into the extracted keywords.').

# # **Input Text (Job Details & Applicant Skills):**
# # ***
# # {text_input}
# # ***

# # **JSON Output:**
# # """

# # # --- 3. The Core Logic Function (Unchanged) ---
# # def process_recruiter_text(text_to_process: str) -> dict:
# #     model = genai.GenerativeModel('gemini-2.5-flash')
# #     prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
# #     try:
# #         response = model.generate_content(prompt_with_input)
# #         # Clean response: remove surrounding code fences that AI sometimes adds despite instructions
# #         clean_response = response.text.strip()
# #         if clean_response.startswith('```json'):
# #             clean_response = clean_response[7:].strip()
# #         if clean_response.endswith('```'):
# #             clean_response = clean_response[:-3].strip()
                                                    
# #         parsed_json = json.loads(clean_response)
# #         return parsed_json
# #     except json.JSONDecodeError:
# #         return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
# #     except Exception as e:
# #         return {"error": f"An error occurred: {e}"}

# # # --- 4. iCalendar File Generation Function (Unchanged) ---
# # def create_ics_file(details: dict) -> str:
# #     date_str = details.get("interview_scheduled_date", "Not specified")
# #     role = details.get("role_position", "Job Interview")
# #     client = details.get("client_company", "Client Company")
# #     recruiter = details.get("hr_name", "Recruiter")
# #     mode = details.get("interview_mode", "Mode Not Specified")
# #     try:
# #         # Assuming date_str is in YYYY-MM-DD format as per prompt instruction
# #         start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
# #         end_date = start_date + datetime.timedelta(hours=1)
# #         dt_format = "%Y%m%dT%H%M%S"
# #         dt_start = start_date.strftime(dt_format)
# #         dt_end = end_date.strftime(dt_format)
# #         dt_stamp = datetime.datetime.now().strftime(dt_format)
# #     except ValueError:
# #         return ""

# #     summary = f"Interview: {role} @ {client}"
# #     description = (
# #         f"Role: {role}\n"
# #         f"Company: {client}\n"
# #         f"Recruiter: {recruiter}\n"
# #         f"Round 1 Details: {details.get('round_1_details', 'N/A')}\n"
# #         f"Mode: {mode}\n"
# #         f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
# #     )

# #     ics_content = f"""BEGIN:VCALENDAR
# # VERSION:2.0
# # PRODID:-//AI Job Agent//EN
# # BEGIN:VEVENT
# # UID:{dt_stamp}-{hash(summary)}
# # DTSTAMP:{dt_stamp}
# # DTSTART:{dt_start}
# # DTEND:{dt_end}
# # SUMMARY:{summary}
# # DESCRIPTION:{description}
# # END:VEVENT
# # END:VCALENDAR"""
# #     return ics_content.replace('\n', '\r\n')

# # # --- 5. Building the Streamlit Web Interface (Modified for Expanded Expanders) ---
# # st.title("                        🤖 AI Job Agent")
# # st.write("Analyze job details and your own skills simultaneously to generate a match score and tracking data.")

# # # Help Section
# # with st.expander("❓ How This Works & Expected Fields", expanded=False):
# #     st.markdown("""
# #         The AI analyzes the Job Details and your skills to pull 22 key data points, including a **Match Score** and **Proactive Prep Hint**.

# #         **New Fields:** `match_score`, `skill_gap_analysis`, and `prep_hint`.

# #         **Tip:** For best results, put your resume/skills in the first section, and the full Job Description in the third section.
# #     """)

# # # Form with Expanders for Each Section
# # with st.form(key='data_extraction_form'):
    
# #     # # 1. Applicant Skills (Expanded by default for immediate input)
# #     # st.subheader("🧠 1. Applicant Skills (For Match Score)")
# #     # with st.expander("Paste your key skills, technologies, and experience here.", expanded=True):
# #     #     applicant_skills = st.text_area(
# #     #         "Applicant Skills Input:",
# #     #         #height=150,
# #     #         height=50,
# #     #         placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification.",
# #     #         key='applicant_skills',
# #     #         label_visibility="collapsed" # Hide redundant label
# #     #     )

# #     # 2. Recruiter Call Summary (Expanded by default for immediate input)
# #     st.subheader("📞 1. Recruiter Call Summary")
# #     with st.expander("Summarize your conversation with the recruiter:", expanded=True):
# #         call_details = st.text_input(
# #             "Call Details Input:",
# #             placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k.",
# #             key='call_details',
# #             label_visibility="collapsed" # Hide redundant label
# #         )

# #     # 3. Full Job Description Text (Expanded by default for immediate input)
# #     st.subheader("📄 2. Full Job Description Text")
# #     with st.expander("Paste the full Job Description, email, or message here:", expanded=True):
# #         recruiter_text = st.text_area(
# #             "Recruiter Text Input:",
# #             #height=350,
# #             height=150,
# #             placeholder="E.g., Dear [Name], We are looking for a Senior Full Stack Developer (React/Node.js) for our client, Acme Corp. in Bangalore (Hybrid)...",
# #             key='recruiter_text',
# #             label_visibility="collapsed" # Hide redundant label
# #         )

# #       # 1. Applicant Skills (Expanded by default for immediate input)
# #     st.subheader("🧠 3. Applicant Skills (For Match Score)")
# #     with st.expander("Paste your key skills, technologies, and experience here.", expanded=True):
# #         applicant_skills = st.text_area(
# #             "Applicant Skills Input:",
# #             #height=150,
# #             height=20,
# #             placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification.",
# #             key='applicant_skills',
# #             label_visibility="collapsed" # Hide redundant label
# #         )

# #     st.markdown("---") # Separator before the submit button

# #     submitted = st.form_submit_button("✨ Extract, Score, and Prepare Files")

# # # --- 6. Processing Logic (Unchanged) ---
# # if submitted:
# #     # Combining inputs for the AI prompt
# #     combined_text = (
# #         f"--- APPLICANT SKILLS ---\n{applicant_skills}\n\n"
# #         f"--- JOB DETAILS ---\n"
# #         f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
# #     )

# #     if call_details.strip() or recruiter_text.strip() or applicant_skills.strip():
# #         with st.spinner("🧠 The AI is analyzing and scoring the fit..."):
# #             structured_data_dict = process_recruiter_text(combined_text)

# #             if "error" in structured_data_dict:
# #                 st.error(structured_data_dict["error"])
# #             else:
# #                 st.success("Extraction and scoring complete! Review results and download your files below.")
# #                 st.subheader("✅ Extracted Information Review")

# #                 # Display Results in a DataFrame
# #                 df_display = pd.DataFrame([structured_data_dict]).T
# #                 df_display.columns = ["Extracted Value"]
# #                 st.dataframe(df_display, use_container_width=True)

# #                 st.divider()

# #                 # iCalendar Download Button
# #                 if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
# #                     ics_data = create_ics_file(structured_data_dict)
# #                     if ics_data:
# #                         st.download_button(
# #                             label="📅 Download Calendar Event (.ics)",
# #                             data=ics_data,
# #                             file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
# #                             mime="text/calendar"
# #                         )

# #                 # CSV Download Button
# #                 output = io.StringIO()
# #                 headers = list(structured_data_dict.keys()) # Use extracted keys dynamically
                
# #                 # Check if all required headers are present, if not, use the full list as fallback
# #                 required_headers = [
# #                     "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
# #                     "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
# #                     "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
# #                     "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
# #                     "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
# #                 ]
# #                 # Ensure the CSV writer uses the full header list to avoid missing columns
# #                 final_headers = required_headers

# #                 writer = csv.DictWriter(output, fieldnames=final_headers, extrasaction='ignore')
# #                 writer.writeheader()
                
# #                 # Ensure all missing keys in the dictionary are filled with "" to prevent DictWriter errors
# #                 row_to_write = {key: structured_data_dict.get(key, "") for key in final_headers}
# #                 writer.writerow(row_to_write)
                
# #                 csv_data = output.getvalue()

# #                 st.download_button(
# #                     label="📄 Download Job Tracker (.csv)",
# #                     data=csv_data,
# #                     file_name="job_details.csv",
# #                     mime="text/csv"
# #                 )
# #     else:
# #         st.warning("Please provide some information in at least one of the input sections.")

# # # import os
# # # import json
# # # import csv
# # # import io
# # # import pandas as pd
# # # import datetime
# # # from dotenv import load_dotenv
# # # import google.generativeai as genai
# # # import streamlit as st

# # # # --- 1. Configuration and Setup ---
# # # load_dotenv()
# # # try:
# # #     genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
# # # except KeyError:
# # #     st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
# # #     st.stop()

# # # # --- 2. The AI Prompt (FINAL MODIFIED) ---
# # # EXTRACTION_PROMPT = """
# # # You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

# # # **CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```

# # # **JSON Keys to use:**
# # # - "date_contacted": Date HR contacted you or you applied.
# # # - "hr_name": Name of the HR/recruiter.
# # # - "phone_number": HR’s phone number.
# # # - "email_id": HR’s email address.
# # # - "role_position": Job title for the opportunity.
# # # - "recruiter_company": The staffing/recruitment agency name (if applicable).
# # # - "client_company": The company the job is actually for.
# # # - "location": Job location (e.g., city, remote, hybrid).
# # # - "job_type": Permanent, Contract, Internship, or Freelance.
# # # - "mode_of_contact": How you were contacted (e.g., Call, Email, LinkedIn, Naukri).
# # # - "interview_mode": Online, Offline, or Hybrid.
# # # - "interview_scheduled_date": Date of the interview (if scheduled).
# # # - "round_1_details": Details for the first interview round (e.g., "Technical - Scheduled").
# # # - "round_2_details": Details for the second interview round.
# # # - "ctc_offered_expected": Salary discussed or expected range.
# # # - "status": Current status (e.g., "Awaiting JD", "Interview Scheduled", "Selected", "Rejected").
# # # - "next_follow_up_date": When you plan to follow up.
# # # - "review_notes": Your personal comments or notes.
# # # - "extracted_keywords": A comma-separated list of the 5-10 most critical hard skills and technologies required for the role (e.g., Python, AWS, Kubernetes, React, SQL).
# # # - "match_score": A percentage score (e.g., "85%") representing the fit between the job's required skills and the applicant's skills provided in the input.
# # # - "skill_gap_analysis": A brief, one-sentence summary of the main skill gaps (e.g., "Missing experience in Terraform and advanced SQL queries.").
# # # - "prep_hint": A one-sentence, proactive hint based on the extracted status (e.g., if 'Awaiting JD', output: 'Draft a polite follow-up email asking for the JD by tomorrow.'; if 'Interview Scheduled', output: 'Focus on behavioral questions and a deep dive into the extracted keywords.').

# # # **Input Text (Job Details & Applicant Skills):**
# # # ***
# # # {text_input}
# # # ***

# # # **JSON Output:**
# # # """

# # # # --- 3. The Core Logic Function (Unchanged) ---
# # # def process_recruiter_text(text_to_process: str) -> dict:
# # #     model = genai.GenerativeModel('gemini-2.5-flash')
# # #     prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
# # #     try:
# # #         response = model.generate_content(prompt_with_input)
# # #         # Clean response: remove surrounding code fences that AI sometimes adds despite instructions
# # #         clean_response = response.text.strip()
# # #         if clean_response.startswith('```json'):
# # #             clean_response = clean_response[7:].strip()
# # #         if clean_response.endswith('```'):
# # #             clean_response = clean_response[:-3].strip()
                                                    
# # #         parsed_json = json.loads(clean_response)
# # #         return parsed_json
# # #     except json.JSONDecodeError:
# # #         return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
# # #     except Exception as e:
# # #         return {"error": f"An error occurred: {e}"}

# # # # --- 4. iCalendar File Generation Function (Unchanged) ---
# # # def create_ics_file(details: dict) -> str:
# # #     date_str = details.get("interview_scheduled_date", "Not specified")
# # #     role = details.get("role_position", "Job Interview")
# # #     client = details.get("client_company", "Client Company")
# # #     recruiter = details.get("hr_name", "Recruiter")
# # #     mode = details.get("interview_mode", "Mode Not Specified")
# # #     try:
# # #         # Assuming date_str is in YYYY-MM-DD format as per prompt instruction
# # #         start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
# # #         end_date = start_date + datetime.timedelta(hours=1)
# # #         dt_format = "%Y%m%dT%H%M%S"
# # #         dt_start = start_date.strftime(dt_format)
# # #         dt_end = end_date.strftime(dt_format)
# # #         dt_stamp = datetime.datetime.now().strftime(dt_format)
# # #     except ValueError:
# # #         return ""

# # #     summary = f"Interview: {role} @ {client}"
# # #     description = (
# # #         f"Role: {role}\n"
# # #         f"Company: {client}\n"
# # #         f"Recruiter: {recruiter}\n"
# # #         f"Round 1 Details: {details.get('round_1_details', 'N/A')}\n"
# # #         f"Mode: {mode}\n"
# # #         f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
# # #     )

# # #     ics_content = f"""BEGIN:VCALENDAR
# # # VERSION:2.0
# # # PRODID:-//AI Job Agent//EN
# # # BEGIN:VEVENT
# # # UID:{dt_stamp}-{hash(summary)}
# # # DTSTAMP:{dt_stamp}
# # # DTSTART:{dt_start}
# # # DTEND:{dt_end}
# # # SUMMARY:{summary}
# # # DESCRIPTION:{description}
# # # END:VEVENT
# # # END:VCALENDAR"""
# # #     return ics_content.replace('\n', '\r\n')

# # # # --- 5. Building the Streamlit Web Interface (Modified for Expanded Expanders) ---
# # # st.title("🤖 AI Job Agent")
# # # st.write("Analyze job details and your own skills simultaneously to generate a match score and tracking data.")

# # # # Help Section
# # # with st.expander("❓ How This Works & Expected Fields", expanded=False):
# # #     st.markdown("""
# # #         The AI analyzes the Job Details and your skills to pull 22 key data points, including a **Match Score** and **Proactive Prep Hint**.

# # #         **New Fields:** `match_score`, `skill_gap_analysis`, and `prep_hint`.

# # #         **Tip:** For best results, put your resume/skills in the first section, and the full Job Description in the third section.
# # #     """)

# # # # Form with Expanders for Each Section
# # # with st.form(key='data_extraction_form'):
    
# # #     # 1. Applicant Skills (Expanded by default for immediate input)
# # #     st.subheader("🧠 1. Applicant Skills (For Match Score)")
# # #     with st.expander("Paste your key skills, technologies, and experience here.", expanded=True):
# # #         applicant_skills = st.text_area(
# # #             "Applicant Skills Input:",
# # #             height=150,
# # #             placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification.",
# # #             key='applicant_skills',
# # #             label_visibility="collapsed" # Hide redundant label
# # #         )

# # #     # 2. Recruiter Call Summary (Expanded by default for immediate input)
# # #     st.subheader("📞 2. Recruiter Call Summary")
# # #     with st.expander("Summarize your conversation with the recruiter:", expanded=True):
# # #         call_details = st.text_input(
# # #             "Call Details Input:",
# # #             placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k.",
# # #             key='call_details',
# # #             label_visibility="collapsed" # Hide redundant label
# # #         )

# # #     # 3. Full Job Description Text (Expanded by default for immediate input)
# # #     st.subheader("📄 3. Full Job Description Text")
# # #     with st.expander("Paste the full Job Description, email, or message here:", expanded=True):
# # #         recruiter_text = st.text_area(
# # #             "Recruiter Text Input:",
# # #             height=350,
# # #             placeholder="E.g., Dear [Name], We are looking for a Senior Full Stack Developer (React/Node.js) for our client, Acme Corp. in Bangalore (Hybrid)...",
# # #             key='recruiter_text',
# # #             label_visibility="collapsed" # Hide redundant label
# # #         )

# # #     st.markdown("---") # Separator before the submit button

# # #     submitted = st.form_submit_button("✨ Extract, Score, and Prepare Files")

# # # # --- 6. Processing Logic (Unchanged) ---
# # # if submitted:
# # #     # Combining inputs for the AI prompt
# # #     combined_text = (
# # #         f"--- APPLICANT SKILLS ---\n{applicant_skills}\n\n"
# # #         f"--- JOB DETAILS ---\n"
# # #         f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
# # #     )

# # #     if call_details.strip() or recruiter_text.strip() or applicant_skills.strip():
# # #         with st.spinner("🧠 The AI is analyzing and scoring the fit..."):
# # #             structured_data_dict = process_recruiter_text(combined_text)

# # #             if "error" in structured_data_dict:
# # #                 st.error(structured_data_dict["error"])
# # #             else:
# # #                 st.success("Extraction and scoring complete! Review results and download your files below.")
# # #                 st.subheader("✅ Extracted Information Review")

# # #                 # Display Results in a DataFrame
# # #                 df_display = pd.DataFrame([structured_data_dict]).T
# # #                 df_display.columns = ["Extracted Value"]
# # #                 st.dataframe(df_display, use_container_width=True)

# # #                 st.divider()

# # #                 # iCalendar Download Button
# # #                 if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
# # #                     ics_data = create_ics_file(structured_data_dict)
# # #                     if ics_data:
# # #                         st.download_button(
# # #                             label="📅 Download Calendar Event (.ics)",
# # #                             data=ics_data,
# # #                             file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
# # #                             mime="text/calendar"
# # #                         )

# # #                 # CSV Download Button
# # #                 output = io.StringIO()
# # #                 headers = list(structured_data_dict.keys()) # Use extracted keys dynamically
                
# # #                 # Check if all required headers are present, if not, use the full list as fallback
# # #                 required_headers = [
# # #                     "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
# # #                     "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
# # #                     "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
# # #                     "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
# # #                     "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
# # #                 ]
# # #                 # Ensure the CSV writer uses the full header list to avoid missing columns
# # #                 final_headers = required_headers

# # #                 writer = csv.DictWriter(output, fieldnames=final_headers, extrasaction='ignore')
# # #                 writer.writeheader()
                
# # #                 # Ensure all missing keys in the dictionary are filled with "" to prevent DictWriter errors
# # #                 row_to_write = {key: structured_data_dict.get(key, "") for key in final_headers}
# # #                 writer.writerow(row_to_write)
                
# # #                 csv_data = output.getvalue()

# # #                 st.download_button(
# # #                     label="📄 Download Job Tracker (.csv)",
# # #                     data=csv_data,
# # #                     file_name="job_details.csv",
# # #                     mime="text/csv"
# # #                 )
# # #     else:
# # #         st.warning("Please provide some information in at least one of the input sections.")
