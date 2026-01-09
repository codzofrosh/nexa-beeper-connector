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


"""AI pipeline that composes classifier + policy.

`run_pipeline` is intentionally small: it takes a raw text string, runs a
classifier to obtain a label and confidence, and then a policy to decide
an action (NOTIFY, ESCALATE, IGNORE, ...).
"""

from ai.classifier import classify
from ai.policy import decide


def run_pipeline(text: str):
    """Run classification and policy to produce an action dict.

    Returns a dict with keys: label, confidence, action.
    """
    label, confidence = classify(text)
    action = decide(label, confidence)

    return {
        "label": label,
        "confidence": confidence,
        "action": action,
    }
