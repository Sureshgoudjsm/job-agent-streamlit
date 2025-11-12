# webapp.py

# --- 1. Import necessary libraries ---
import os
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st  # Import Streamlit

# --- 2. Configuration and Model Setup ---

# Load environment variables from the .env file
load_dotenv()

# Configure the Google AI client
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    # Display a clear error in the web app if the key is missing
    st.error("CRITICAL ERROR: GOOGLE_API_KEY not found. Please ensure your .env file is correctly set up.")
    st.stop() # Stop the app from running further

# The prompt for data extraction (exactly the same as before)
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

# --- 3. The Core Logic Function ---
# This function is almost identical to your previous one.
def process_recruiter_text(text_to_process: str) -> str:
    """
    Sends the text to the Gemini model and returns the structured output.
    """
    # Use the same reliable model
    #model = genai.GenerativeModel('gemini-1.5-flash-latest')
    #model = genai.GenerativeModel('gemini-pro')
    model=genai.GenerativeModel('gemini-2.5-flash')

    prompt_with_input = EXTRACTION_PROMPT.format(text_input=text_to_process)
    
    try:
        response = model.generate_content(prompt_with_input)
        return response.text
    except Exception as e:
        # Return a user-friendly error message
        return f"An error occurred while contacting the AI service: {e}"

# --- 4. Building the Streamlit Web Interface ---

# Set the title of the web page
st.title("🤖 AI Job Agent Jagan Usain Please try this")
st.write("Paste the text from a recruiter's email or your call notes below to extract key details.")

# Create a text area for user input
# The `height` parameter makes the box taller, which is nice for long emails.
# The `placeholder` gives the user a hint.
recruiter_text = st.text_area(
    "Recruiter Text Input", 
    height=300, 
    placeholder="Example: Hi, my name is Jane from Tech Recruiters..."
)

# Create a button that the user will click to start the process
if st.button("Extract Details"):
    # Check if the user has entered any text
    if recruiter_text.strip():
        # If they have, show a spinner while processing
        with st.spinner("🧠 The AI JobAgent is analyzing the text..."):
            # Call our existing function to do the work
            structured_data = process_recruiter_text(recruiter_text)
            
            # Display the results
            st.subheader("Extracted Information")
            st.markdown(structured_data) # Use st.markdown to render the formatted text nicely
            
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
        # If the text box is empty, show a warning
        st.warning("Please paste some text into the input box first.")


