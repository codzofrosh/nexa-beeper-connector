def run_pipeline(msg: dict):
    """
    msg = normalized message
    """
    text = msg["text"]

    # Placeholder logic
    if "buy" in text.lower() or "price" in text.lower():
        return "ENQUIRY"
    if "offer" in text.lower() or "sale" in text.lower():
        return "PROMOTION"
    return "GENERAL"
