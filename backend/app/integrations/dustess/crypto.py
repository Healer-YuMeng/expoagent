from __future__ import annotations

import base64
import hashlib

from Crypto.Cipher import AES  # type: ignore


def sha1_signature(*values: str | None) -> str:
    parts = [v for v in values if v]
    parts.sort()
    data = "".join(parts).encode("utf-8")
    return hashlib.sha1(data).hexdigest()


def decode_aes_key(encoding_key: str) -> bytes:
    if not encoding_key:
        raise ValueError("encoding_aes_key 不能为空")
    padding = "=" * (4 - len(encoding_key) % 4)
    return base64.b64decode(encoding_key + padding)


def pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > 32:
        raise ValueError("invalid padding")
    return data[:-pad]


def aes_decrypt(encrypted: str, aes_key: bytes) -> bytes:
    cipher = AES.new(aes_key, AES.MODE_CBC, aes_key[:16])
    decoded = base64.b64decode(encrypted)
    return pkcs7_unpad(cipher.decrypt(decoded))
