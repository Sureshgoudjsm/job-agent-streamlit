import os
import json
import csv
import io
import pandas as pd # <-- NEW IMPORT for cleaner display
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

# --- 2. The AI Prompt (Unchanged) ---
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

# --- 3. The Core Logic Function (Unchanged) ---
def process_recruiter_text(text_to_process: str) -> dict:
    """
    Sends text to the Gemini model, expects a JSON response, and parses it into a Python dictionary.
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        # Safely remove potential markdown and strip whitespace
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        parsed_json = json.loads(clean_response)
        return parsed_json
    except json.JSONDecodeError:
        return {"error": f"The AI returned an invalid JSON format. Raw output: {clean_response}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

# --- 4. Building the Streamlit Web Interface (IMPROVED UX) ---
st.title("🤖 AI Job Agent")
st.write("Paste your recruiter communication (emails, JDs, call notes) below to instantly extract structured tracking data.")

# Add a help expander for transparency
with st.expander("❓ How This Works & Expected Fields"):
    st.markdown("""
        The AI analyzes the text you paste and uses a precise template to pull out **18 key data points** for your job tracking spreadsheet.
        
        **Examples of fields extracted:** `hr_name`, `role_position`, `client_company`, `location`, `ctc_offered_expected`, `status`, etc.
        
        **Tip:** For the best results, include **dates**, **salaries**, and the **company name** in your input text.
    """)

# Use st.form to group all inputs and control execution
with st.form(key='data_extraction_form'):
    
    st.subheader("1. Call/Chat Summary (Optional, but helpful)")
    call_details = st.text_input(
        "Summarize your conversation with the recruiter in one or two lines:",
        placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k.",
        key='call_details'
    )

    st.subheader("2. Full Text Input (Required)")
    recruiter_text = st.text_area(
        "Paste the **full text** from the Job Description, email, or other source here.", 
        height=350,
        placeholder="E.g., Dear [Name], We are looking for a Senior Full Stack Developer (React/Node.js) for our client, Acme Corp. in Bangalore (Hybrid). The interview is scheduled for 2025-12-01. Salary range is 18-22 LPA...",
        key='recruiter_text'
    )
    
    # The submit button
    submitted = st.form_submit_button("✨ Extract and Prepare CSV")

if submitted:
    
    combined_text = f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
    
    if call_details.strip() or recruiter_text.strip():
        with st.spinner("🧠 The AI is analyzing the text..."):
            structured_data_dict = process_recruiter_text(combined_text)
            
            if "error" in structured_data_dict:
                st.error(structured_data_dict["error"])
            else:
                st.success("Extraction complete! Review the results and download your CSV below.")
                st.subheader("✅ Extracted Information Review")
                
                # --- NEW: Convert to DataFrame for a clean table view ---
                df_display = pd.DataFrame([structured_data_dict]).T
                df_display.columns = ["Extracted Value"]
                st.dataframe(df_display, use_container_width=True) # Display the table

                st.divider()
                
                # --- CSV CREATION LOGIC ---
                output = io.StringIO()
                
                # Define the column headers in the exact order for the CSV.
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
