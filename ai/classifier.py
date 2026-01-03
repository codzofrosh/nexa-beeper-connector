# def classify(text: str) -> dict:
#     text = text.lower()

#     if "?" in text:
#         intent = "enquiry"
#     elif "please" in text:
#         intent = "request"
#     elif "offer" in text or "buy now" in text:
#         intent = "promotion"
#     elif "not working" in text or "bad" in text:
#         intent = "complaint"
#     else:
#         intent = "other"

#     sentiment = "neutral"
#     if any(w in text for w in ["bad", "worst", "hate"]):
#         sentiment = "negative"
#     elif any(w in text for w in ["good", "thanks", "great"]):
#         sentiment = "positive"

#     return {
#         "intent": intent,
#         "sentiment": sentiment,
#         "confidence": 0.7 if intent != "other" else 0.3,
#     }

def classify(text: str) -> tuple [str, float]:
    text = text.lower()

    if not text:
        return "UNKNOWN", 0.0
    if any(k in text for k in ["price", "cost", "pricing"]):
        return "ENQUIRY",0.85
    if any(k in text for k in ["buy", "order", "purchase"]):
        return "INTENT", 0.8
    if any(k in text for k in ["spam", "offer", "free"]):
        return "PROMOTION", 0.75

    return "SOCIAL",0.4
