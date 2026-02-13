from __future__ import annotations
from cryptography.fernet import Fernet

class Crypto:
    def __init__(self, fernet_key: str):
        self._fernet = Fernet(fernet_key.encode("utf-8"))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
