def classify(text: str) -> dict:
    text = text.lower()

    if "?" in text:
        intent = "enquiry"
    elif "please" in text:
        intent = "request"
    elif "offer" in text or "buy now" in text:
        intent = "promotion"
    elif "not working" in text or "bad" in text:
        intent = "complaint"
    else:
        intent = "other"

    sentiment = "neutral"
    if any(w in text for w in ["bad", "worst", "hate"]):
        sentiment = "negative"
    elif any(w in text for w in ["good", "thanks", "great"]):
        sentiment = "positive"

    return {
        "intent": intent,
        "sentiment": sentiment,
        "confidence": 0.7 if intent != "other" else 0.3,
    }
