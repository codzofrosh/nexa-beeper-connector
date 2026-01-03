# def decide(classification: dict) -> str:
#     intent = classification["intent"]

#     if intent == "promotion":
#         return "SUPPRESS"
#     if intent in ("enquiry", "request"):
#         return "NOTIFY"
#     if intent == "complaint":
#         return "ESCALATE"

#     return "IGNORE"

def decide(label: str, confidence: float) -> str:
    """
    Returns one of:
    NOTIFY
    ESCALATE
    IGNORE
    """
    if confidence < 0.6:
        return "IGNORE"

    if label == "ENQUIRY":
        return "NOTIFY"

    if label == "SUPPORT":
        return "ESCALATE"

    return "IGNORE"
