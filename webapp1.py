import os
import json
import csv
import io
import pandas as pd
import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

# --- 1. Page Configuration (MUST be the first Streamlit command) ---
st.set_page_config(
    layout="wide",
    page_title="Job Agent",
    page_icon="🤖"
)

# --- 2. Configuration and Setup ---
load_dotenv()
try:
    # Ensure this is replaced with your actual key name if different
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except (KeyError, TypeError):
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure it is correctly set up in your environment or a .env file.")
    st.stop()

# --- 3. Session State Initialization ---
# This dictionary holds the state of our app, mimicking a multi-page flow
if 'app_state' not in st.session_state:
    st.session_state.app_state = {
        'current_view': 'start',  # 'start', 'map', 'results'
        'profile_data': "",
        'job_description': "",
        'skills_data': "",
        'analysis_result': None
    }

# --- 4. The AI Prompt (Unchanged) ---
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).
**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences.
**JSON Keys to use:**
- "date_contacted", "hr_name", "phone_number", "email_id", "role_position", "recruiter_company", "client_company", "location", "job_type", "mode_of_contact", "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details", "ctc_offered_expected", "status", "next_follow_up_date", "review_notes", "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint".
**Input Text (Job Details & Applicant Skills):**
***
{text_input}
***
**JSON Output:**
"""

# --- 5. Core Logic & Calendar Functions (Unchanged) ---
def process_recruiter_text(text_to_process: str) -> dict:
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        clean_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(clean_response)
    except json.JSONDecodeError:
        return {"error": f"The AI returned an invalid JSON format. Raw output: {response.text}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

def create_ics_file(details: dict) -> str:
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

# --- 6. UI Rendering Functions ---

def load_css():
    """Loads all custom CSS for the mind map UI."""
    st.markdown("""
    <style>
        /* --- Base & Fonts --- */
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap' );
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200' );
        
        body {
            font-family: 'Manrope', sans-serif;
        }
        
        /* --- Main Layout & Background --- */
        .stApp {
            background-color: #101c22;
            color: #fff;
        }
        
        /* --- Remove Streamlit's default padding --- */
        .block-container {
            padding: 2rem 4rem 2rem 4rem !important;
        }
        
        /* --- START VIEW CENTERING --- */
        .start-page-container {
            display: flex;
            flex-direction: column;
            justify-content: center; /* Center vertically */
            align-items: center; /* Center horizontally */
            min-height: 70vh; 
            text-align: center;
            /* REDUCED GAP to bring button closer to text */
            gap: 1rem; 
        }
        
        /* --- Custom Card Styling for Mind Map Nodes --- */
        .mind-map-card {
            background-color: #192b33;
            border: 1px solid #325567;
            border-radius: 0.75rem;
            padding: 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        }
        .mind-map-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(19, 164, 236, 0.2), 0 4px 6px -4px rgba(19, 164, 236, 0.2);
        }
        .mind-map-card h2 {
            font-size: 1.25rem;
            font-weight: 700;
            color: #fff;
        }
        .mind-map-card p {
            color: #92b7c9;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }
        .mind-map-card .icon {
            font-size: 2.5rem;
            color: #13a4ec;
        }
        
        /* --- Text Area Styling --- */
        .stTextArea textarea {
            background-color: #101c22;
            border: 1px solid #325567;
            color: #fff;
            border-radius: 0.5rem;
        }
        
        /* --- Button Styling --- */
        .stButton button {
            background-color: #13a4ec;
            color: white;
            border-radius: 0.5rem;
            padding: 0.75rem 1.5rem;
            font-weight: 700;
            border: none;
        }
        .stButton button:hover {
            background-color: #0f8ac9;
        }
        .stButton button:disabled {
            background-color: #233c48;
            color: #5a6e78;
            cursor: not-allowed;
        }
        
        /* --- Header Styling --- */
        .main-header {
            text-align: center;
            padding: 2rem 0;
            margin-bottom: 2rem; 
        }
        .main-header h1 {
            font-size: 3rem;
            font-weight: 800;
            letter-spacing: -0.033em;
        }
        .main-header p {
            font-size: 1.1rem;
            color: #92b7c9;
        }

        /* --- Start View Header (Specific overrides) --- */
        #start-header h1 {
            font-size: 5rem; 
            font-weight: 900;
            margin-bottom: 0rem;
        }
        #start-header p {
            font-size: 1.5rem; 
            font-weight: 500;
            color: #92b7c9;
            /* REMOVED MARGIN to allow button to sit closer */
            margin-bottom: 0rem; 
        }
        
        /* --- Results Styling --- */
        .results-card {
            background-color: #111c22;
            border-radius: 0.75rem;
            padding: 1.5rem;
            border: 1px solid #325567;
        }
        .stMetric {
            background-color: #192b33;
            border-radius: 0.5rem;
            padding: 1rem;
            border: 1px solid #325567;
        }
        .stMetric > div > div > div {
            font-size: 2.5rem !important;
            color: #50E3C2 !important;
        }
    </style>
    """, unsafe_allow_html=True)

def draw_start_view():
    """Renders the initial view with the central 'Job Agent' node."""
    
    # We use a custom container class defined in CSS to handle the centering
    st.markdown('<div class="start-page-container">', unsafe_allow_html=True)

    # Header content
    st.markdown('<div id="start-header"><h1>Job Agent</h1><p>Intelligently Map Your Next Career Move</p></div>', unsafe_allow_html=True)
    
    # Button content 
    # Used specific columns to center the button perfectly horizontally
    _, btn_col, _ = st.columns([5, 2, 5]) 
    with btn_col:
         if st.button("🚀 Start Mapping", key="start_mapping_button", use_container_width=True):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

def draw_map_view():
    """Renders the main mind map interface for data input."""
    # This view does NOT use the start-page-container, so it flows normally below the nav.
    st.markdown('<div class="main-header"><h2>Build Your Career Mind Map</h2><p>Complete the nodes below to generate your analysis.</p></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
            <div class="mind-map-card">
                <span class="material-symbols-outlined icon">person</span>
                <h2>Your Profile</h2>
                <p>Paste your resume summary or key skills.</p>
            </div>
        """, unsafe_allow_html=True)
        st.session_state.app_state['profile_data'] = st.text_area("Your Profile", height=200, key="profile_input", label_visibility="collapsed", placeholder="e.g., Python (5 years), AWS Certified, Project Management...")

    with col2:
        st.markdown("""
            <div class="mind-map-card">
                <span class="material-symbols-outlined icon">description</span>
                <h2>Job Description</h2>
                <p>Input the details of the role you're targeting.</p>
            </div>
        """, unsafe_allow_html=True)
        st.session_state.app_state['job_description'] = st.text_area("Job Description", height=200, key="jd_input", label_visibility="collapsed", placeholder="Paste the full job description here...")

    with col3:
        st.markdown("""
            <div class="mind-map-card">
                <span class="material-symbols-outlined icon">assessment</span>
                <h2>Skill Assessment</h2>
                <p>Optionally, add any other relevant notes or skills.</p>
            </div>
        """, unsafe_allow_html=True)
        st.session_state.app_state['skills_data'] = st.text_area("Skill Assessment", height=200, key="skills_input", label_visibility="collapsed", placeholder="Add any extra notes, call summaries, or specific skills to highlight.")

    st.markdown("---")
    
    # Disable button until required fields are filled
    is_ready = bool(st.session_state.app_state['profile_data'].strip() and st.session_state.app_state['job_description'].strip())
    
    # Place the "Generate Analysis" button across the bottom
    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        if st.button("✨ Generate Analysis", disabled=not is_ready, use_container_width=True):
            # Combine all inputs for the AI
            combined_text = (
                f"--- APPLICANT SKILLS ---\n{st.session_state.app_state['profile_data']}\n\n"
                f"--- JOB DETAILS ---\n{st.session_state.app_state['job_description']}\n\n"
                f"--- ADDITIONAL NOTES ---\n{st.session_state.app_state['skills_data']}"
            )
            
            with st.spinner("🧠 The AI is running the match analysis..."):
                result = process_recruiter_text(combined_text)
                st.session_state.app_state['analysis_result'] = result
                st.session_state.app_state['current_view'] = 'results'
                st.rerun()

def draw_results_view():
    """Renders the final analysis results."""
    st.markdown('<div class="main-header"><h2>Job Match Analysis</h2><p>An at-a-glance analysis of your profile against the job description.</p></div>', unsafe_allow_html=True)
    
    result = st.session_state.app_state['analysis_result']
    if not result or "error" in result:
        st.error(result.get("error", "An unknown error occurred during analysis."))
        if st.button("⬅️ Go Back"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()
        return

    # Main 3-column layout for results
    col1, col2, col3 = st.columns([1, 2, 1], gap="large")

    with col1:
        with st.container(border=True):
            st.metric(label="Overall Match Score", value=result.get('match_score', 'N/A'))
            st.markdown(f"**Skill Gap:** {result.get('skill_gap_analysis', 'Not identified.')}")
            st.markdown(f"**Prep Hint:** {result.get('prep_hint', 'No specific hint available.')}")

    with col2:
        with st.container(border=True):
            st.subheader("📋 Full Extracted Data")
            df_display = pd.DataFrame([result]).T
            df_display.columns = ["Extracted Value"]
            st.dataframe(df_display, use_container_width=True)

    with col3:
        with st.container(border=True):
            st.subheader("💾 Downloads")
            # CSV Download
            output = io.StringIO()
            # Use keys from the analysis result for headers, ensuring it's valid for DictWriter
            required_keys = ["date_contacted", "hr_name", "phone_number", "email_id", "role_position", "recruiter_company", "client_company", "location", "job_type", "mode_of_contact", "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details", "ctc_offered_expected", "status", "next_follow_up_date", "review_notes", "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"]
            writer = csv.DictWriter(output, fieldnames=required_keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerow({k: result.get(k, "") for k in required_keys}) # Fill missing keys with empty string
            csv_data = output.getvalue()
            st.download_button(label="📄 Download Job Tracker (.csv)", data=csv_data, file_name="job_details.csv", mime="text/csv", use_container_width=True)
            
            # Calendar Download
            ics_data = create_ics_file(result)
            if ics_data:
                st.download_button(label="📅 Download Calendar Event (.ics)", data=ics_data, file_name="interview.ics", mime="text/calendar", use_container_width=True)

    st.markdown("---")
    if st.button("🔄 Start New Analysis"):
        # Reset the entire state
        st.session_state.app_state = {
            'current_view': 'start',
            'profile_data': "",
            'job_description': "",
            'skills_data': "",
            'analysis_result': None
        }
        st.rerun()

# --- 7. Main App Router ---
def main():
    load_css()
    
    view = st.session_state.app_state['current_view']
    
    if view == 'start':
        draw_start_view()
    elif view == 'map':
        draw_map_view()
    elif view == 'results':
        draw_results_view()

if __name__ == "__main__":
    main()
