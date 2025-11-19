import os
import json
import csv
import io
import re
import pandas as pd
import datetime
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

# --- 1. Page Configuration (MUST be the first Streamlit command) ---
st.set_page_config(
    layout="wide",
    page_title="Job Agent Sheshu try this app",
    page_icon="🤖"
)

# --- 2. Configuration and Setup ---
load_dotenv()

# Try env var first, then Streamlit secrets
api_key = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY", None)

if not api_key:
    st.error(
        "CRITICAL ERROR: GOOGLE_API_KEY not found.\n\n"
        "Please set it as an environment variable or in Streamlit Secrets."
    )
    st.stop()

genai.configure(api_key=api_key)

@st.cache_resource
def get_model():
    """Return a cached Gemini model instance."""
    return genai.GenerativeModel('gemini-2.5-flash')

# --- 3. Session State Initialization ---
def reset_app_state():
    st.session_state.app_state = {
        'current_view': 'start',  # 'start', 'map', 'results'
        'profile_data': "",
        'job_description': "",
        'skills_data': "",
        'analysis_result': None,
    }

if 'app_state' not in st.session_state:
    reset_app_state()

if 'history' not in st.session_state:
    st.session_state.history = []

# --- 4. The AI Prompt ---
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 
1) Job Details (JD, email, call notes) and 
2) Applicant Skills (Resume/Summary).

You MUST:
- Infer as many fields as possible from context.
- Use "Not specified" if you truly cannot infer a value.

**CRITICAL INSTRUCTION:** 
You MUST return the output as a single, valid JSON object. 
Do not add any explanatory text, markdown formatting, or code fences.

**IMPORTANT FORMAT RULES:**
- "interview_scheduled_date" MUST be in the format "YYYY-MM-DD" only (e.g., "2025-01-30").
- "next_follow_up_date" SHOULD also be in the format "YYYY-MM-DD" where possible.
- "match_score" should be a numeric percentage from 0 to 100 (integer or string is fine).

**JSON Keys to use (all keys must be present in the JSON, even if value is "Not specified"):**
- "date_contacted"
- "hr_name"
- "phone_number"
- "email_id"
- "role_position"
- "recruiter_company"
- "client_company"
- "location"
- "job_type"
- "mode_of_contact"
- "interview_mode"
- "interview_scheduled_date"
- "round_1_details"
- "round_2_details"
- "ctc_offered_expected"
- "status"
- "next_follow_up_date"
- "review_notes"
- "extracted_keywords"
- "match_score"
- "skill_gap_analysis"
- "prep_hint"

**Input Text (Job Details & Applicant Skills):**
***
{text_input}
***
**JSON Output (ONLY the JSON object, nothing else):**
"""

# --- 5. Core Logic & Calendar Functions ---

def safe_json_from_response(text: str) -> dict:
    """
    Extract the first JSON object from the model's text response
    and parse it safely.
    """
    # Remove common code fences if present
    cleaned = text.strip().replace('```json', '').replace('```', '')
    # Try to find the first {...} block
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        # If no braces found, just try to parse the whole thing
        return json.loads(cleaned)
    json_str = match.group(0)
    return json.loads(json_str)

def process_recruiter_text(text_to_process: str) -> dict:
    model = get_model()
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        raw_text = response.text or ""
        parsed = safe_json_from_response(raw_text)
        return parsed
    except json.JSONDecodeError:
        return {
            "error": (
                "The AI returned an invalid JSON format. "
                "Raw output from the model was:\n\n"
                f"{response.text if 'response' in locals() else 'N/A'}"
            )
        }
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

def create_ics_file(details: dict) -> str:
    """
    Create a simple .ics calendar event based on the extracted details.
    Expects "interview_scheduled_date" in YYYY-MM-DD format.
    """
    date_str = details.get("interview_scheduled_date")
    if not date_str or date_str == "Not specified":
        return ""

    try:
        start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0)
        end_date = start_date + datetime.timedelta(hours=1)

        dt_format = "%Y%m%dT%H%M%S"
        summary = f"Interview: {details.get('role_position', 'Job')} @ {details.get('client_company', 'Client')}"
        description = (
            f"Role: {details.get('role_position', 'N/A')}\\n"
            f"Company: {details.get('client_company', 'N/A')}\\n"
            f"Location: {details.get('location', 'N/A')}\\n"
            f"Notes: {details.get('review_notes', 'N/A')}"
        )

        ics_content = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//AI Job Agent//EN\n"
            "BEGIN:VEVENT\n"
            f"UID:{datetime.datetime.now().strftime(dt_format)}-{hash(summary)}\n"
            f"DTSTAMP:{datetime.datetime.now().strftime(dt_format)}\n"
            f"DTSTART:{start_date.strftime(dt_format)}\n"
            f"DTEND:{end_date.strftime(dt_format)}\n"
            f"SUMMARY:{summary}\n"
            f"DESCRIPTION:{description}\n"
            "END:VEVENT\n"
            "END:VCALENDAR"
        )
        return ics_content
    except (ValueError, TypeError):
        return ""

# --- 6. UI Styling ---

def load_css():
    """Loads all custom CSS for the mind map UI."""
    st.markdown("""
    <style>
        /* --- Base & Fonts --- */
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

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
            padding: 2rem 2rem 2rem 2rem !important;
        }

        /* --- Custom Card Styling for Mind Map Nodes --- */
        .mind-map-card {
            background-color: #192b33;
            border: 1px solid #325567;
            border-radius: 0.75rem;
            padding: 1.5rem;
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
                        0 2px 4px -2px rgba(0, 0, 0, 0.1);
        }
        .mind-map-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 15px -3px rgba(19, 164, 236, 0.2),
                        0 4px 6px -4px rgba(19, 164, 236, 0.2);
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
            width: 100%;
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
        }
        .main-header h1 {
            font-size: 3rem;
            font-weight: 800;
            letter-spacing: -0.033em;
        }
        .main-header h2 {
            font-size: 2rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }
        .main-header p {
            font-size: 1.1rem;
            color: #92b7c9;
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

# --- 7. UI Rendering Functions ---

def draw_start_view():
    """Renders the initial view with the central 'Job Agent' node."""
    st.markdown(
        '<div class="main-header">'
        '<h1>Job Agent</h1>'
        '<p>Intelligently Map and Track Your Recruiter Conversations</p>'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown("""
    **How it works:**
    1. Paste your **profile/skills** and the **job description or recruiter email**  
    2. Let the AI extract all key details (role, company, dates, CTC, status, etc.)  
    3. Download a **CSV tracker** and an **Interview Calendar Event**  
    """)

    _, center_col, _ = st.columns([1, 1, 1])
    with center_col:
        if st.button("🚀 Start Mapping"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()

def draw_map_view():
    """Renders the main mind map interface for data input."""
    st.markdown(
        '<div class="main-header">'
        '<h2>Build Your Career Mind Map</h2>'
        '<p>Complete the nodes below to generate your analysis.</p>'
        '</div>',
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns(3, gap="large")

    with col1:
        st.markdown("""
            <div class="mind-map-card">
                <span class="material-symbols-outlined icon">person</span>
                <h2>Your Profile</h2>
                <p>Paste your resume summary, LinkedIn about, or key skills.</p>
            </div>
        """, unsafe_allow_html=True)

        profile_text = st.text_area(
            "Your Profile",
            height=200,
            key="profile_input",
            label_visibility="collapsed",
            placeholder="e.g., 5+ years in Python, data analysis, SQL, AWS; experience in fintech..."
        )
        st.session_state.app_state['profile_data'] = profile_text
        st.caption(f"{len(profile_text)} characters")

    with col2:
        st.markdown("""
            <div class="mind-map-card">
                <span class="material-symbols-outlined icon">description</span>
                <h2>Job Description</h2>
                <p>Paste the full JD, recruiter email, or call notes.</p>
            </div>
        """, unsafe_allow_html=True)

        jd_text = st.text_area(
            "Job Description",
            height=200,
            key="jd_input",
            label_visibility="collapsed",
            placeholder="Paste the full job description, email, or call summary here..."
        )
        st.session_state.app_state['job_description'] = jd_text
        st.caption(f"{len(jd_text)} characters")

    with col3:
        st.markdown("""
            <div class="mind-map-card">
                <span class="material-symbols-outlined icon">assessment</span>
                <h2>Extra Notes</h2>
                <p>Any additional notes, expectations, or comments.</p>
            </div>
        """, unsafe_allow_html=True)

        skills_text = st.text_area(
            "Skill Assessment",
            height=200,
            key="skills_input",
            label_visibility="collapsed",
            placeholder="Add extra notes, call summaries, expected CTC, notice period, etc."
        )
        st.session_state.app_state['skills_data'] = skills_text
        st.caption(f"{len(skills_text)} characters")

    st.markdown("---")

    is_ready = bool(
        st.session_state.app_state['profile_data'].strip()
        and st.session_state.app_state['job_description'].strip()
    )

    if not is_ready:
        st.info("Please fill at least **Your Profile** and **Job Description** to run the analysis.")

    if st.button("✨ Generate Analysis", disabled=not is_ready):
        combined_text = (
            f"--- APPLICANT SKILLS ---\n{st.session_state.app_state['profile_data']}\n\n"
            f"--- JOB DETAILS ---\n{st.session_state.app_state['job_description']}\n\n"
            f"--- ADDITIONAL NOTES ---\n{st.session_state.app_state['skills_data']}"
        )

        with st.spinner("🧠 The AI is running the match & extraction analysis..."):
            result = process_recruiter_text(combined_text)
            st.session_state.app_state['analysis_result'] = result
            if "error" not in result:
                # Keep a simple history for this session
                st.session_state.history.append(result)
            st.session_state.app_state['current_view'] = 'results'
            st.rerun()

def draw_results_view():
    """Renders the final analysis results."""
    st.markdown(
        '<div class="main-header">'
        '<h2>Job Match & Tracker Analysis</h2>'
        '<p>An at-a-glance analysis of your profile against the recruiter/job details.</p>'
        '</div>',
        unsafe_allow_html=True
    )

    result = st.session_state.app_state['analysis_result']

    if not result:
        st.error("No analysis result found. Please go back and run the analysis again.")
        if st.button("⬅️ Go Back"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()
        return

    if "error" in result:
        st.error(result.get("error", "An unknown error occurred during analysis."))
        if st.button("⬅️ Go Back"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()
        return

    # Try to cast match_score to int if possible
    raw_score = result.get('match_score', 'N/A')
    try:
        match_score_value = int(str(raw_score).replace('%', '').strip())
        match_score_display = f"{match_score_value}%"
    except Exception:
        match_score_value = None
        match_score_display = str(raw_score)

    # --- Layout ---
    # Top summary row
    summary_container = st.container()
    with summary_container:
        col_a, col_b, col_c = st.columns([1, 2, 1], gap="large")

        with col_a:
            with st.container(border=True):
                st.metric(label="Overall Match Score", value=match_score_display)
                st.markdown(f"**Status:** {result.get('status', 'Not specified')}")
                st.markdown(f"**Next Follow-up:** {result.get('next_follow_up_date', 'Not specified')}")

        with col_b:
            with st.container(border=True):
                st.subheader("🧩 Summary")
                st.markdown(f"- **Role:** {result.get('role_position', 'Not specified')}")
                st.markdown(f"- **Recruiter / Company:** {result.get('recruiter_company', 'Not specified')}")
                st.markdown(f"- **Client Company:** {result.get('client_company', 'Not specified')}")
                st.markdown(f"- **Location:** {result.get('location', 'Not specified')}")
                st.markdown(f"- **Job Type:** {result.get('job_type', 'Not specified')}")
                st.markdown(f"- **Mode of Contact:** {result.get('mode_of_contact', 'Not specified')}")

        with col_c:
            with st.container(border=True):
                st.subheader("🎯 Prep & Gap")
                st.markdown(f"**Skill Gap:** {result.get('skill_gap_analysis', 'Not identified.')}")
                st.markdown(f"**Prep Hint:** {result.get('prep_hint', 'No specific hint available.')}")

    st.markdown("---")

    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        with st.container(border=True):
            st.subheader("📋 Full Extracted Data")
            df_display = pd.DataFrame([result]).T
            df_display.columns = ["Extracted Value"]
            st.dataframe(df_display, use_container_width=True)

    with col2:
        with st.container(border=True):
            st.subheader("💾 Downloads")

            # CSV Download
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=result.keys())
            writer.writeheader()
            writer.writerow(result)
            csv_data = output.getvalue()
            st.download_button(
                label="📄 Download Job Tracker (.csv)",
                data=csv_data,
                file_name="job_details.csv",
                mime="text/csv",
                use_container_width=True
            )

            # Calendar Download
            ics_data = create_ics_file(result)
            if ics_data:
                st.download_button(
                    label="📅 Download Calendar Event (.ics)",
                    data=ics_data,
                    file_name="interview.ics",
                    mime="text/calendar",
                    use_container_width=True
                )
            else:
                st.caption(
                    "No valid interview date found to create a calendar event "
                    "(check that the model returned YYYY-MM-DD)."
                )

    st.markdown("---")

    if st.session_state.history:
        with st.expander("🧾 View this session's history"):
            hist_df = pd.DataFrame(st.session_state.history)
            st.dataframe(hist_df, use_container_width=True)

    col_back, col_new = st.columns(2)
    with col_back:
        if st.button("⬅️ Edit Inputs"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()
    with col_new:
        if st.button("🔄 Start New Analysis"):
            reset_app_state()
            st.rerun()

# --- 8. Main App Router ---

def main():
    load_css()

    # Sidebar
    with st.sidebar:
        st.markdown("### 🤖 Job Agent")
        st.markdown(
            "Turn messy JDs, emails, and call notes into a **structured job tracker** "
            "with follow-up dates and interview events."
        )
        st.markdown("**Steps:**")
        st.markdown("1. Paste your profile & the job details\n2. Click *Generate Analysis*\n3. Download CSV / Calendar")
        st.markdown("---")
        if st.session_state.app_state.get('analysis_result'):
            st.markdown("**Last Match Score:**")
            last = st.session_state.app_state['analysis_result']
            st.write(last.get('match_score', 'N/A'))

    view = st.session_state.app_state['current_view']

    if view == 'start':
        draw_start_view()
    elif view == 'map':
        draw_map_view()
    elif view == 'results':
        draw_results_view()
    else:
        # Fallback in case of any weird state
        reset_app_state()
        draw_start_view()

if __name__ == "__main__":
    main()
