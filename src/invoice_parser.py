import re
import pdfplumber
import pytesseract
from PIL import Image


# If Tesseract is not available in PATH, uncomment this line:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_text_from_txt(uploaded_file):
    text = uploaded_file.read().decode("utf-8")
    return text


def extract_text_from_pdf(uploaded_file):
    text = ""

    with pdfplumber.open(uploaded_file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    return text


def extract_text_from_image(uploaded_file):
    image = Image.open(uploaded_file)
    text = pytesseract.image_to_string(image)
    return text


def extract_invoice_text(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".txt"):
        return extract_text_from_txt(uploaded_file)

    elif file_name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)

    elif file_name.endswith((".png", ".jpg", ".jpeg")):
        return extract_text_from_image(uploaded_file)

    else:
        return ""


def extract_field(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def clean_amount(value):
    if value is None:
        return 0

    value = str(value)
    value = value.replace(",", "")
    value = value.replace("₹", "")
    value = value.replace("Rs.", "")
    value = value.replace("INR", "")
    value = value.strip()

    try:
        return float(value)
    except ValueError:
        return 0


def parse_invoice(uploaded_file):
    text = extract_invoice_text(uploaded_file)

    invoice_number = extract_field(
        r"Invoice\s*(Number|No|#)?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        text
    )

    if invoice_number and isinstance(invoice_number, str):
        # Because regex has 2 groups, we need a simpler fallback below
        pass

    invoice_number_match = re.search(
        r"Invoice\s*(Number|No|#)?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE
    )

    if invoice_number_match:
        invoice_number = invoice_number_match.group(2)
    else:
        invoice_number = None

    vendor_name = extract_field(
        r"Vendor\s*[:\-]?\s*([A-Za-z0-9\s&.,]+)",
        text
    )

    po_number = extract_field(
        r"PO\s*(Number|No|#)?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        text
    )

    po_number_match = re.search(
        r"PO\s*(Number|No|#)?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        text,
        re.IGNORECASE
    )

    if po_number_match:
        po_number = po_number_match.group(2)
    else:
        po_number = None

    invoice_date = extract_field(
        r"Invoice\s*Date\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
        text
    )

    subtotal = extract_field(
        r"Subtotal\s*[:\-]?\s*₹?\s*([0-9,]+\.?[0-9]*)",
        text
    )

    tax = extract_field(
        r"Tax\s*[:\-]?\s*₹?\s*([0-9,]+\.?[0-9]*)",
        text
    )

    total_amount = extract_field(
        r"Total\s*Amount\s*[:\-]?\s*₹?\s*([0-9,]+\.?[0-9]*)",
        text
    )

    if total_amount is None:
        total_amount = extract_field(
            r"Total\s*[:\-]?\s*₹?\s*([0-9,]+\.?[0-9]*)",
            text
        )

    invoice_data = {
        "invoice_number": invoice_number,
        "vendor_name": vendor_name,
        "po_number": po_number,
        "invoice_date": invoice_date,
        "subtotal": clean_amount(subtotal),
        "tax": clean_amount(tax),
        "total_amount": clean_amount(total_amount),
        "raw_text": text
    }

    return invoice_data