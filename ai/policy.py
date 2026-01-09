# def decide(classification: dict) -> str:
#     intent = classification["intent"]

#     if intent == "promotion":
#         return "SUPPRESS"
#     if intent in ("enquiry", "request"):
#         return "NOTIFY"
#     if intent == "complaint":
#         return "ESCALATE"

#     return "IGNORE"

"""Decision policy that maps classification to actions.

This module implements the simple rules that convert a `(label, confidence)`
into a resulting action string used by the rest of the system.
"""

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
