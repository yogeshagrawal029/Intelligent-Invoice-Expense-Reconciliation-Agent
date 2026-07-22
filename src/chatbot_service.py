from src.database import get_reconciliation_summary, save_chatbot_message

def chatbot_help():
    return "Ask: summary, show invoice INV9002, show failed emails, show audit logs, approve invoice INV9002 comment Looks good."

def handle_chatbot_message(message, current_user, permissions):
    lower = message.lower().strip()
    if "summary" in lower:
        s = get_reconciliation_summary()
        response = f"Total: {s['total']} | Matched: {s['matched']} | Exceptions: {s['exceptions']} | Human review: {s['human_review']} | Duplicates: {s['duplicates']}"
    else:
        response = chatbot_help()
    save_chatbot_message(current_user.get("username"), current_user.get("role"), message, response, "READ")
    return response, "READ"

