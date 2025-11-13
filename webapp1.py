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
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

# --- 2. The AI Prompt (FINAL MODIFIED) ---
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

# --- 3. The Core Logic Function (Unchanged) ---
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

# --- 4. iCalendar File Generation Function (Unchanged) ---
def create_ics_file(details: dict) -> str:
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

# --- 5. Building the Streamlit Web Interface (Modified for Expanded Expanders) ---
st.title("🤖 AI Job Agent")
st.write("Analyze job details and your own skills simultaneously to generate a match score and tracking data.")

# Help Section
with st.expander("❓ How This Works & Expected Fields", expanded=False):
    st.markdown("""
        The AI analyzes the Job Details and your skills to pull 22 key data points, including a **Match Score** and **Proactive Prep Hint**.

        **New Fields:** `match_score`, `skill_gap_analysis`, and `prep_hint`.

        **Tip:** For best results, put your resume/skills in the first section, and the full Job Description in the third section.
    """)

# Form with Expanders for Each Section
with st.form(key='data_extraction_form'):
    
    # 1. Applicant Skills (Expanded by default for immediate input)
    st.subheader("🧠 1. Applicant Skills (For Match Score)")
    with st.expander("Paste your key skills, technologies, and experience here.", expanded=True):
        applicant_skills = st.text_area(
            "Applicant Skills Input:",
            height=150,
            placeholder="e.g., Python (5 years), AWS (3 years, Certified), Terraform, Docker, SQL, Scrum Master Certification.",
            key='applicant_skills',
            label_visibility="collapsed" # Hide redundant label
        )

    # 2. Recruiter Call Summary (Expanded by default for immediate input)
    st.subheader("📞 2. Recruiter Call Summary")
    with st.expander("Summarize your conversation with the recruiter:", expanded=True):
        call_details = st.text_input(
            "Call Details Input:",
            placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k.",
            key='call_details',
            label_visibility="collapsed" # Hide redundant label
        )

    # 3. Full Job Description Text (Expanded by default for immediate input)
    st.subheader("📄 3. Full Job Description Text")
    with st.expander("Paste the full Job Description, email, or message here:", expanded=True):
        recruiter_text = st.text_area(
            "Recruiter Text Input:",
            height=350,
            placeholder="E.g., Dear [Name], We are looking for a Senior Full Stack Developer (React/Node.js) for our client, Acme Corp. in Bangalore (Hybrid)...",
            key='recruiter_text',
            label_visibility="collapsed" # Hide redundant label
        )

    st.markdown("---") # Separator before the submit button

    submitted = st.form_submit_button("✨ Extract, Score, and Prepare Files")

# --- 6. Processing Logic (Unchanged) ---
if submitted:
    # Combining inputs for the AI prompt
    combined_text = (
        f"--- APPLICANT SKILLS ---\n{applicant_skills}\n\n"
        f"--- JOB DETAILS ---\n"
        f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
    )

    if call_details.strip() or recruiter_text.strip() or applicant_skills.strip():
        with st.spinner("🧠 The AI is analyzing and scoring the fit..."):
            structured_data_dict = process_recruiter_text(combined_text)

            if "error" in structured_data_dict:
                st.error(structured_data_dict["error"])
            else:
                st.success("Extraction and scoring complete! Review results and download your files below.")
                st.subheader("✅ Extracted Information Review")

                # Display Results in a DataFrame
                df_display = pd.DataFrame([structured_data_dict]).T
                df_display.columns = ["Extracted Value"]
                st.dataframe(df_display, use_container_width=True)

                st.divider()

                # iCalendar Download Button
                if structured_data_dict.get("interview_scheduled_date") not in ["Not specified", None, ""]:
                    ics_data = create_ics_file(structured_data_dict)
                    if ics_data:
                        st.download_button(
                            label="📅 Download Calendar Event (.ics)",
                            data=ics_data,
                            file_name=f"interview_{structured_data_dict.get('client_company', 'details')}.ics",
                            mime="text/calendar"
                        )

                # CSV Download Button
                output = io.StringIO()
                headers = list(structured_data_dict.keys()) # Use extracted keys dynamically
                
                # Check if all required headers are present, if not, use the full list as fallback
                required_headers = [
                    "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
                    "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
                    "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
                    "ctc_offered_expected", "status", "next_follow_up_date", "review_notes",
                    "extracted_keywords", "match_score", "skill_gap_analysis", "prep_hint"
                ]
                # Ensure the CSV writer uses the full header list to avoid missing columns
                final_headers = required_headers

                writer = csv.DictWriter(output, fieldnames=final_headers, extrasaction='ignore')
                writer.writeheader()
                
                # Ensure all missing keys in the dictionary are filled with "" to prevent DictWriter errors
                row_to_write = {key: structured_data_dict.get(key, "") for key in final_headers}
                writer.writerow(row_to_write)
                
                csv_data = output.getvalue()

                st.download_button(
                    label="📄 Download Job Tracker (.csv)",
                    data=csv_data,
                    file_name="job_details.csv",
                    mime="text/csv"
                )
    else:
        st.warning("Please provide some information in at least one of the input sections.")
