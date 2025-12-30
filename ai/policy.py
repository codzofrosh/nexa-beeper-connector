# def decide(classification: dict) -> str:
#     intent = classification["intent"]

#     if intent == "promotion":
#         return "SUPPRESS"
#     if intent in ("enquiry", "request"):
#         return "NOTIFY"
#     if intent == "complaint":
#         return "ESCALATE"

#     return "IGNORE"

def decide(label: str) -> str:
    if label in ("ENQUIRY", "INTENT"):
        return "NOTIFY"
    if label == "PROMOTION":
        return "SUPPRESS"
    return "IGNORE"
