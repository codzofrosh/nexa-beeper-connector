from ai.pipeline import run_pipeline

TESTS = {
    "price please": ("ENQUIRY", "NOTIFY"),
    "what is the cost?": ("ENQUIRY", "NOTIFY"),
    "limited time offer": ("PROMOTION", "IGNORE"),
    "hi": ("SOCIAL", "IGNORE"),
    "": ("UNKNOWN", "IGNORE"),
}

for text, expected in TESTS.items():
    result = run_pipeline(text)
    print(
        f"{text!r:25} → {result} "
        f"{'✅' if (result['label'], result['action']) == expected else '❌'}"
    )
