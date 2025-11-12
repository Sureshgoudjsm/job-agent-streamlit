

# webapp.py (Version 4 - with Dual Inputs)

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
You are a data extraction specialist. Your task is to analyze the following text from a recruiter and extract the specified pieces of information. The text may contain notes from a phone call and details from an email or job description.

**CRITICAL INSTRUCTION:** You MUST return the output as a single, valid JSON object. Do not add any explanatory text, markdown formatting, or code fences like ```json. Your entire response should be only the JSON object itself.

**JSON Keys to use:**
- "recruiter_name"
- "recruiter_company"
- "hiring_company"
- "job_title"
- "required_skills"
- "salary_range"
- "employment_type"
- "interview_mode"

If a piece of information is not available, the value for that key should be "Not specified".

**Input Text:**
---
{text_input}
---

**JSON Output:**
"""

def process_recruiter_text(text_to_process: str) -> dict:
    """
    Sends text to the Gemini model, expects a JSON response, and parses it into a Python dictionary.
    Returns a dictionary with the extracted data.
    """
    model=genai.GenerativeModel('gemini-2.5-flash')
    #model = genai.GenerativeModel('gemini-pro')
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

# --- 5. Building the Streamlit Web Interface (MODIFIED SECTION) ---
#st.title("🤖 AI Job Agent")
st.title("Roopa 👄")
st.write("Provide the key details from your conversation and paste any written info (like emails or JDs) to extract a summary.")

# --- NEW: Input Field 1 for Call Details ---
#st.subheader("1. On-Call Communication Summary")
st.subheader("Snanam ki vastava")

call_details = st.text_input(
    "Summarize your call with the recruiter in one or two lines.",
    placeholder="e.g., Spoke with John from Tech Recruiters about a Python role, salary is around 150k."
)

# --- NEW: Input Field 2 for Written Details ---
st.subheader("2. Paste Email, Job Description, or Other Info")
recruiter_text = st.text_area(
    "Paste the full text from emails, job descriptions, etc., here.", 
    height=250
)

# Create a button that the user will click to start the process
if st.button("Extract Details"):
    # --- NEW: Combine both inputs before sending to the AI ---
    combined_text = f"Call Summary: {call_details}\n\nDetailed Info:\n{recruiter_text}"
    
    # Check if the user has entered any text in either box
    if call_details.strip() or recruiter_text.strip():
        with st.spinner("🧠 The AI is analyzing the text..."):
            # Send the COMBINED text to the processing function
            structured_data_dict = process_recruiter_text(combined_text)
            
            st.subheader("Extracted Information")
            
            if "error" in structured_data_dict:
                st.error(structured_data_dict["error"])
            else:
                st.json(structured_data_dict)
                
                st.divider()
                
                output = io.StringIO()
                headers = structured_data_dict.keys()
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
        # If both text boxes are empty, show a warning
        st.warning("Please provide some information in at least one of the input boxes.")



