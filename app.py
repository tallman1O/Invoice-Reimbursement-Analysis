# ui/streamlit_app.py

import streamlit as st
import requests
import json
import io

# --- Configuration ---
# Ensure this URL matches where your FastAPI server is running
FASTAPI_ENDPOINT_URL = "http://127.0.0.1:8000/analyze_invoices"

st.set_page_config(
    page_title="Invoice Reimbursement Analyzer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Header Section ---
st.title("💰 Invoice Reimbursement Analysis App")
st.markdown("""
    Upload your HR Reimbursement Policy (PDF) and a ZIP file containing employee invoices (PDFs).
    The app will analyze each invoice against the policy using an AI model and provide a detailed reimbursement status.
""")

st.divider()

# --- File Upload Section ---
st.subheader("1. Upload Files")

col1, col2 = st.columns(2)

with col1:
    policy_file = st.file_uploader(
        "Upload HR Reimbursement Policy (PDF)",
        type=["pdf"],
        help="The company's official HR policy document in PDF format."
    )

with col2:
    invoice_zip = st.file_uploader(
        "Upload Employee Invoices (ZIP containing PDFs)",
        type=["zip"],
        accept_multiple_files=False, # Ensure only one zip file is uploaded
        help="A ZIP archive containing one or more employee expense invoices in PDF format."
    )

st.markdown("---")

# --- Analysis Trigger Button ---
st.subheader("2. Run Analysis")

if st.button("Analyze Invoices", use_container_width=True, type="primary"):
    if policy_file is None:
        st.error("Please upload the HR Reimbursement Policy PDF.")
    elif invoice_zip is None:
        st.error("Please upload the Employee Invoices ZIP file.")
    else:
        with st.spinner("Analyzing invoices... This may take a moment depending on the number of invoices and policy length."):
            try:
                # Prepare files for FastAPI multipart/form-data request
                files = {
                    "policy_file": (policy_file.name, policy_file.getvalue(), "application/pdf"),
                    "invoice_zip": (invoice_zip.name, invoice_zip.getvalue(), "application/zip")
                }

                # Make the POST request to the FastAPI endpoint
                response = requests.post(FASTAPI_ENDPOINT_URL, files=files)

                if response.status_code == 200:
                    result = response.json()
                    st.success("Analysis Complete!")

                    # --- Display Results ---
                    st.subheader("3. Analysis Results")

                    if "invoice_analyses" in result and result["invoice_analyses"]:
                        for invoice_data in result["invoice_analyses"]:
                            invoice_id = invoice_data.get("Invoice identifier", "N/A")
                            status = invoice_data.get("Reimbursement Status", "N/A")
                            reimbursable_amount = invoice_data.get("Reimbursable Amount", "N/A")
                            reason = invoice_data.get("Reason", "No reason provided.")

                            # Use st.expander for a collapsible view of each invoice's details
                            with st.expander(f"**Invoice: `{invoice_id}` - Status: `{status}`**"):
                                st.markdown(f"**Reimbursement Status:** <span style='font-size: 1.1em; color: {'green' if status == 'Fully Reimbursed' else ('orange' if status == 'Partially Reimbursed' else 'red')}; font-weight: bold;'>{status}</span>", unsafe_allow_html=True)
                                st.markdown(f"**Reimbursable Amount:** **${reimbursable_amount}**")
                                st.markdown(f"**Reason:** {reason}")
                                st.markdown("---") # Separator for clarity

                    else:
                        st.warning("No invoice analysis results returned from the API.")

                elif response.status_code == 400:
                    st.error(f"Input Error: {response.json().get('detail', 'Bad Request')}")
                else:
                    st.error(f"API Error: {response.status_code} - {response.text}")

            except requests.exceptions.ConnectionError:
                st.error(f"Could not connect to the FastAPI server at {FASTAPI_ENDPOINT_URL}. "
                         "Please ensure the backend API is running.")
            except json.JSONDecodeError:
                st.error("Received an invalid JSON response from the API. Please check the backend logs.")
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

st.markdown("---")
st.caption("Powered by FastAPI, Streamlit, and Google Gemini AI.")
st.markdown("For best results, ensure your PDFs are text-searchable, not just scanned images.")

