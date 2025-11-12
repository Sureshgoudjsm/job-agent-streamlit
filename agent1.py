# C:\TestAgent\multi_tool_agent\agent.py

# --- 1. Import necessary libraries ---
import os
import sys
from dotenv import load_dotenv
from google.genai import Client
# Import the necessary components from ADK
from google.adk.agents import LlmAgent
#from google.adk.agents.code import CodeTool
#from google.adk.tools import CodeTool
from google.adk.code_executors import BuiltInCodeExecutor # New import path

# --- 2. Configuration and Client Initialization ---

# Load environment variables (API Key etc.)
load_dotenv()

# The model to use. 'gemini-2.5-flash' is the stable, current model.
MODEL_ID = 'gemini-2.5-flash'

try:
    # Initialize the Client. It automatically picks up GOOGLE_API_KEY.
    client = Client()
    # Ensure the client is accessible later (though ADK often manages this)
    print(f"Gemini Client initialized successfully, using model: {MODEL_ID}")
except Exception as e:
    print(f"ERROR: Failed to initialize Gemini Client. Check GOOGLE_API_KEY: {e}")
    # We will let the ADK handle the failure, but this check is good.

# --- 3. Define a Sample Tool (Required for multi_tool_agent) ---
# Since you named your directory 'multi_tool_agent', the ADK expects a tool.
# This is a dummy tool to satisfy the ADK structure.

def current_date_time() -> str:
    """Returns the current date and time."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- 4. The Core Agent Definition (The FIX for 'No root_agent found') ---
# This LlmAgent incorporates your extraction prompt and defines the agent structure.

# The prompt for data extraction
EXTRACTION_INSTRUCTION = """
You are a data extraction specialist. Your task is to analyze the user's text from a recruiter and pull out the specified pieces of information.

**Information to Extract:**
1.  **Recruiter Name:** The name of the person who sent the message.
2.  **Recruiter Company:** The company the recruiter works for.
3.  **Hiring Company:** The company that has the job opening.
4.  **Job Title:** The title of the position.
5.  **Required Skills:** A list of key skills, technologies, or qualifications mentioned.
6.  **Salary Range:** The offered salary for the role.
7.  **Employment Type:** Whether the job is permanent, contract, full-time, etc.
8.  **Interview Mode:** How the interviews will be conducted (e.g., Online, Offline).

If any piece of information is not available in the text, explicitly state "Not specified". Return ONLY the structured output.
"""

# The ADK requires the main agent instance to be named 'root_agent'
# This is the variable the ADK CLI looks for.
# root_agent = LlmAgent(
#     name="RecruiterDataExtractor",
#     instruction=EXTRACTION_INSTRUCTION,
#     model=MODEL_ID,
#     # Define the tools this agent can use. 
#     # The CodeTool wraps your Python function.
#     tools=[
#         CodeTool.from_function(current_date_time)
#     ],
# )

# Define the BuiltInCodeExecutor instance
code_executor_instance = BuiltInCodeExecutor() 

root_agent = LlmAgent(
    name="RecruiterDataExtractor",
    instruction=EXTRACTION_INSTRUCTION,
    model=MODEL_ID,
    # The executor is assigned here, NOT in the 'tools' list
    code_executor=code_executor_instance,
    # Use an actual Function Tool if you still need one, or remove 'tools' entirely
    tools=[] 
)

# --- 5. Optional: Standalone Execution Block (For testing outside ADK) ---
# This section allows you to test the agent logic directly via your terminal 
# if you uncomment the code inside process_text.

def process_recruiter_text(text_to_process: str) -> str:
    """Sends the text to the Gemini model and returns the structured output."""
    
    # NOTE: Since the agent is defined as root_agent above, in a real ADK flow, 
    # the ADK runner handles the prompt and response. 
    
    # However, for simple standalone testing (without the ADK web server), 
    # you can use the direct API call method you used before:
    
    prompt_with_input = EXTRACTION_INSTRUCTION + f"\n\n**Input Text:**\n---\n{text_to_process}\n---\n\n**Structured Output:**"
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt_with_input
        )
        return response.text
    except Exception as e:
        return f"An error occurred while contacting the AI service: {e}"

if __name__ == "__main__":
    print("-" * 30)
    print("--- AI Job Agent (Standalone Test Mode) ---")
    print("This mode runs the core logic without the ADK web server.")
    print("Paste the recruiter's text below (Ctrl+D or Ctrl+Z to process):")
    print("-" * 30)

    try:
        user_input = sys.stdin.read()
    except Exception:
        user_input = ""

    if user_input.strip():
        print("\nProcessing your text...")
        structured_data = process_recruiter_text(user_input)
        
        print("\n" + "=" * 30)
        print("--- EXTRACTED INFORMATION ---")
        print("=" * 30)
        print(structured_data)
        print("=" * 30)
    else:
        print("No input received. Exiting.")