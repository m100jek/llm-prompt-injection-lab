import base64
import codecs
import re

VALID_ENCODINGS = {"base64", "rot13", "hex"}


def validate_encoded_payload(text: str, encoding: str) -> None:
    if encoding not in VALID_ENCODINGS:
        raise ValueError(f"Unsupported encoding: {encoding}")

    if encoding == "base64":
        try:
            base64.b64decode(text, validate=True)
        except Exception as exc:
            raise ValueError(f"Invalid base64 payload: {exc}") from exc
        return

    if encoding == "rot13":
        codecs.decode(text, "rot13")
        return

    if encoding == "hex":
        cleaned = text.strip()
        if not re.fullmatch(r"[0-9a-fA-F]+", cleaned) or len(cleaned) % 2 != 0:
            raise ValueError("Invalid hex payload")
