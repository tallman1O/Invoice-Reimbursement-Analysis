import os
import zipfile
import shutil
import json
import tempfile
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import PyPDF2  # For PDF text extraction
import google.generativeai as genai  # For Google Gemini LLM
from dotenv import load_dotenv  # Import load_dotenv
import uvicorn  # Import uvicorn to allow running as a script

from pydantic import BaseModel, Field
from enum import Enum

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# Retrieve API key from environment variables
# For Canvas environment, API key is automatically provided if left as empty string
API_KEY = os.getenv("GEMINI_API_KEY", "")  # Get API key from .env or default to empty string for Canvas
genai.configure(api_key=API_KEY)

# Choose the Gemini model
# Gemini 1.5 Flash is generally faster and more cost-effective for text analysis.
# If more complex reasoning or larger context windows are needed, consider 'gemini-1.5-pro-latest'.
GEMINI_MODEL = "gemini-1.5-flash"

app = FastAPI(
    title="Invoice Reimbursement Analysis API",
    description="Automates checking employee expense invoices against HR policy using LLM.",
    version="1.0.0"
)

# --- CORS Middleware ---
# This is crucial to allow the Streamlit frontend (running on a different port)
# to make requests to this FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development. In production, specify your Streamlit app's URL.
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Optimized System Prompt for LLM ---
# This prompt guides the LLM to act as an HR policy analyst and produce structured JSON output.
SYSTEM_PROMPT = """
You are an expert HR reimbursement policy analyst. Your task is to meticulously evaluate employee expense invoices against the provided company's HR Reimbursement Policy.

**Policy and Invoice Data:**
- The complete HR Reimbursement Policy will be provided as context.
- Each invoice's details (date, amount, purpose, items, taxes) will be provided for analysis.

**Analysis Process:**
1.  **Understand Policy:** Thoroughly analyze the HR Reimbursement Policy to identify all reimbursable categories, limits, restrictions, and conditions.
2.  **Extract Invoice Details:** Accurately extract all relevant details from the invoice, including the total amount, itemized expenses, date, and purpose.
3.  **Categorize and Apply Policy:** Determine the appropriate expense category for the invoice based on the policy. Apply the specific policy limits and restrictions for that category.
4.  **Calculate Reimbursement:** Calculate the exact reimbursable amount based on the policy rules.
5.  **Determine Status:** Assign one of the following statuses:
    * **Fully Reimbursed:** The entire invoice amount is eligible and within policy limits.
    * **Partially Reimbursed:** Only a portion of the invoice amount is eligible due to policy limits or specific non-reimbursable items.
    * **Declined:** The invoice is not reimbursable at all due to policy violations or explicit non-reimbursable clauses.

**Output Format (Strict JSON):**
For each invoice, provide a JSON object with the following structure. Ensure all amounts are integers.

```json
{
  "Invoice identifier": "filename.pdf",
  "Reimbursement Status": "Fully Reimbursed" | "Partially Reimbursed" | "Declined",
  "Reimbursable Amount": <integer_value>,
  "Reason": "A concise explanation derived directly from the policy. For 'Fully Reimbursed', state which policy clause supports it. For 'Partially Reimbursed' or 'Declined', explain the specific policy violation or limitation."
}
```

**Crucial Rules:**
-   **Strictly adhere to the provided HR Reimbursement Policy.** Do NOT introduce external rules, assumptions, or common knowledge about HR policies.
-   All `Reimbursable Amount` values MUST be integers.
-   Provide a `Reason` for ALL reimbursement statuses.
-   If an invoice is "Partially Reimbursed", explicitly state the policy limit or specific items that were not reimbursable.
-   If an invoice is "Declined", explicitly state the policy restriction or clause that makes it non-reimbursable.
-   If an invoice is "Fully Reimbursed", explicitly state the policy clause that supports its full reimbursement.
"""


# --- Helper Functions ---

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extracts text content from a PDF file.
    Args:
        pdf_path: The path to the PDF file.
    Returns:
        The extracted text content as a string.
    Raises:
        Exception: If PDF cannot be read or text extraction fails.
    """
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                text += reader.pages[page_num].extract_text() or ""
        return text
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF {pdf_path}: {e}")


async def analyze_invoice_with_llm(policy_text: str, invoice_filename: str, invoice_text: str) -> Dict[str, Any]:
    """
    Analyzes a single invoice against the policy using the LLM.
    Args:
        policy_text: The extracted text of the HR reimbursement policy.
        invoice_filename: The filename of the current invoice.
        invoice_text: The extracted text of the current invoice.
    Returns:
        A dictionary containing the LLM's analysis for the invoice.
    Raises:
        HTTPException: If LLM call fails or returns malformed JSON.
    """
    model = genai.GenerativeModel(GEMINI_MODEL)

    user_prompt = f"""
HR Reimbursement Policy:
```
{policy_text}
```

Invoice to Analyze (Filename: {invoice_filename}):
```
{invoice_text}
```

Please analyze this invoice strictly according to the HR Reimbursement Policy provided above and return the analysis in the specified JSON format.
"""
    try:
        # Make the LLM call with the optimized system prompt and user prompt
        response = await model.generate_content_async(
            contents=[
                {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{
                                                "text": "Understood. I will analyze the invoices based on the provided policy and return the results in the specified JSON format."}]},
                {"role": "user", "parts": [{"text": user_prompt}]}
            ],
            generation_config={"response_mime_type": "application/json"}  # Request JSON output
        )

        # Access the text part of the response, which should be JSON string
        raw_json_string = response.candidates[0].content.parts[0].text

        # Parse the JSON string
        analysis_result = json.loads(raw_json_string)

        # Add the invoice identifier from the filename if not already present or for consistency
        if "Invoice identifier" not in analysis_result:
            analysis_result["Invoice identifier"] = invoice_filename

        return analysis_result
    except json.JSONDecodeError as e:
        print(f"LLM returned non-JSON or malformed JSON for {invoice_filename}: {raw_json_string}. Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM returned malformed JSON for invoice {invoice_filename}. Please try again or check prompt."
        )
    except Exception as e:
        print(f"Error during LLM analysis for {invoice_filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze invoice {invoice_filename} with LLM: {e}"
        )


class ReimbursementStatus(str, Enum):
    fully = "Fully Reimbursed"
    partially = "Partially Reimbursed"
    declined = "Declined"

class InvoiceAnalysis(BaseModel):
    invoice_identifier: str = Field(..., alias="Invoice identifier", description="Filename of the invoice")
    reimbursement_status: ReimbursementStatus = Field(..., alias="Reimbursement Status", description="Outcome of reimbursement analysis")
    reimbursable_amount: int = Field(..., alias="Reimbursable Amount", description="Amount eligible for reimbursement")
    reason: str = Field(..., alias="Reason", description="Explanation derived from HR policy")

    class Config:
        allow_population_by_field_name = True  # This helps FastAPI correctly use aliases
        schema_extra = {
            "example": {
                "Invoice identifier": "invoice123.pdf",
                "Reimbursement Status": "Partially Reimbursed",
                "Reimbursable Amount": 150,
                "Reason": "Meal limit exceeded. Only $150 of the $250 was eligible under policy clause 3.2."
            }
        }

class InvoiceAnalysisResponse(BaseModel):
    overall_status: str
    invoice_analyses: List[InvoiceAnalysis]

# --- FastAPI Endpoint ---

@app.post("/analyze_invoices/", response_model=InvoiceAnalysisResponse)
async def analyze_invoices(
        policy_file: UploadFile = File(..., description="PDF file containing the HR Reimbursement Policy."),
        invoice_zip: UploadFile = File(..., description="ZIP file containing one or more employee invoice PDF files.")
):

    """
    Analyzes employee expense invoices against a company's HR reimbursement policy.

    Args:
        policy_file (UploadFile): The HR Reimbursement Policy as a PDF file.
        invoice_zip (UploadFile): A ZIP file containing employee invoice PDF files.

    Returns:
        JSONResponse: A JSON object detailing the analysis for each invoice,
                      including an overall status for the batch.
    """
    temp_dir = None
    try:
        # 1. Create a temporary directory for file storage
        temp_dir = tempfile.mkdtemp()
        policy_path = os.path.join(temp_dir, policy_file.filename)
        invoice_zip_path = os.path.join(temp_dir, invoice_zip.filename)
        extracted_invoices_dir = os.path.join(temp_dir, "invoices")
        os.makedirs(extracted_invoices_dir, exist_ok=True)

        # 2. Save uploaded files
        with open(policy_path, "wb") as buffer:
            shutil.copyfileobj(policy_file.file, buffer)
        with open(invoice_zip_path, "wb") as buffer:
            shutil.copyfileobj(invoice_zip.file, buffer)

        # 3. Extract HR Policy text
        if not policy_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="HR Policy file must be a PDF.")
        policy_text = extract_text_from_pdf(policy_path)
        if not policy_text.strip():
            raise HTTPException(status_code=400,
                                detail="Could not extract text from HR Policy PDF. It might be empty or malformed.")

        # 4. Extract invoices from ZIP
        invoice_files = []
        with zipfile.ZipFile(invoice_zip_path, 'r') as zip_ref:
            for member in zip_ref.namelist():
                # Only process PDF files within the zip
                if member.lower().endswith(".pdf") and not member.startswith(
                        '__MACOSX/'):  # Ignore macOS specific files
                    member_path = zip_ref.extract(member, extracted_invoices_dir)
                    invoice_files.append(member_path)

        if not invoice_files:
            raise HTTPException(status_code=400, detail="No PDF invoice files found in the provided ZIP archive.")

        # 5. Analyze each invoice using LLM
        analysis_results = []
        fully_reimbursed_count = 0
        partially_reimbursed_count = 0
        declined_count = 0

        for invoice_path in invoice_files:
            invoice_filename = os.path.basename(invoice_path)
            try:
                invoice_text = extract_text_from_pdf(invoice_path)
                if not invoice_text.strip():
                    print(f"Warning: Could not extract text from invoice {invoice_filename}. Skipping analysis.")
                    analysis_result = {
                        "invoice_identifier": invoice_filename,
                        "reimbursement_status": "Declined",
                        "reimbursable_amount": 0,
                        "reason": "Could not extract readable text from this invoice PDF."
                    }
                    declined_count += 1
                    analysis_results.append(analysis_result)
                    continue  # Skip to next invoice

                # Call LLM for analysis
                invoice_analysis = await analyze_invoice_with_llm(
                    policy_text=policy_text,
                    invoice_filename=invoice_filename,
                    invoice_text=invoice_text
                )
                analysis_results.append(invoice_analysis)

                # Update counts for overall status
                status = invoice_analysis.get("Reimbursement Status")
                if status == "Fully Reimbursed":
                    fully_reimbursed_count += 1
                elif status == "Partially Reimbursed":
                    partially_reimbursed_count += 1
                elif status == "Declined":
                    declined_count += 1

            except Exception as e:
                print(f"Error processing individual invoice {invoice_filename}: {e}")
                analysis_result = {
                    "Invoice identifier": invoice_filename,
                    "Reimbursement Status": "Declined",
                    "Reimbursable Amount": 0,
                    "Reason": f"Processing error: {str(e)}"
                }
                declined_count += 1  # Count as declined if processing failed
                analysis_results.append(analysis_result)

        # Determine overall status
        overall_status = "No Invoices Processed"
        if len(analysis_results) > 0:
            if fully_reimbursed_count == len(analysis_results):
                overall_status = "All Fully Reimbursed"
            elif declined_count == len(analysis_results):
                overall_status = "All Declined"
            else:
                overall_status = "Mixed Status"  # Any combination of statuses

        return JSONResponse(content={
            "overall_status": overall_status,
            "invoice_analyses": analysis_results
        })

    except HTTPException as e:
        # Re-raise FastAPI HTTP exceptions directly
        raise e
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unhandled error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
    finally:
        # 6. Clean up temporary files
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"Cleaned up temporary directory: {temp_dir}")


# This block allows you to run the FastAPI app directly using 'python main.py'
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
