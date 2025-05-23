# Invoice Reimbursement Analysis API

This project provides a FastAPI backend API and a Streamlit frontend UI to automate the process of checking employee expense invoices against a company's HR reimbursement policy using a Large Language Model (LLM).

---

## Table of Contents
1.  [Project Overview](#project-overview)
2.  [Features](#features)
3.  [Technologies Used](#technologies-used)
4.  [Usage](#usage)
5.  [API Endpoint Details](#api-endpoint-details)
6.  [LLM Strategy & Prompt Engineering](#llm-strategy--prompt-engineering)
7.  [Error Handling](#error-handling)

---

## 1. Project Overview

The core goal of this project is to streamline the expense reimbursement process by programmatically analyzing invoices against a given HR policy. Employees can submit a ZIP file containing multiple invoice PDFs, along with the company's HR policy PDF. The system then determines the reimbursement status (Fully Reimbursed, Partially Reimbursed, or Declined) and the reimbursable amount for each invoice, providing a detailed reason based on the policy.

## 2. Features

* **FastAPI Backend:** A robust and high-performance API built with FastAPI.
* **Streamlit Frontend:** An intuitive and user-friendly web interface for easy interaction.
* **PDF Content Extraction:** Extracts text from both policy and invoice PDF documents.
* **LLM-Powered Analysis:** Utilizes the Google Gemini 1.5 Flash model to interpret policies and invoices.
* **Structured Output:** Returns a clear JSON response with per-invoice analysis, including status, amount, and detailed reasons.
* **Overall Batch Status:** Provides a summary status for the entire batch of invoices processed.
* **Temporary File Management:** Securely handles and cleans up uploaded files.
* **CORS Enabled:** Configured to allow cross-origin requests from the Streamlit frontend.
* **API Documentation:** Automatic interactive API documentation via Swagger UI.

---

## 3. Technologies Used

* **Python 3.8+**
* **FastAPI:** Web framework for building the API.
* **Streamlit:** For creating the interactive web UI.
* **Uvicorn:** ASGI server to run the FastAPI application.
* **PyPDF2:** For extracting text from PDF files.
* **`python-dotenv`:** For managing environment variables (e.g., API keys).
* **Google Gemini API (`google-generativeai`):** The Large Language Model used for analysis.
* **Pydantic:** For data validation and serialization, used to define API response models.
* **`python-multipart`:** Required by FastAPI for handling file uploads.

---

## 4. Usage

1.  **Start both the FastAPI backend and the Streamlit frontend** as described in the "Setup and Installation" section.
2.  **Open the Streamlit application** in your browser (`http://localhost:8501`).
3.  **Upload the HR Reimbursement Policy PDF** using the first file uploader.
4.  **Upload a ZIP file containing your invoice PDFs** using the second file uploader.
5.  **Click the "Analyze Invoices" button.**
6.  The Streamlit app will display the analysis results, including the overall status and detailed reimbursement information for each invoice.

---

## 5. API Endpoint Details

The FastAPI backend exposes a single endpoint:

* **Endpoint:** `/analyze_invoices/`
* **Method:** `POST`
* **Description:** Analyzes employee expense invoices against a company's HR reimbursement policy using an LLM.
* **Inputs (Form Data):**
    * `policy_file`: `File` (PDF file) - The HR Reimbursement Policy.
    * `invoice_zip`: `File` (ZIP file) - A ZIP archive containing invoice PDFs.
* **Outputs (JSON):**
    The endpoint returns a JSON object conforming to the `InvoiceAnalysisResponse` Pydantic model:

    ```json
    {
      "overall_status": "string",
      "invoice_analyses": [
        {
          "Invoice identifier": "string",
          "Reimbursement Status": "Fully Reimbursed" | "Partially Reimbursed" | "Declined",
          "Reimbursable Amount": 0,
          "Reason": "string"
        }
      ]
    }
    ```
    A detailed schema is available in the Swagger UI (`/docs`).

---

## 6. LLM Strategy & Prompt Engineering

* **LLM Choice:** Google Gemini 1.5 Flash is used for its balance of performance, cost-effectiveness, and large context window.
* **Minimization Strategy:** To reduce LLM calls, the HR Reimbursement Policy is extracted and processed once. This extracted text is then passed as context to the LLM for each individual invoice analysis, avoiding redundant policy interpretation.
* **Optimized System Prompt:** The system prompt is carefully crafted to guide the LLM as an "expert HR reimbursement policy analyst." It emphasizes:
    * Strict adherence to the provided policy.
    * Clear, structured JSON output format.
    * Requirement for a "Reason" for *all* reimbursement statuses (Fully, Partially, Declined), citing specific policy clauses or violations.
    * Enforcement of integer amounts for reimbursement.

---

## 7. Error Handling

The application includes robust error handling for:
* Invalid file types (non-PDF policy, non-PDFs within ZIP).
* Empty ZIP files or inability to extract text from PDFs.
* LLM API errors (e.g., malformed JSON response from LLM, network issues).
* General internal server errors.

User-friendly error messages are displayed in the Streamlit UI, and detailed error logs are printed on the FastAPI backend console.