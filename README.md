# Intelligent Invoice & Expense Reconciliation Agent

## Overview

The **Intelligent Invoice & Expense Reconciliation Agent** is a Streamlit-based capstone project that automates invoice reconciliation using document parsing, OCR, rule-based matching, anomaly detection, human approval workflow, SMTP email automation, SQLite persistence, role-based access control, audit logging, and **LangChain-powered AI review**.

The application performs three-way matching between:

```text
Purchase Order  ↔  Invoice  ↔  Bank Statement
```

It extracts invoice details from TXT, PDF, and image files, validates invoices against purchase orders and bank transactions, detects mismatches, duplicate payments, anomalies, and routes exceptions for human review. LangChain is used to generate business-friendly AI reconciliation explanations and professional vendor email drafts.

---

## Problem Statement

Manual invoice reconciliation is time-consuming, error-prone, and difficult to scale. Finance and operations teams often need to manually verify invoices against purchase orders and bank payments.

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
- Unauthorized or untracked approvals
- Email communication delays
- Lack of audit trail for user actions

This project automates reconciliation, stores results in a database, enables controlled human review, sends vendor communication, and maintains an audit-ready activity log.

---

## Key Features

### Reconciliation Features

- Upload Purchase Order CSV
- Upload Bank Statement CSV
- Upload single invoice file
- Upload multiple invoice files for bulk processing
- Extract invoice fields from TXT, PDF, PNG, JPG, and JPEG files
- Perform three-way matching between PO, invoice, and bank statement
- Detect amount mismatch
- Detect vendor mismatch
- Detect missing or invalid PO
- Detect missing payment
- Detect duplicate payment
- Detect high tax anomaly
- Detect high-value invoice anomaly
- Generate rule-based exception explanation
- Prevent duplicate reconciliation database entries for the same invoice
- Store reconciliation results in SQLite database

### LangChain AI Features

- Generate LangChain AI reconciliation review
- Generate business-friendly exception explanation
- Generate risk-level summary
- Generate recommended next action
- Generate LangChain vendor email draft
- Allow human review before email sending

### Human Approval Workflow

- Route exceptions to human approval
- Save approval decision to SQLite database
- Store reviewer comments
- Store the username of the approver in the Approval Section
- Display approval records with:

```text
id
invoice_number
decision
comment
approved_by
decision_time
```

### Email Features

- Send vendor email from the application using SMTP
- Support To, CC, and BCC fields
- Save email logs in SQLite database
- Save unsent emails as drafts
- View all email logs
- Retry failed or unsent emails
- Remove failed email from retry list after successful retry
- Send password reset code by email
- Send initial temporary password by email
- Send temporary password from User Management fallback flow
- Send password change notification email after password update

### User Authentication and RBAC

- Login and logout
- Forgot password flow
- Password reset using email reset code
- First-time login password reset enforcement
- SQLite-based user management
- Role-based access control

Supported roles:

```text
Admin
Editor
Email Sender
Viewer
Pending
```

### User Management Features

- View all users
- Create users
- Edit users
- Delete users
- Activate or deactivate users
- Assign roles
- Prevent duplicate username
- Prevent duplicate email address
- Normalize email addresses to lowercase
- Display User Management table with separate action columns:

```text
Edit | Delete | Send Password
```

### Super Admin and Admin Role Rules

Only the exact username below can create, edit, delete, or update users:

```text
admin
```

The default `admin` user can:

```text
Create users
Edit users
Delete users
Update users
Send temporary password to any user
View User Management tab
View Audit Logs tab
Perform all operational admin activities
```

Any other user with role `Admin` can:

```text
View User Management tab
View Audit Logs tab
Perform operational admin activities
Send temporary password to non-default-admin users
```

Any other user with role `Admin` cannot:

```text
Create users
Edit users
Delete users
Update users
Reset default admin password
```

### Password Policy Features

Passwords must follow these rules:

```text
Allowed characters:
A-Z
a-z
0-9
@ # !

Required:
At least one uppercase letter
At least one lowercase letter
At least one number
At least one special character from @, #, !

Length:
Minimum 10 characters
Maximum 16 characters

Blocked:
Sequential numbers like 1234 or 12345
Sequential letters like abcd or ABCD
Reverse sequences like dcba or 4321
Same character repeated 4 or more times

History:
Last 3 passwords cannot be reused
```

### First-Time Password Flow

When Admin creates a user:

1. Admin enters username, email, role, and status.
2. Admin does not enter a password.
3. The application generates a compliant temporary password.
4. The temporary password is sent to the user's registered email.
5. User logs in using the temporary password.
6. User is forced to reset the password.
7. User must login again using the new password.

### First-Time Admin Setup

On the very first launch, if the default `admin` user does not exist:

1. The application generates a compliant temporary admin password.
2. The temporary password is sent to `DEFAULT_ADMIN_EMAIL`.
3. The admin user is created with `must_change_password=1`.
4. Admin logs in with the temporary password.
5. Admin is forced to reset password.
6. Admin logs in again with the new password.

No hardcoded admin password is required in `.env`.

### Forgot Password Fallback

If Forgot Password email or reset code sending fails, an Admin role user can use User Management:

```text
User Management → Send Password column → 🔑
```

This action:

1. Generates a compliant temporary password.
2. Updates the selected user's password.
3. Sets `must_change_password=1`.
4. Attempts to send the temporary password by email.
5. If email fails, shows the temporary password once on screen to the Admin.
6. Logs the event in the audit table.

### Audit Logging Features

The application logs user activities in SQLite for future audit purposes.

Logged events include:

```text
LOGIN success
LOGIN failed
LOGOUT
PASSWORD_RESET_CODE_REQUEST success
PASSWORD_RESET_CODE_REQUEST failed
PASSWORD_RESET success
PASSWORD_RESET failed
FIRST_LOGIN_PASSWORD_CHANGE_REQUIRED
FIRST_LOGIN_PASSWORD_RESET
USER_CREATED
USER_UPDATED
USER_DELETED
INITIAL_PASSWORD_SENT
TEMPORARY_PASSWORD_SENT_FROM_USER_MANAGEMENT
INVOICE_APPROVAL_SAVED
```

Audit records include:

```text
event_type
actor_username
target_username
target_email
actor_role
status
ip_address
user_agent
details
created_at
```

---

## Where LangChain Is Used

LangChain is used as the AI layer of the project.

It is used for:

### 1. AI Reconciliation Review Agent

- Reads invoice data, reconciliation result, duplicate result, and anomaly result.
- Generates a business-friendly explanation.
- Provides risk level and recommended action.
- Helps reviewers understand why an invoice requires attention.

### 2. AI Vendor Email Draft Agent

- Reads exception details.
- Drafts professional vendor communication.
- Creates email content based on reconciliation findings.

The financial matching logic remains rule-based because reconciliation must be deterministic and auditable. LangChain is added on top of the matching engine to improve explanation, review, and communication.

---

## Technology Stack

### Core Development

- **Python**  
  Main programming language for document processing, matching, anomaly detection, authentication, audit logging, and workflow automation.

- **VS Code**  
  Development environment for coding and debugging.

### Frontend

- **Streamlit**  
  Web dashboard for authentication, file upload, reconciliation, approval, email logs, user management, and audit logs.

### Data Processing

- **Pandas**  
  Used for reading, cleaning, transforming, and displaying CSV and database records.

### Document Parsing and OCR

- **pdfplumber**  
  Extracts text from PDF invoices.

- **PyMuPDF**  
  Supports PDF handling and scanned PDF workflows.

- **Tesseract OCR**  
  Extracts text from invoice images and scanned documents.

- **pytesseract**  
  Python wrapper for Tesseract OCR.

### AI and Agentic Layer

- **LangChain**  
  Builds the AI reconciliation review and AI vendor email drafting flow.

- **langchain-openai**  
  Connects LangChain with OpenAI chat models.

- **OpenAI API**  
  Generates AI-powered explanations and email drafts.

### Database and Storage

- **SQLite**  
  Stores users, reconciliation results, approvals, email logs, password reset tokens, password history, and audit logs.

### Email

- **SMTP**  
  Sends vendor emails, password reset codes, temporary passwords, and password change notifications.

---

## Project Structure

```text
invoice-reconciliation-agent/
│
├── app.py
├── requirements.txt
├── README.md
├── .env
├── invoice_agent.db
│
├── data/
│   ├── invoices/
│   ├── po/
│   │   └── purchase_orders.csv
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
│   ├── reconciliation_service.py
│   ├── database.py
│   ├── auth_service.py
│   └── email_sender.py
│
└── output/
```

> Note: `email_drafter.py` is no longer required if vendor email drafting is handled by `generate_langchain_email()` in `src/ai_agent.py` and email sending is handled by `src/email_sender.py`.

---

## SQLite Tables

The application uses these main SQLite tables:

```text
users
password_history
password_reset_tokens
reconciliation_results
approval_decisions
email_logs
user_activity_audit
```

### users

Stores user profile and authentication metadata.

```text
id
username
email
password_hash
role
is_active
must_change_password
created_at
```

### password_history

Stores password hashes for last-password reuse prevention.

```text
id
username
password_hash
created_at
```

### password_reset_tokens

Stores reset codes for forgot password flow.

```text
id
username
email
reset_code
is_used
expires_at
created_at
```

### reconciliation_results

Stores invoice reconciliation results.

### approval_decisions

Stores approval decisions and approver username.

```text
id
invoice_number
decision
comment
approved_by
decision_time
```

### email_logs

Stores sent, failed, and draft email records.

### user_activity_audit

Stores full user and admin activity logs.

---

## Workflow

```text
Login
  ↓
Upload PO CSV
  ↓
Upload Bank Statement CSV
  ↓
Upload Invoice or Multiple Invoices
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
Human Approval Workflow
  ↓
Save Approval with approved_by user
  ↓
Generate Vendor Email Draft
  ↓
Send Email or Save Draft
  ↓
Store Results, Logs, and Audit Trail in SQLite
```

---

## Invoice Test Scenarios

The project supports these test scenarios:

1. **Perfect Match**
   - PO, invoice, and bank payment match correctly.

2. **Amount Mismatch**
   - Invoice amount does not match PO amount or bank payment amount.

3. **Vendor Mismatch**
   - Vendor name on invoice does not match vendor in PO.

4. **Missing PO**
   - Invoice does not contain a valid PO number.

5. **No Payment Found**
   - Invoice exists but matching bank transaction is missing.

6. **High Tax Anomaly**
   - Tax percentage is higher than expected threshold.

7. **High Value Invoice**
   - Invoice amount is above high-value review threshold.

8. **Duplicate Payment**
   - Multiple bank transactions may match the same invoice.

9. **Processing Error**
   - Invoice file cannot be parsed or processed.

---

## Supported Exceptions

```text
AMOUNT_MISMATCH
BANK_AMOUNT_MISMATCH
VENDOR_MISMATCH
PAYMENT_NOT_FOUND
MISSING_OR_INVALID_PO
MISSING_PO
DUPLICATE_PAYMENT
HIGH_TAX
HIGH_VALUE_INVOICE
UNKNOWN_VENDOR
INVALID_AMOUNT
MISSING_INVOICE_DATE
PROCESSING_ERROR
```

---

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

For Windows CMD:

```bash
venv\Scripts\activate
```

For Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

For macOS/Linux:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

If LangChain packages are missing:

```bash
pip install langchain langchain-openai python-dotenv
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here

SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=yourgmail@gmail.com
SMTP_PASSWORD=your_16_character_gmail_app_password

DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_EMAIL=yourgmail@gmail.com
```

Do not commit `.env` to GitHub because it contains secrets.

---

## First Launch Admin Setup

On first launch, if the `admin` user does not exist:

```text
Username: admin
Temporary password: sent to DEFAULT_ADMIN_EMAIL
```

Admin must reset the temporary password on first login.

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
- Rule-based exception explanation
- LangChain AI reconciliation review
- Human approval decision with approver username
- LangChain AI vendor email draft
- Email send logs
- Failed email retry queue
- User activity audit logs
- SQLite-backed reconciliation history

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
- SMTP email integration
- SQLite database integration
- Login and role-based access control
- Secure password policy enforcement
- Password reset and first-login reset workflows
- User management and audit logging
- Streamlit dashboard development
- End-to-end capstone project design

---

## Future Enhancements

- PostgreSQL database integration
- Microsoft Graph email integration
- Azure AI Document Intelligence
- Advanced ML anomaly detection
- FastAPI backend service
- Docker deployment
- Cloud deployment
- Export audit reports
- Approval workflow notifications
- Multi-level approval routing
- Dashboard analytics for finance KPIs

---

## Author

**Yogesh Agrawal**

Capstone Project: Intelligent Invoice & Expense Reconciliation Agent
