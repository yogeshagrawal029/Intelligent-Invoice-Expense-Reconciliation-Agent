# Intelligent Invoice & Expense Reconciliation Agent

## Overview

The **Intelligent Invoice & Expense Reconciliation Agent** is a capstone project that automates invoice reconciliation using document parsing, OCR, rule-based matching, anomaly detection, human approval workflow, and **LangChain-powered AI review**.

The application performs three-way matching between:

```text
Purchase Order  ↔  Invoice  ↔  Bank Statement
```

It extracts invoice details from TXT, PDF, and image files, validates them against purchase orders and bank transactions, detects mismatches, duplicate payments, anomalies, and routes exceptions for human review. LangChain is used to generate AI-powered reconciliation explanations and professional vendor email drafts.

---

## Problem Statement

Manual invoice reconciliation is time-consuming, error-prone, and difficult to scale. Finance teams often need to manually verify invoices against purchase orders and bank payments.

Common issues include:

- Invoice amount mismatch
- Vendor name mismatch
- Missing or invalid purchase order
- Duplicate payment
- Payment not found
- High tax amount
- High-value invoice
- Unknown vendor
- Missing invoice details

This project automates the reconciliation process and surfaces only the exceptions that require human attention.

---

## Key Features

- Upload Purchase Order CSV
- Upload Bank Statement CSV
- Upload Single Invoice File
- Extract invoice fields from TXT, PDF, PNG, JPG, and JPEG files
- Perform three-way reconciliation
- Detect duplicate payments
- Detect anomalies
- Generate rule-based exception explanation
- Generate LangChain AI reconciliation review
- Route exceptions to human approval queue
- Generate rule-based vendor email draft
- Generate LangChain AI vendor email draft
- Download reconciliation report as CSV
- Streamlit dashboard for easy demo and review

---

## Where LangChain Is Used

LangChain is used as the AI layer of the project.

It is used for:

1. **AI Reconciliation Review Agent**
   - Reads invoice data, reconciliation result, duplicate result, and anomaly result.
   - Generates a business-friendly explanation.
   - Provides risk level and recommended action.

2. **AI Vendor Email Draft Agent**
   - Reads the exception details.
   - Drafts a professional vendor email.
   - Creates communication based on actual reconciliation findings.

The financial matching logic is still rule-based because reconciliation must be deterministic and auditable. LangChain is added on top of the matching engine to improve explanation, review, and communication.

---

## Technology Stack

### Core Development

- **Python**  
  Used as the main programming language for document processing, matching logic, anomaly detection, and workflow automation.

- **VS Code**  
  Used as the primary development environment for coding, debugging, and project management.

### Frontend

- **Streamlit**  
  Used to build the interactive web dashboard for uploading files, viewing results, approving exceptions, and downloading reports.

### Data Processing

- **Pandas**  
  Used for reading, cleaning, transforming, and analyzing purchase order CSV and bank statement CSV files.

### Document Parsing and OCR

- **pdfplumber**  
  Used to extract text from PDF invoices.

- **PyMuPDF**  
  Used for PDF handling and future support for complex or scanned PDF files.

- **Tesseract OCR**  
  Used to extract text from invoice images and scanned documents.

- **pytesseract**  
  Python wrapper used to connect Tesseract OCR with the application.

### AI and Agentic Layer

- **LangChain**  
  Used to build the AI reconciliation review agent and vendor email drafting agent.

- **langchain-openai**  
  Used to connect LangChain with OpenAI chat models.

- **OpenAI API**  
  Used by LangChain to generate AI-powered explanations and email drafts.

### Storage

- **CSV Files**  
  Used for purchase orders, bank statements, approval decisions, and downloadable reconciliation reports.

---

## Project Structure

```text
invoice-reconciliation-agent/
│
├── app.py
├── requirements.txt
├── README.md
├── .env
│
├── data/
│   ├── invoices/
│   │   ├── invoice1.txt
│   │   ├── invoice2.txt
│   │   ├── invoice3.txt
│   │   ├── invoice4.txt
│   │   ├── invoice5.txt
│   │   ├── invoice6.txt
│   │   └── invoice7.txt
│   │
│   ├── po/
│   │   └── purchase_orders.csv
│   │
│   └── bank/
│       └── bank_statement.csv
│
├── src/
│   ├── __init__.py
│   ├── po_parser.py
│   ├── bank_parser.py
│   ├── invoice_parser.py
│   ├── matcher.py
│   ├── duplicate_detector.py
│   ├── anomaly_detector.py
│   ├── explanation_agent.py
│   ├── ai_agent.py
│   ├── approval_workflow.py
│   └── email_drafter.py
│
└── output/
    └── approval_decisions.csv

---

## Workflow

```text
Upload PO CSV
      ↓
Upload Bank Statement CSV
      ↓
Upload Single Invoice
      ↓
Extract Invoice Data
      ↓
Perform Three-Way Matching
      ↓
Detect Duplicate Payments
      ↓
Detect Anomalies
      ↓
Generate Rule-Based Explanation
      ↓
Generate LangChain AI Review
      ↓
Human Approval Queue
      ↓
Generate Vendor Email Draft
      ↓
Download Reconciliation Report
```

---

## Invoice Test Scenarios

The project includes multiple invoice scenarios for testing:

1. **Invoice 1: Perfect Match**
   - PO, invoice, and bank payment match correctly.

2. **Invoice 2: Amount Mismatch**
   - Invoice amount does not match PO amount or bank payment amount.

3. **Invoice 3: Vendor Mismatch**
   - Vendor name on invoice does not match vendor in PO.

4. **Invoice 4: Missing PO**
   - Invoice does not contain a valid PO number.

5. **Invoice 5: No Payment Found**
   - Invoice exists but matching bank transaction is missing.

6. **Invoice 6: High Tax Anomaly**
   - Tax percentage is higher than expected threshold.

7. **Invoice 7: High Value Invoice**
   - Invoice amount is above high-value review threshold.

---

## Supported Exceptions

- `AMOUNT_MISMATCH`
- `BANK_AMOUNT_MISMATCH`
- `VENDOR_MISMATCH`
- `PAYMENT_NOT_FOUND`
- `MISSING_OR_INVALID_PO`
- `MISSING_PO`
- `DUPLICATE_PAYMENT`
- `HIGH_TAX`
- `HIGH_VALUE_INVOICE`
- `UNKNOWN_VENDOR`
- `INVALID_AMOUNT`
- `MISSING_INVOICE_DATE`
- `PROCESSING_ERROR`

---

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

For Windows:

```bash
venv\Scripts\activate
```

For macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If LangChain packages are not installed, install them manually:

```bash
pip install langchain langchain-openai python-dotenv
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_api_key_here
```

Do not commit `.env` to GitHub because it contains a secret key.

---

## Run Application

```bash
streamlit run app.py
```

Application URL:

```text
http://localhost:8501
```

---

## Sample Purchase Order CSV

```csv
po_number,vendor_name,total_amount,status
PO1001,ABC Technologies,100000,Approved
PO1002,Global Stationery,15000,Approved
PO1003,CloudNet Services,25000,Approved
```

---

## Sample Bank Statement CSV

```csv
transaction_id,vendor_name,amount,description,date
TXN001,ABC Technologies,100000,Payment INV9001,2026-07-10
TXN002,Global Stationery,16000,Payment INV9002,2026-07-11
TXN003,ABC Technologies,100000,Payment INV9001,2026-07-12
```

---

## Sample Invoice TXT

```text
Vendor: ABC Technologies
Invoice Number: INV9001
PO Number: PO1001
Invoice Date: 2026-07-08
Subtotal: 90000
Tax: 10000
Total Amount: 100000
```

---

## LangChain AI Review Example

LangChain generates a review like:

```text
1. Executive Summary
Invoice INV9002 requires review because the invoice amount does not match the purchase order amount.

2. Issue Identified
Amount mismatch was found between the invoice and PO.

3. Risk Level
Medium

4. Human Review Required
Yes, because financial mismatch requires validation before payment.

5. Recommended Action
Ask the vendor to confirm the amount difference or submit a corrected invoice.
```

---

## LangChain Vendor Email Example

```text
Subject: Amount Mismatch Clarification for Invoice INV9002

Dear Global Stationery Team,

We are reviewing invoice INV9002 against purchase order PO1002. During reconciliation, an amount difference was identified between the invoice and approved purchase order.

Please verify the invoice amount and share a corrected invoice or supporting clarification.

Regards,
Accounts Payable Team
```

---

## Output

The application produces:

- Dashboard summary
- Three-way reconciliation result
- Duplicate payment result
- Anomaly detection result
- Rule-based explanation
- LangChain AI reconciliation review
- Human approval decision
- Rule-based vendor email draft
- LangChain AI vendor email draft
- Downloadable CSV reconciliation report

---

## Learning Outcomes

This project demonstrates:

- OCR and document processing
- PDF and image invoice extraction
- CSV parsing and validation
- Three-way financial reconciliation
- Duplicate payment detection
- Rule-based anomaly detection
- Human-in-the-loop workflow
- LangChain-based AI review agent
- Vendor email draft automation
- Streamlit dashboard development
- End-to-end capstone project design

---

## Future Enhancements

- Bulk invoice processing
- SQLite or PostgreSQL database integration
- Azure AI Document Intelligence integration
- Advanced ML anomaly detection
- User login and role-based access control
- Email sending through SMTP or Microsoft Graph API
- REST API using FastAPI
- Deployment on cloud platform
- Audit trail and approval history dashboard

---

## Author

**Yogesh Agrawal**

Capstone Project: Intelligent Invoice & Expense Reconciliation Agent
