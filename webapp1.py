import os
import json
import csv
import io
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st
import pandas as pd
from filelock import FileLock

# --- Configuration ---
load_dotenv()
CSV_PATH = "job_contacts.csv"
LOCK_PATH = CSV_PATH + ".lock"

# Ensure Google API key
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

# --- Prompt (unchanged from your version) ---
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided texts: 1) Job Details (JD, email, call notes) and 2) Applicant Skills (Resume/Summary).

**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```json. Your entire response should be only the JSON object itself. If a piece of information is not available, the value for that key MUST BE "Not specified".

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
---
{text_input}
---

**JSON Output:**
"""

# --- Utility: Ensure CSV exists with headers ---
HEADERS = [
    "Date", "Timestamp", "EntryID",
    "date_contacted","hr_name","phone_number","email_id","role_position",
    "recruiter_company","client_company","location","job_type","mode_of_contact",
    "interview_mode","interview_scheduled_date","round_1_details","round_2_details",
    "ctc_offered_expected","status","next_follow_up_date","review_notes",
    "extracted_keywords","match_score","skill_gap_analysis","prep_hint"
]

def ensure_csv():
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=HEADERS)
        df.to_csv(CSV_PATH, index=False)

# --- Core: call Gemini and parse JSON ---
def process_recruiter_text(text_to_process: str) -> dict:
    """
    Sends text to the Gemini model, expects a JSON response, and parses it into a Python dictionary.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        clean_response = response.text.strip()
        # strip common fences if any
        clean_response = clean_response.replace("```json", "").replace("```", "").strip()
        parsed_json = json.loads(clean_response)
        # Normalize missing keys to "Not specified"
        for key in [
            "date_contacted","hr_name","phone_number","email_id","role_position",
            "recruiter_company","client_company","location","job_type","mode_of_contact",
            "interview_mode","interview_scheduled_date","round_1_details","round_2_details",
            "ctc_offered_expected","status","next_follow_up_date","review_notes",
            "extracted_keywords","match_score","skill_gap_analysis","prep_hint"
        ]:
            if key not in parsed_json or parsed_json[key] in [None, ""]:
                parsed_json[key] = "Not specified"
        return parsed_json
    except json.JSONDecodeError:
        return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

# --- iCalendar generator (keeps your original logic, improved UID) ---
def create_ics_file(details: dict) -> str:
    """Generates an iCalendar (.ics) string from extracted job details."""
    date_str = details.get("interview_scheduled_date", "Not specified")
    role = details.get("role_position", "Job Interview")
    client = details.get("client_company", "Client Company")
    recruiter = details.get("hr_name", "Recruiter")
    mode = details.get("interview_mode", "Mode Not Specified")

    try:
        # Accept common ISO formats or fallback
        start_date = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=10, minute=0, second=0)
        end_date = start_date + timedelta(hours=1)
        dt_format = "%Y%m%dT%H%M%S"
        dt_start = start_date.strftime(dt_format)
        dt_end = end_date.strftime(dt_format)
        dt_stamp = datetime.now().strftime(dt_format)
    except Exception:
        return ""  # if date parsing fails, return empty so UI doesn't show download

    summary = f"Interview: {role} @ {client}"
    description = (
        f"Role: {role}\\n"
        f"Company: {client}\\n"
        f"Recruiter: {recruiter}\\n"
        f"Round 1 Details: {details.get('round_1_details', 'N/A')}\\n"
        f"Mode: {mode}\\n"
        f"HR Contact: {details.get('email_id', 'N/A')} / {details.get('phone_number', 'N/A')}"
    )
    uid = f"{uuid.uuid4()}@jobaiagent"
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AI Job Agent//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dt_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{summary}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR"""
    return ics_content.replace("\n", "\r\n")

# --- CSV append with file lock & duplicate detection ---
def read_all_entries() -> pd.DataFrame:
    ensure_csv()
    return pd.read_csv(CSV_PATH)

def append_row_to_csv(row: dict):
    ensure_csv()
    lock = FileLock(LOCK_PATH, timeout=10)
    with lock:
        df = pd.read_csv(CSV_PATH)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        df.to_csv(CSV_PATH, index=False)

def detect_duplicate(df: pd.DataFrame, candidate: dict, days_window: int = 14) -> pd.DataFrame:
    """
    Heuristic duplicate detection:
     - Exact phone number match OR
     - email + role match within last `days_window` days
    Returns matching rows (may be empty).
    """
    matches = pd.DataFrame()
    phone = candidate.get("phone_number", "").strip()
    email = candidate.get("email_id", "").strip()
    role = candidate.get("role_position", "").strip()
    # check phone match
    if phone and phone != "Not specified":
        matches = df[df["phone_number"].astype(str).str.strip() == phone]
    # email+role match (and recent)
    if matches.empty and email and email != "Not specified" and role and role != "Not specified":
        recent_cutoff = datetime.now() - timedelta(days=days_window)
        # Parse timestamp column to datetime safely
        df_ts = df.copy()
        if "Timestamp" in df_ts.columns:
            try:
                df_ts["__ts_parsed"] = pd.to_datetime(df_ts["Timestamp"], errors='coerce')
            except Exception:
                df_ts["__ts_parsed"] = pd.NaT
        else:
            df_ts["__ts_parsed"] = pd.NaT
        cond_email_role = (
            (df_ts["email_id"].astype(str).str.strip() == email) &
            (df_ts["role_position"].astype(str).str.strip() == role) &
            (df_ts["__ts_parsed"] >= recent_cutoff)
        )
        matches = df_ts[cond_email_role]
    return matches

# --- Streamlit UI ---
st.set_page_config(page_title="AI Job Agent", layout="wide")
st.title("🤖 AI Job Agent — Job Contact & Interview Extractor")

# Left: Form. Right: Table + filters
col1, col2 = st.columns([1, 1.6])

with col1:
    st.subheader("Step 1 — Provide your info")

    with st.form(key="entry_form"):
        st.markdown("**Applicant Skills** (for match score)")
        applicant_skills = st.text_area(
            "Paste your key skills, technologies, and years of experience here.",
            height=140,
            placeholder="e.g., Python (5 years), AWS (3 years), Terraform, SQL, React..."
        )

        st.markdown("**Call / Mail Summary**")
        call_details = st.text_input(
            "Summarize your conversation with the recruiter (one or two lines).",
            placeholder="e.g., Spoke with Priya from ABC Staffing re: Data Analyst role..."
        )

        st.markdown("**Full Job Description / Email / JD**")
        recruiter_text = st.text_area(
            "Paste the full JD, email or other source text here.",
            height=300,
            placeholder="Full JD, email, interview scheduling text..."
        )

        submitted = st.form_submit_button("✨ Extract, Append & Prepare Files")

    st.markdown("---")
    st.subheader("Quick actions / Settings")
    show_duplicates_setting = st.checkbox("Warn on probable duplicates", value=True)
    days_window = st.number_input("Duplicate window (days)", value=14, min_value=1, max_value=365)

with col2:
    st.subheader("Saved Contacts / Filters")

    # Load entries
    ensure_csv()
    df_all = read_all_entries()

    # Filters
    filter_status = st.multiselect("Filter by status", options=sorted(df_all["status"].unique()) if not df_all.empty else [], default=[])
    search_text = st.text_input("Search (role/company/HR/email/phone)")

    df_view = df_all.copy()
    if filter_status:
        df_view = df_view[df_view["status"].isin(filter_status)]
    if search_text:
        s = search_text.strip().lower()
        df_view = df_view[df_view.apply(lambda r: s in str(r.get("role_position","")).lower()
                                       or s in str(r.get("client_company","")).lower()
                                       or s in str(r.get("hr_name","")).lower()
                                       or s in str(r.get("email_id","")).lower()
                                       or s in str(r.get("phone_number","")).lower(), axis=1)]

    st.write(f"Showing {len(df_view)} entries")
    # Show table (most recent first)
    if "Timestamp" in df_view.columns:
        try:
            df_view["__ts_parsed"] = pd.to_datetime(df_view["Timestamp"], errors="coerce")
            df_view = df_view.sort_values("__ts_parsed", ascending=False).drop(columns="__ts_parsed")
        except Exception:
            pass

    st.dataframe(df_view[HEADERS].fillna(""), use_container_width=True)

    # Download current CSV (filtered or full)
    csv_buffer = io.StringIO()
    df_view.to_csv(csv_buffer, index=False)
    st.download_button("Download current list (.csv)", data=csv_buffer.getvalue(), file_name="job_contacts_export.csv", mime="text/csv")

# --- Handle submission: call AI, show results, append to CSV if accepted ---
if submitted:
    combined_text = (
        f"--- APPLICANT SKILLS ---\n{applicant_skills}\n\n"
        f"--- JOB DETAILS ---\n"
        f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
    )

    if not (call_details.strip() or recruiter_text.strip()):
        st.warning("Please provide call details or JD text before submitting.")
    else:
        with st.spinner("🧠 Analyzing with Gemini..."):
            structured = process_recruiter_text(combined_text)

        if "error" in structured:
            st.error(structured["error"])
        else:
            st.success("✔ Extraction complete — review below.")
            # Present results in a neat table
            df_extracted = pd.DataFrame([structured]).T
            df_extracted.columns = ["Extracted Value"]
            st.subheader("Extracted Fields")
            st.dataframe(df_extracted, use_container_width=True)

            # Build the row to append to CSV (normalize to our HEADERS)
            timestamp = datetime.utcnow().isoformat()
            entry_id = str(uuid.uuid4())
            csv_row = {
                "Date": structured.get("date_contacted", "Not specified"),
                "Timestamp": timestamp,
                "EntryID": entry_id,
            }
            for key in HEADERS:
                if key in ["Date", "Timestamp", "EntryID"]:
                    continue
                csv_row[key] = structured.get(key, "Not specified")

            # Duplicate detection
            df_existing = read_all_entries()
            duplicates = pd.DataFrame()
            if show_duplicates_setting:
                duplicates = detect_duplicate(df_existing, csv_row, days_window)

            if not duplicates.empty:
                st.warning("⚠️ Probable duplicate(s) detected based on phone or email+role within the recent window.")
                st.dataframe(duplicates[HEADERS].fillna(""), use_container_width=True)
                col_yes, col_no = st.columns(2)
                with col_yes:
                    append_anyway = st.button("Append Anyway")
                with col_no:
                    skip_append = st.button("Skip Append (Cancel)")
                # Wait for user action
                if append_anyway:
                    append_row_to_csv(csv_row)
                    st.success("Appended entry to CSV.")
                    # Offer downloads
                    if csv_row.get("interview_scheduled_date") not in ["Not specified", "", None]:
                        ics = create_ics_file(csv_row)
                        if ics:
                            st.download_button(
                                label="📅 Download Calendar Event (.ics)",
                                data=ics,
                                file_name=f"interview_{csv_row.get('client_company','appointment')}.ics",
                                mime="text/calendar"
                            )
                    # Download single-row CSV
                    s = io.StringIO()
                    writer = csv.DictWriter(s, fieldnames=HEADERS)
                    writer.writeheader()
                    writer.writerow(csv_row)
                    st.download_button("📄 Download this entry (.csv)", data=s.getvalue(), file_name=f"job_entry_{entry_id}.csv", mime="text/csv")
                elif skip_append:
                    st.info("Entry not appended.")
                else:
                    st.info("Choose whether to append or skip the detected duplicate.")
            else:
                # No duplicates: append directly
                append_row_to_csv(csv_row)
                st.success("Entry appended to CSV.")

                # Offer ICS if date exists
                if csv_row.get("interview_scheduled_date") not in ["Not specified", "", None]:
                    ics = create_ics_file(csv_row)
                    if ics:
                        st.download_button(
                            label="📅 Download Calendar Event (.ics)",
                            data=ics,
                            file_name=f"interview_{csv_row.get('client_company','appointment')}.ics",
                            mime="text/calendar"
                        )

                # Download single-row CSV
                s = io.StringIO()
                writer = csv.DictWriter(s, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerow(csv_row)
                st.download_button("📄 Download this entry (.csv)", data=s.getvalue(), file_name=f"job_entry_{entry_id}.csv", mime="text/csv")

# --- Footer / Help ---
st.markdown("---")
with st.expander("Tips & Notes"):
    st.markdown("""
    - Each submission creates a new row in `job_contacts.csv` (stored next to the app).  
    - If you're deploying for multiple users, consider using Google Sheets, Airtable or a DB instead of a local CSV.  
    - Duplicate detection is heuristic-based (phone OR email+role within recent days). Tune `days_window` as needed.  
    - The AI is asked to return strict JSON; if parsing fails, check raw AI output for formatting issues.
    """)
