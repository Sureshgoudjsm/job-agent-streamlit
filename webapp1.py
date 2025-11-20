# streamlit_app_jd_whisperer_drive_logo.py
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

# Optional Google Sheets libs
try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSHEETS_LIBS = True
except ImportError:
    HAS_GSHEETS_LIBS = False

# ------------------------------
#  PAGE CONFIG (brand)
# ------------------------------
st.set_page_config(
    page_title="JD Whisperer",
    layout="wide",
    page_icon="🤫"
)

# ------------------------------
#  LOGO SOURCE: Google Drive direct URL (Option A)
#  Replace the ID if you ever change files.
# ------------------------------
DRIVE_FILE_ID = "1DJoP8qI8X5mgFnuB3eQueC_WbX7_AT5n"
# Direct view URL for Google Drive files
LOGO_URL = f"https://drive.google.com/uc?export=view&id={DRIVE_FILE_ID}"

# Optional local fallback path (if you upload later)
LOCAL_LOGO_PATH = "/mnt/data/your_uploaded_logo.png"

# ------------------------------
#  ENV + AI CONFIG
# ------------------------------
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY", None)
if not API_KEY:
    st.error("CRITICAL: GOOGLE_API_KEY not set. Add to env or Streamlit Secrets.")
    st.stop()

genai.configure(api_key=API_KEY)

@st.cache_resource
def get_model():
    return genai.GenerativeModel('gemini-2.5-flash')

# ------------------------------
#  GOOGLE SHEETS (optional persistence)
# ------------------------------
FIELD_ORDER = [
    "date_contacted","hr_name","phone_number","email_id","role_position",
    "recruiter_company","client_company","location","job_type","mode_of_contact",
    "interview_mode","interview_scheduled_date","round_1_details","round_2_details",
    "ctc_offered_expected","status","next_follow_up_date","review_notes",
    "extracted_keywords","match_score","skill_gap_analysis","prep_hint"
]

def _get_gsheets_creds_and_id():
    try:
        sheet_id = st.secrets.get("GOOGLE_SHEET_ID", None)
        sa_info = st.secrets.get("GOOGLE_SERVICE_ACCOUNT", None)
        if not sheet_id or not sa_info:
            return None, None
        if isinstance(sa_info, str):
            creds_dict = json.loads(sa_info)
        else:
            creds_dict = dict(sa_info)
        return creds_dict, sheet_id
    except Exception:
        return None, None

@st.cache_resource
def get_gsheets_worksheet():
    if not HAS_GSHEETS_LIBS:
        return None
    creds_dict, sheet_id = _get_gsheets_creds_and_id()
    if not creds_dict or not sheet_id:
        return None
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(sheet_id)
    ws = sh.sheet1
    try:
        existing_values = ws.get_all_values()
        if not existing_values:
            headers = ["timestamp_utc"] + FIELD_ORDER
            ws.append_row(headers, value_input_option="USER_ENTERED")
    except Exception:
        pass
    return ws

def save_history_to_gsheets(result: dict):
    try:
        ws = get_gsheets_worksheet()
        if ws is None:
            return
        timestamp = datetime.datetime.utcnow().isoformat()
        row = [timestamp] + [result.get(k, "") for k in FIELD_ORDER]
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        st.warning(f"Could not save to Google Sheets: {e}")

def load_history_dataframe() -> pd.DataFrame:
    df = None
    try:
        ws = get_gsheets_worksheet()
    except Exception:
        ws = None
    if ws is not None:
        try:
            records = ws.get_all_records()
            if records:
                df = pd.DataFrame(records)
        except Exception as e:
            st.warning(f"Could not load history from Google Sheets: {e}")
    if (df is None or df.empty) and st.session_state.get("history"):
        df = pd.DataFrame(st.session_state.get("history"))
    if df is None:
        df = pd.DataFrame()
    return df

# ------------------------------
#  SESSION STATE (clear comments where used)
# ------------------------------
def reset_app_state():
    """
    Resets the core app_state dict.
    - current_view: controls which screen (start/map/results)
    - profile_data, job_description, skills_data: inputs
    - analysis_result: last AI output
    """
    st.session_state.app_state = {
        'current_view': 'start',
        'profile_data': "",
        'job_description': "",
        'skills_data': "",
        'analysis_result': None
    }

# app_state: main flow container
if 'app_state' not in st.session_state:
    reset_app_state()

# history: in-memory runs for current browser session
if 'history' not in st.session_state:
    st.session_state['history'] = []

# mode: 'Analyze' or 'History' (used by sidebar buttons)
if 'mode' not in st.session_state:
    st.session_state['mode'] = 'Analyze'

# ------------------------------
#  EXTRACTION PROMPT
# ------------------------------
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts:
1) Job Details (JD, email, call notes) and
2) Applicant Skills (Resume/Summary).

You MUST:
- Infer as many fields as possible from context.
- Use "Not specified" if you truly cannot infer a value.

CRITICAL: Return a single, valid JSON object only.

FIELD-SPECIFIC RULES:
- "interview_scheduled_date" as "YYYY-MM-DD"
- "skill_gap_analysis": VERY SHORT (2-3 sentences max)
- "prep_hint": 1-2 short sentences

JSON Keys (all must be present):
""" + ", ".join(FIELD_ORDER + ["match_score","skill_gap_analysis","prep_hint"]) + """

Input:
***
{text_input}
***
Return ONLY the JSON object.
"""

# ------------------------------
#  HELPERS
# ------------------------------
def safe_json_from_response(text: str) -> dict:
    cleaned = text.strip().replace('```json', '').replace('```', '')
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if not match:
        return json.loads(cleaned)
    return json.loads(match.group(0))

def keep_first_sentences(text: str, max_sentences: int = 3) -> str:
    if not isinstance(text, str):
        return text
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s for s in sentences if s]
    if not sentences:
        return text
    return " ".join(sentences[:max_sentences])

def process_recruiter_text(text_to_process: str) -> dict:
    model = get_model()
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        raw_text = response.text or ""
        parsed = safe_json_from_response(raw_text)
        for key in ("skill_gap_analysis", "prep_hint"):
            if key in parsed and isinstance(parsed[key], str):
                parsed[key] = keep_first_sentences(parsed[key], 3)
        return parsed
    except json.JSONDecodeError:
        return {"error": f"Invalid JSON returned. Raw: {response.text if 'response' in locals() else 'N/A'}"}
    except Exception as e:
        return {"error": f"Error: {e}"}

def create_ics_file(details: dict) -> str:
    date_str = details.get("interview_scheduled_date")
    if not date_str or date_str == "Not specified":
        return ""
    try:
        start_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0)
        end_date = start_date + datetime.timedelta(hours=1)
        dt_format = "%Y%m%dT%H%M%S"
        summary = f"Interview: {details.get('role_position', 'Job')} @ {details.get('client_company', 'Client')}"
        description = f"Role: {details.get('role_position','N/A')}\\nCompany: {details.get('client_company','N/A')}\\nNotes: {details.get('review_notes','')}"
        ics_content = (
            "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//JD Whisperer//EN\nBEGIN:VEVENT\n"
            f"UID:{datetime.datetime.now().strftime(dt_format)}-{hash(summary)}\n"
            f"DTSTAMP:{datetime.datetime.now().strftime(dt_format)}\n"
            f"DTSTART:{start_date.strftime(dt_format)}\n"
            f"DTEND:{end_date.strftime(dt_format)}\n"
            f"SUMMARY:{summary}\nDESCRIPTION:{description}\nEND:VEVENT\nEND:VCALENDAR"
        )
        return ics_content
    except Exception:
        return ""

def sanitize_df_for_streamlit(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if df[col].map(lambda x: isinstance(x, (dict, list, set, tuple))).any():
            df[col] = df[col].map(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list, set, tuple)) else x)
    return df

# ------------------------------
#  BRAND CSS (Manrope + Inter, gradient whisper lines)
# ------------------------------
def load_brand_css():
    st.markdown(f"""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Manrope:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
    :root{{
        --bg: #0B1E37;
        --surface: #122642;
        --muted: #9EACBE;
        --text: #F5F9FF;
        --accent-1: #4C8CFF;
        --accent-2: #6A5CFF;
        --accent-3: #00D4D0;
    }}
    body {{
        font-family: 'Inter', 'Manrope', sans-serif;
        background: var(--bg) !important;
        color: var(--text) !important;
    }}
    .stApp .block-container {{
        padding: 2rem 2rem 3rem 2rem !important;
        background: linear-gradient(180deg, rgba(11,30,55,0.95) 0%, rgba(17,38,66,0.95) 100%);
        border-radius: 8px;
    }}
    .main-header {{
        text-align: left;
        padding: 1rem 0;
        display:flex;
        align-items:center;
        gap:1rem;
    }}
    .main-header img.logo {{
        height:56px;
    }}
    .main-header h1 {{
        margin:0;
        font-family: 'Manrope', sans-serif;
        font-weight: 800;
        font-size: 34px;
        color: var(--text);
        letter-spacing: -0.02em;
        background: linear-gradient(90deg, var(--accent-1), var(--accent-2), var(--accent-3));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .main-header p {{
        margin:0;
        color: var(--muted);
        font-size: 14px;
    }}
    .mind-map-card {{
        background: linear-gradient(180deg, rgba(22,38,60,0.6), rgba(17,30,45,0.45));
        border: 1px solid rgba(76,140,255,0.12);
        border-radius: 12px;
        padding: 18px;
        text-align:center;
    }}
    .stButton > button {{
        background: linear-gradient(90deg, var(--accent-1), var(--accent-2)) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 10px 14px !important;
        font-weight: 700 !important;
        border: none !important;
    }}
    .stButton > button:hover {{
        filter: brightness(1.03);
    }}
    .stMetric > div > div > div {{
        color: var(--accent-3) !important;
    }}
    .results-card {{
        background: linear-gradient(180deg, rgba(8,20,36,0.45), rgba(16,28,42,0.6));
        border-radius: 12px;
        padding: 16px;
        border: 1px solid rgba(106,92,255,0.12);
    }}
    .sidebar .stMarkdown p, .sidebar .stMarkdown li {{
        color: var(--muted) !important;
    }}
    .whisper-divider {{
        height:6px;
        border-radius:6px;
        background: linear-gradient(90deg, var(--accent-1), var(--accent-2), var(--accent-3));
        margin: 16px 0;
    }}
    </style>
    """, unsafe_allow_html=True)

# ------------------------------
#  UI: Start / Map / Results / History
# ------------------------------
def try_show_logo(width=72):
    """
    Try to display the logo from Drive URL. Fallback to local path if Drive load fails.
    (st.image will usually handle remote URLs; fallback is just a try/except)
    """
    try:
        st.image(LOGO_URL, width=width)
    except Exception:
        # fallback if local file was uploaded
        if os.path.exists(LOCAL_LOGO_PATH):
            st.image(LOCAL_LOGO_PATH, width=width)

def draw_start_view():
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    try:
        # show logo from Drive URL
        st.image(LOGO_URL, width=72, use_column_width=False)
    except Exception:
        # fallback to local if available
        if os.path.exists(LOCAL_LOGO_PATH):
            st.image(LOCAL_LOGO_PATH, width=72)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="display:flex;flex-direction:column;gap:6px">', unsafe_allow_html=True)
    st.markdown('<h1>JD Whisperer</h1>', unsafe_allow_html=True)
    st.markdown('<p>Decode job descriptions into clear candidate insights — skills, gaps, match score & follow-ups.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    _, center_col, _ = st.columns([1,1,1])
    with center_col:
        if st.button("🚀 Start Mapping"):
            # session: move to map
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()

def draw_map_view():
    st.markdown('<div style="display:flex;gap:1rem;align-items:center;">', unsafe_allow_html=True)
    st.markdown('<h2 style="margin:0;color:var(--text)">Build Your Career Mind Map</h2>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")
    with col1:
        st.markdown('<div class="mind-map-card"><h3>Your Profile</h3><p>Paste resume summary or LinkedIn About.</p></div>', unsafe_allow_html=True)
        profile_text = st.text_area("Your Profile", height=200, key="profile_input", label_visibility="collapsed", placeholder="e.g., 5+ years in Python, AWS, SQL...")
        st.session_state.app_state['profile_data'] = profile_text
        st.caption(f"{len(profile_text)} characters")

    with col2:
        st.markdown('<div class="mind-map-card"><h3>Job Description</h3><p>Paste the JD, recruiter email, or call notes.</p></div>', unsafe_allow_html=True)
        jd_text = st.text_area("Job Description", height=200, key="jd_input", label_visibility="collapsed", placeholder="Paste JD here...")
        st.session_state.app_state['job_description'] = jd_text
        st.caption(f"{len(jd_text)} characters")

    with col3:
        st.markdown('<div class="mind-map-card"><h3>Extra Notes</h3><p>CTC, notice period, call summary.</p></div>', unsafe_allow_html=True)
        skills_text = st.text_area("Skill Assessment", height=200, key="skills_input", label_visibility="collapsed", placeholder="Additional notes...")
        st.session_state.app_state['skills_data'] = skills_text
        st.caption(f"{len(skills_text)} characters")

    st.markdown('<div class="whisper-divider"></div>', unsafe_allow_html=True)

    is_ready = bool(st.session_state.app_state['profile_data'].strip() and st.session_state.app_state['job_description'].strip())
    if not is_ready:
        st.info("Please fill at least Your Profile and Job Description to generate analysis.")

    if st.button("✨ Generate Analysis", disabled=not is_ready):
        combined_text = (
            f"--- APPLICANT SKILLS ---\n{st.session_state.app_state['profile_data']}\n\n"
            f"--- JOB DETAILS ---\n{st.session_state.app_state['job_description']}\n\n"
            f"--- ADDITIONAL NOTES ---\n{st.session_state.app_state['skills_data']}"
        )
        with st.spinner("🧠 JD Whisperer is analyzing..."):
            result = process_recruiter_text(combined_text)
            st.session_state.app_state['analysis_result'] = result
            if "error" not in result:
                st.session_state['history'].append(result)
                save_history_to_gsheets(result)
            st.session_state.app_state['current_view'] = 'results'
            st.rerun()

def draw_results_view():
    st.markdown('<div style="display:flex;justify-content:space-between;align-items:center">', unsafe_allow_html=True)
    left, right = st.columns([1,4])
    with left:
        try:
            st.image(LOGO_URL, width=64)
        except Exception:
            if os.path.exists(LOCAL_LOGO_PATH):
                st.image(LOCAL_LOGO_PATH, width=64)
    with right:
        st.markdown('<h2 style="margin:0">Job Match & Tracker Analysis</h2>', unsafe_allow_html=True)
        st.markdown('<p style="margin:0;color:var(--muted)">An at-a-glance analysis of your profile against the recruiter/job details.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    result = st.session_state.app_state.get('analysis_result')
    if not result:
        st.error("No analysis found. Please run an analysis.")
        if st.button("⬅️ Go Back"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()
        return
    if "error" in result:
        st.error(result.get("error"))
        if st.button("⬅️ Go Back"):
            st.session_state.app_state['current_view'] = 'map'
            st.rerun()
        return

    raw_score = result.get('match_score','N/A')
    try:
        match_score_display = f"{int(str(raw_score).replace('%','').strip())}%"
    except Exception:
        match_score_display = str(raw_score)

    col1, col2 = st.columns([1,2], gap="large")
    with col1:
        st.metric(label="Overall Match Score", value=match_score_display)
        st.markdown(f"**Status:** {result.get('status','Not specified')}")
        st.markdown(f"**Next Follow-up:** {result.get('next_follow_up_date','Not specified')}")

    with col2:
        st.subheader("🧩 Summary")
        st.markdown(f"- **Role:** {result.get('role_position','Not specified')}")
        st.markdown(f"- **Company:** {result.get('client_company','Not specified')}")
        st.markdown(f"- **Location:** {result.get('location','Not specified')}")
        st.markdown(f"- **Mode:** {result.get('mode_of_contact','Not specified')}")

    st.markdown('<div class="whisper-divider"></div>', unsafe_allow_html=True)

    st.subheader("🎯 Prep & Gap")
    st.markdown(f"**Skill Gap (short):** {result.get('skill_gap_analysis','Not identified.')}")
    st.markdown(f"**Prep Hint:** {result.get('prep_hint','No hint available.')}")

    st.markdown('---')

    colL, colR = st.columns([2,1], gap="large")
    with colL:
        st.subheader("📋 Full Extracted Data")
        df_display = pd.DataFrame([result]).T
        df_display.columns = ["Extracted Value"]
        df_display = sanitize_df_for_streamlit(df_display)
        st.dataframe(df_display, use_container_width=True)
    with colR:
        st.subheader("💾 Downloads")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=result.keys())
        writer.writeheader()
        writer.writerow(result)
        csv_data = output.getvalue()
        st.download_button("📄 Download Job Tracker (.csv)", data=csv_data, file_name="job_details.csv", mime="text/csv", use_container_width=True)
        ics_data = create_ics_file(result)
        if ics_data:
            st.download_button("📅 Download Calendar Event (.ics)", data=ics_data, file_name="interview.ics", mime="text/calendar", use_container_width=True)
        else:
            st.caption("No valid interview date found to create a calendar event (YYYY-MM-DD expected).")

    st.markdown('---')
    if st.session_state.get('history'):
        with st.expander("🧾 View this session's history"):
            hist_df = pd.DataFrame(st.session_state['history'])
            hist_df = sanitize_df_for_streamlit(hist_df)
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

def draw_history_view():
    st.markdown('<div style="display:flex;align-items:center;gap:1rem">', unsafe_allow_html=True)
    try:
        st.image(LOGO_URL, width=56)
    except Exception:
        if os.path.exists(LOCAL_LOGO_PATH):
            st.image(LOCAL_LOGO_PATH, width=56)
    st.markdown('<h2 style="margin:0">📊 History Dashboard</h2>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    df = load_history_dataframe()
    if df.empty:
        st.info("No history found yet.")
        return
    if "timestamp_utc" in df.columns:
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")
    # Metrics
    c1,c2,c3 = st.columns(3)
    c1.metric("Total Records", len(df))
    if "role_position" in df.columns:
        c2.metric("Unique Roles", df["role_position"].fillna("").nunique())
    else:
        c2.metric("Unique Roles","-")
    if "status" in df.columns:
        c3.metric("Statuses", df["status"].fillna("").nunique())
    else:
        c3.metric("Statuses","-")
    st.markdown('---')
    # Filters
    st.subheader("🔍 Filters")
    left, right = st.columns([3,1])
    with left:
        text_query = st.text_input("Search role / recruiter / client", placeholder="e.g., Python, Accenture")
    with right:
        if "status" in df.columns:
            status_opts = sorted([s for s in df["status"].dropna().unique() if s])
        else:
            status_opts = []
        status_filter = st.multiselect("Status", options=status_opts, default=status_opts)
    date_range = None
    if "timestamp_utc" in df.columns and df["timestamp_utc"].notna().any():
        min_d = df["timestamp_utc"].min().date()
        max_d = df["timestamp_utc"].max().date()
        date_range = st.slider("Date range", min_value=min_d, max_value=max_d, value=(min_d, max_d))
    mask = pd.Series(True, index=df.index)
    if text_query:
        q = text_query.lower()
        cols_to_search=[]
        for name in ["role_position","recruiter_company","client_company"]:
            if name in df.columns:
                cols_to_search.append(df[name].fillna("").str.lower())
        if cols_to_search:
            combined = cols_to_search[0].str.contains(q)
            for extra in cols_to_search[1:]:
                combined = combined | extra.str.contains(q)
            mask &= combined
    if status_filter and "status" in df.columns:
        mask &= df["status"].fillna("").isin(status_filter)
    if date_range and "timestamp_utc" in df.columns:
        s,e = date_range
        mask &= (df["timestamp_utc"].dt.date >= s) & (df["timestamp_utc"].dt.date <= e)
    df_filtered = df[mask].copy()
    df_filtered = sanitize_df_for_streamlit(df_filtered)
    st.markdown(f"Showing **{len(df_filtered)}** records")
    st.markdown('---')
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

# ------------------------------
#  MAIN: sidebar + routing
# ------------------------------
def main():
    load_brand_css()

    # Sidebar with brand logo + mode buttons (stored in session_state['mode'])
    with st.sidebar:
        st.markdown("<div style='display:flex;align-items:center;gap:8px'>", unsafe_allow_html=True)
        try:
            st.image(LOGO_URL, width=48)
        except Exception:
            if os.path.exists(LOCAL_LOGO_PATH):
                st.image(LOCAL_LOGO_PATH, width=48)
        st.markdown("<div><strong>JD Whisperer</strong><br><small style='color:var(--muted)'>Decode any job description</small></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("#### Mode")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Analyze", use_container_width=True, key="mode_analyze_btn"):
                st.session_state['mode'] = "Analyze"
                st.rerun()
        with col_b:
            if st.button("History", use_container_width=True, key="mode_history_btn"):
                st.session_state['mode'] = "History"
                st.rerun()
        st.caption(f"Current mode: **{st.session_state['mode']}**")

        st.markdown("---")
        st.markdown("**Steps (Analyze mode):**\n1. Paste profile & JD\n2. Click Generate Analysis\n3. Download CSV / Calendar")

        creds_dict, sheet_id = _get_gsheets_creds_and_id()
        if HAS_GSHEETS_LIBS and creds_dict and sheet_id:
            st.success("Google Sheets logging: ON")
        else:
            st.info("Google Sheets logging: OFF (configure secrets)")

        st.markdown('---')
        if st.session_state.app_state.get('analysis_result'):
            st.markdown("**Last Match Score:**")
            st.write(st.session_state.app_state['analysis_result'].get('match_score','N/A'))

    mode = st.session_state.get('mode', 'Analyze')
    if mode == "History":
        draw_history_view()
        return

    view = st.session_state.app_state.get('current_view','start')
    if view == 'start':
        draw_start_view()
    elif view == 'map':
        draw_map_view()
    elif view == 'results':
        draw_results_view()
    else:
        reset_app_state()
        draw_start_view()

if __name__ == "__main__":
    main()
