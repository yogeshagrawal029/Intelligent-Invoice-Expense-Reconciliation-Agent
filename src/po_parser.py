# src/po_parser.py

import pandas as pd


def load_purchase_orders(uploaded_file):
    """
    Load Purchase Order CSV
    """

    po_df = pd.read_csv(uploaded_file)

    po_df.columns = po_df.columns.str.strip()

    return po_df


def validate_po_columns(po_df):

    required_columns = [
        "po_number",
        "vendor_name",
        "total_amount"
    ]

    missing = []

    for column in required_columns:
        if column not in po_df.columns:
            missing.append(column)

    return missing