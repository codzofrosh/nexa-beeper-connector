def decide(classification: dict) -> str:
    intent = classification["intent"]

    if intent == "promotion":
        return "SUPPRESS"
    if intent in ("enquiry", "request"):
        return "NOTIFY"
    if intent == "complaint":
        return "ESCALATE"

    return "IGNORE"
