"""Small adapter based on Tuya's official Python Pulsar SDK example.

Reference: https://github.com/tuya/tuya-pulsar-sdk-python
The official sample supports the current Message Service ``aes_gcm`` envelope
as well as legacy ECB envelopes.  Secrets are accepted only as function inputs
and are never logged or returned.
"""

from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from Crypto.Cipher import AES


def build_authentication(pulsar: Any, access_id: str, access_secret: str) -> Any:
    """Build Tuya's documented Pulsar AuthenticationBasic instance."""

    secret_md5 = hashlib.md5(access_secret.encode("utf-8")).hexdigest()
    password_md5 = hashlib.md5(f"{access_id}{secret_md5}".encode("utf-8")).hexdigest()
    username = f'{{"username": "{access_id}","password"'
    password = f'"{password_md5[8:24]}"}}'
    return pulsar.AuthenticationBasic(username, password, "auth1")


def decrypt_message(payload: bytes, properties: dict[str, str], access_secret: str) -> dict[str, Any]:
    """Decrypt and parse one Tuya Message Service payload without logging it."""

    envelope = json.loads(payload.decode("utf-8"))
    encrypted = base64.b64decode(envelope["data"])
    key = access_secret[8:24].encode("utf-8")
    encryption_mode = properties.get("em", "")
    if encryption_mode == "aes_gcm":
        nonce, ciphertext, tag = encrypted[:12], encrypted[12:-16], encrypted[-16:]
        plaintext = AES.new(key, AES.MODE_GCM, nonce).decrypt_and_verify(ciphertext, tag)
    else:
        plaintext = AES.new(key, AES.MODE_ECB).decrypt(encrypted).replace(b"\r", b"").replace(b"\n", b"").replace(b"\f", b"")
    decoded = json.loads(plaintext.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Tuya decrypted payload must be a JSON object")
    return decoded


def message_id(message: Any) -> str:
    """Return the stable Pulsar ledger/entry/partition/batch identifier."""

    return f"{message.ledger_id()}:{message.entry_id()}:{message.partition()}:{message.batch_index()}"
