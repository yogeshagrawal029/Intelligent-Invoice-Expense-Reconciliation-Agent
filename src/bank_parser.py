# src/bank_parser.py

import pandas as pd


def load_bank_statement(uploaded_file):
    """
    Load Bank Statement CSV
    """

    bank_df = pd.read_csv(uploaded_file)

    bank_df.columns = bank_df.columns.str.strip()

    return bank_df


def validate_bank_columns(bank_df):

    required_columns = [
        "transaction_id",
        "vendor_name"
    ]

    missing = []

    for column in required_columns:
        if column not in bank_df.columns:
            missing.append(column)

    return missing