import os
import json

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


load_dotenv()


def get_llm():
    """
    Initialize LangChain ChatOpenAI model.
    Make sure OPENAI_API_KEY is available in .env file.
    """
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is missing. Please add it in the .env file."
        )
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        api_key=api_key
    )
    return llm

def safe_json(data):
    """
    Convert dictionaries/lists into formatted JSON string for prompt input.
    """
    try:
        return json.dumps(data, indent=2, default=str)
    except Exception:
        return str(data)

def generate_langchain_review(
    invoice_data,
    recon_row,
    duplicate_result,
    anomalies
):
    """
    LangChain AI Review Agent.
    This explains invoice reconciliation result in plain business language.
    """
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are an expert Accounts Payable reconciliation auditor.
                Your job is to review invoice reconciliation output and explain the result clearly.You must be concise, professional, and business-friendly.
                Do not invent missing data.Use only the provided invoice data, reconciliation data, duplicate result, and anomaly result.
                """
            ),
            (
                "user",
                """
                Analyze the following reconciliation case.
                Invoice Data:{invoice_data}
                Three-Way Reconciliation Result:{recon_row}
                Duplicate Detection Result:{duplicate_result}
                Anomaly Detection Result:{anomalies}
                Please provide the response in this format:
                1. Executive Summary
                2. Issue Identified
                3. Risk Level: Low / Medium / High
                4. Why Human Review Is or Is Not Required
                5. Recommended Action
                """
            )
        ]
    )
    
    chain = prompt | llm
    
    response = chain.invoke(
        {
        "invoice_data": safe_json(invoice_data),
       "recon_row": safe_json(recon_row),
        "duplicate_result": safe_json(duplicate_result),
        "anomalies": safe_json(anomalies)
        }
    )
    return response.content

def generate_langchain_email(
    invoice_data,
    recon_row,
    duplicate_result,
    anomalies
):
    """
    LangChain AI Email Draft Agent.
    This drafts a vendor email based on the exact issue found.
    """
    
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are a professional Accounts Payable email assistant.
                Your task is to draft a polite and clear vendor email for invoice reconciliation issues.
                Do not blame the vendor.
                Do not include unnecessary technical details.
                Do not invent information.Use only the supplied data.
                """
            ),
            (
                "user",
                """Draft a vendor email for the following reconciliation issue.
                Invoice Data:
                    {invoice_data}
                Reconciliation Result:
                    {recon_row}
                Duplicate Detection:
                    {duplicate_result}
                Anomalies:
                    {anomalies}
                Output format:
                Subject: <email subject>
                Body:
                    <email body>
                    """
            )
        ]
    )
    
    chain = prompt | llm
    
    response = chain.invoke(
        {
            "invoice_data": safe_json(invoice_data),
            "recon_row": safe_json(recon_row),
            "duplicate_result": safe_json(duplicate_result),
            "anomalies": safe_json(anomalies)
        }
    )
    
    return response.content