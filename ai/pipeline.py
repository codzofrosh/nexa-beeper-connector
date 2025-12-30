# def run_pipeline(msg: dict):
#     """
#     msg = normalized message
#     """
#     text = msg["text"]

#     # Placeholder logic
#     if "buy" in text.lower() or "price" in text.lower():
#         return "ENQUIRY"
#     if "offer" in text.lower() or "sale" in text.lower():
#         return "PROMOTION"
#     return "GENERAL"

from ai.classifier import classify
from ai.policy import decide

def run_pipeline(text: str) -> str:
    label = classify(text)
    action = decide(label)
    return f"{label}:{action}"
