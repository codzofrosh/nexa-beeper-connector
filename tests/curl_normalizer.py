import re
import sys

def normalize_curl(curl_text: str) -> str:
    # Remove line continuation characters: \, ^, `
    curl_text = re.sub(r'\\\s*\n', ' ', curl_text)
    curl_text = re.sub(r'\^\s*\n', ' ', curl_text)
    curl_text = re.sub(r'`\s*\n', ' ', curl_text)

    # Remove remaining newlines
    curl_text = re.sub(r'\s*\n\s*', ' ', curl_text)

    # Collapse multiple spaces
    curl_text = re.sub(r'\s+', ' ', curl_text)

    return curl_text.strip()


if __name__ == "__main__":
    print("Paste curl command, then press Ctrl+D (Linux/macOS) or Ctrl+Z + Enter (Windows):\n")
    input_text = sys.stdin.read()
    print("\nSingle-line curl:\n")
    print(normalize_curl(input_text))
