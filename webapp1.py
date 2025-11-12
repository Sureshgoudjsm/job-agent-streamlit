# webapp.py (Version 5 - Comprehensive Tracking)

# --- 1, 2 are unchanged ---
import os
import json
import csv
import io
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

load_dotenv()
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

# --- 3. The AI Prompt (HEAVILY MODIFIED with your new fields) ---
EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided text (which may include call notes and email/JD details) and extract the following specific pieces of information.

**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```json. Your entire response should be only the JSON object itself. If a piece of information is not available, the value for that key MUST be "Not specified".

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

**Input Text:**
---
{text_input}
---

**JSON Output:**
"""

# --- 4. The Core Logic Function (Unchanged, but using your preferred model) ---
def process_recruiter_text(text_to_process: str) -> dict:
    """
    Sends text to the Gemini model, expects a JSON response, and parses it into a Python dictionary.
    """
    # Using your preferred model, as requested.
    #model = genai.GenerativeModel('gemini-1.5-flash')
    model=genai.GenerativeModel('gemini-2.5-flash')
    
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        parsed_json = json.loads(clean_response)
        return parsed_json
    except json.JSONDecodeError:
        return {"error": "The AI returned an invalid format. Please try again."}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

# --- 5. Building the Streamlit Web Interface (MODIFIED CSV HEADERS) ---
st.title("🤖 AI Job Agent")
st.write("Provide the key details from your conversation and paste any written info (like emails or JDs) to extract a summary.")

st.subheader("1. On-Call Communication Summary")
call_details = st.text_input(
    "Summarize your call with the recruiter in one or two lines.",
    placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k."
)

st.subheader("2. Paste Email, Job Description, or Other Info")
recruiter_text = st.text_area(
    "Paste the full text from emails, job descriptions, etc., here.", 
    height=250
)

if st.button("Extract Details"):
    combined_text = f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
    
    if call_details.strip() or recruiter_text.strip():
        with st.spinner("🧠 The AI is analyzing the text..."):
            structured_data_dict = process_recruiter_text(combined_text)
            
            st.subheader("Extracted Information")
            
            if "error" in structured_data_dict:
                st.error(structured_data_dict["error"])
            else:
                st.json(structured_data_dict)
                st.divider()
                
                # --- NEW: CSV CREATION LOGIC with your new headers ---
                output = io.StringIO()
                
                # Define the column headers in the exact order you want them in the CSV.
                # This ensures the spreadsheet is always perfectly organized.
                headers = [
                    "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
                    "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
                    "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
                    "ctc_offered_expected", "status", "next_follow_up_date", "review_notes"
                ]
                
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerow(structured_data_dict)
                csv_data = output.getvalue()

                st.download_button(
                    label="📄 Download as .csv",
                    data=csv_data,
                    file_name="job_details.csv",
                    mime="text/csv"
                )
    else:
        st.warning("Please provide some information in at least one of the input boxes.")
        

'''
# webapp.py (Version 6 - with Colored Headers)

# --- 1, 2, 3, and 4 are unchanged ---
import os
import json
import csv
import io
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

load_dotenv()
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

EXTRACTION_PROMPT = """
You are an expert data extraction assistant for job seekers. Your task is to analyze the provided text (which may include call notes and email/JD details) and extract the following specific pieces of information.

**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```json. Your entire response should be only the JSON object itself. If a piece of information is not available, the value for that key MUST be "Not specified".

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

**Input Text:**
---
{text_input}
---

**JSON Output:**
"""

def process_recruiter_text(text_to_process: str) -> dict:
    """
    Sends text to the Gemini model, expects a JSON response, and parses it into a Python dictionary.
    """
    #model = genai.GenerativeModel('gemini-1.5-flash')
    model=genai.GenerativeModel('gemini-2.5-flash')
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        parsed_json = json.loads(clean_response)
        return parsed_json
    except json.JSONDecodeError:
        return {"error": "The AI returned an invalid format. Please try again."}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

# --- 5. Building the Streamlit Web Interface (MODIFIED HEADERS) ---

# --- NEW: Custom HTML for the yellow background title ---
st.markdown("""
<div style="background-color:#f2d44b; padding:10px; border-radius:5px;">
<h1 style="color:black; text-align:center;">🤖 AI Job Agent</h1>
</div>
""", unsafe_allow_html=True)

st.write("Provide the key details from your conversation and paste any written info (like emails or JDs) to extract a summary.")

# --- NEW: Custom HTML for the yellow background subheaders ---
st.markdown("""
<div style="background-color:#f2d44b; padding:10px; border-radius:5px;">
<h3 style="color:black;">1. On-Call Communication Summary</h3>
</div>
""", unsafe_allow_html=True)

call_details = st.text_input(
    "Summarize your call with the recruiter in one or two lines.",
    placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k.",
    label_visibility="collapsed" # Hides the default label to avoid repetition
)

st.markdown("""
<div style="background-color:#f2d44b; padding:10px; border-radius:5px;">
<h3 style="color:black;">2. Paste Email, Job Description, or Other Info</h3>
</div>
""", unsafe_allow_html=True)

recruiter_text = st.text_area(
    "Paste the full text from emails, job descriptions, etc., here.", 
    height=250,
    label_visibility="collapsed" # Hides the default label
)

# The rest of the logic remains the same
if st.button("Extract Details"):
    combined_text = f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
    
    if call_details.strip() or recruiter_text.strip():
        with st.spinner("🧠 The AI is analyzing the text..."):
            structured_data_dict = process_recruiter_text(combined_text)
            
            # --- NEW: Custom HTML for the results header ---
            st.markdown("""
            <div style="background-color:#f2d44b; padding:10px; border-radius:5px;">
            <h3 style="color:black;">Extracted Information</h3>
            </div>
            """, unsafe_allow_html=True)
            
            if "error" in structured_data_dict:
                st.error(structured_data_dict["error"])
            else:
                st.json(structured_data_dict)
                st.divider()
                
                output = io.StringIO()
                headers = [
                    "date_contacted", "hr_name", "phone_number", "email_id", "role_position",
                    "recruiter_company", "client_company", "location", "job_type", "mode_of_contact",
                    "interview_mode", "interview_scheduled_date", "round_1_details", "round_2_details",
                    "ctc_offered_expected", "status", "next_follow_up_date", "review_notes"
                ]
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerow(structured_data_dict)
                csv_data = output.getvalue()

                st.download_button(
                    label="📄 Download as .csv",
                    data=csv_data,
                    file_name="job_details.csv",
                    mime="text/csv"
                )
    else:
        st.warning("Please provide some information in at least one of the input boxes.")
'''
