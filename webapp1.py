# webapp.py (Version 2 - with Download Button)

# --- 1. Import necessary libraries ---
'''
import os
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

# --- 2. Configuration and Model Setup ---
load_dotenv()
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

# --- 3. The AI Prompt ---
EXTRACTION_PROMPT = """
You are a data extraction specialist. Your task is to analyze the following text from a recruiter and pull out the specified pieces of information.

**Information to Extract:**
1.  **Recruiter Name:** The name of the person who sent the message.
2.  **Recruiter Company:** The company the recruiter works for.
3.  **Hiring Company:** The company that has the job opening.
4.  **Job Title:** The title of the position.
5.  **Required Skills:** A list of key skills, technologies, or qualifications mentioned.
6.  **Salary Range:** The offered salary for the role.
7.  **Employment Type:** Whether the job is permanent, contract, full-time, etc.
8.  **Interview Mode:** How the interviews will be conducted (e.g., Online, Offline).

If any piece of information is not available in the text, explicitly state "Not specified". Return ONLY the structured output as clean Markdown.

**Input Text:**
---
{text_input}
---

**Structured Output:**
"""

# --- 4. The Core Logic Function ---
def process_recruiter_text(text_to_process: str) -> str:
    """
    Sends the text to the Gemini model and returns the structured output.
    """
    #model = genai.GenerativeModel('gemini-pro')
    model=genai.GenerativeModel('gemini-2.5-flash')
  
    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    try:
        response = model.generate_content(prompt_with_input)
        return response.text
    except Exception as e:
        return f"An error occurred while contacting the AI service: {e}"

# --- 5. Building the Streamlit Web Interface ---
st.title("Hi Roopa Ela unnavv, EM chestunnavv, call mee snanam ki vastava")
st.write("Paste the text from a recruiter's email or your call notes below to extract key details.")

recruiter_text = st.text_area(
    "Recruiter Text Input", 
    height=200, 
    placeholder="Example: Hi, my name is Jane from Tech Recruiters..."
)

if st.button("Extract Details"):
    if recruiter_text.strip():
        with st.spinner("🧠 The AI is analyzing the text..."):
            structured_data = process_recruiter_text(recruiter_text)
            
            st.subheader("Extracted Information")
            st.markdown(structured_data)
            
            # --- NEW CODE ADDED HERE ---
            # Add a divider for visual separation
            st.divider() 
            # Add the download button
            st.download_button(
                label="📄 Download as .txt",
                data=structured_data,
                file_name="job_details.txt",
                mime="text/plain"
            )
            # --- END OF NEW CODE ---
            
    else:
        st.warning("Please paste some text into the input box first.") '''

# webapp.py (Version 3 - with CSV Download)

# --- 1. Import necessary libraries ---
'''
import os
import json  # NEW: Import the JSON library to parse the AI's output
import csv   # NEW: Import the CSV library to create the spreadsheet
import io    # NEW: Import the io library to handle the CSV data in memory
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st

# --- 2. Configuration and Model Setup ---
load_dotenv()
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop()

# --- 3. The AI Prompt (MODIFIED FOR JSON OUTPUT) ---
EXTRACTION_PROMPT = """
You are a data extraction specialist. Your task is to analyze the following text from a recruiter and extract the specified pieces of information.

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

# --- 4. The Core Logic Function (MODIFIED TO PARSE JSON) ---
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
        # The AI's response is a string that looks like JSON.
        # We need to parse it into a real Python dictionary.
        # We also clean up potential markdown fences just in case the AI adds them.
        clean_response = response.text.strip().replace("```json", "").replace("```", "")
        parsed_json = json.loads(clean_response)
        return parsed_json
    except json.JSONDecodeError:
        # Handle cases where the AI doesn't return valid JSON
        return {"error": "The AI returned an invalid format. Please try again."}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

# --- 5. Building the Streamlit Web Interface (MODIFIED FOR CSV) ---
st.title("🤖 AI Job Agent")
st.write("Paste the text from a recruiter's email or your call notes below to extract key details.")

recruiter_text = st.text_area(
    "Recruiter Text Input", 
    height=300, 
    placeholder="Example: Hi, my name is Jane from Tech Recruiters..."
)

if st.button("Extract Details"):
    if recruiter_text.strip():
        with st.spinner("🧠 The AI is analyzing the text..."):
            # This now returns a dictionary, not a string
            structured_data_dict = process_recruiter_text(recruiter_text)
            
            st.subheader("Extracted Information")
            
            # Check if there was an error during processing
            if "error" in structured_data_dict:
                st.error(structured_data_dict["error"])
            else:
                # Display the data on the page using st.json or as a table
                st.json(structured_data_dict)
                
                st.divider()
                
                # --- NEW: CSV CREATION LOGIC ---
                # Create a file-like object in memory
                output = io.StringIO()
                # Define the column headers from the dictionary keys
                headers = structured_data_dict.keys()
                writer = csv.DictWriter(output, fieldnames=headers)
                
                # Write the header row
                writer.writeheader()
                # Write the data row
                writer.writerow(structured_data_dict)
                
                # Get the string value from the in-memory file
                csv_data = output.getvalue()
                # --- END OF NEW LOGIC ---

                # MODIFIED: The download button now uses the generated CSV data
                st.download_button(
                    label="📄 Download as .csv",
                    data=csv_data,
                    file_name="job_details.csv",
                    mime="text/csv"
                )
    else:
        st.warning("Please paste some text into the input box first.") '''

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
st.title("🤖 AI Job Agent")
st.write("Provide the key details from your conversation and paste any written info (like emails or JDs) to extract a summary.")

# --- NEW: Input Field 1 for Call Details ---
st.subheader("1. On-Call Communication Summary")
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



