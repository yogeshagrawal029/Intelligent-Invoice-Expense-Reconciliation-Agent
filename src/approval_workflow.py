import pandas as pd
import os
from datetime import datetime


APPROVAL_FILE = "output/approval_decisions.csv"


def save_approval_decision(invoice_number, decision, comment):
    os.makedirs("output", exist_ok=True)

    record = {
        "invoice_number": invoice_number,
        "decision": decision,
        "comment": comment,
        "decision_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    df = pd.DataFrame([record])

    if os.path.exists(APPROVAL_FILE):
        old_df = pd.read_csv(APPROVAL_FILE)
        final_df = pd.concat([old_df, df], ignore_index=True)
    else:
        final_df = df

    final_df.to_csv(APPROVAL_FILE, index=False)

    return record