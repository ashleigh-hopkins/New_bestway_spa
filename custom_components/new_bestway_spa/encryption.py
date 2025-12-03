"""AES-256-CBC encryption for Bestway Smart Spa v2 API commands.

This module implements the encryption algorithm discovered through reverse engineering
of the official Bestway Smart Spa Android app (com/rongwei/library/utils/AESEncrypt.java).

The v2 API endpoint (/api/v2/device/command) requires all command payloads to be encrypted
using this specific AES-256-CBC scheme with SHA-256 key derivation.

Algorithm discovered from: AESEncrypt.bestwayEncrypt() method in decompiled APK
Source: layzspa-aws-iot/bestway_spa_client.py (proven working implementation)
"""

import hashlib
import base64
import logging

_LOGGER = logging.getLogger(__name__)

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    _LOGGER.error("pycryptodome not installed - v2 API encryption unavailable")


def encrypt_command_payload(sign: str, app_secret: str, plaintext: str) -> str:
    """
    Encrypt command payload using Bestway's AES/CBC scheme.

    This implements the encryption algorithm from the official Bestway app's
    AESEncrypt.bestwayEncrypt() method discovered through reverse engineering.

    Algorithm:
    1. Derive AES key from request signature and app secret using SHA-256
    2. Use fixed IV from decompiled APK (hardcoded in official app)
    3. Encrypt plaintext with AES-256-CBC and PKCS7 padding
    4. Return base64-encoded (IV + ciphertext)

    Args:
        sign: MD5 signature from current request (uppercase hex)
              Generated as: MD5(app_id + app_secret + nonce + timestamp)
        app_secret: APP_SECRET constant (same for all users, from APK)
        plaintext: Command payload as JSON string

    Returns:
        Base64-encoded encrypted payload: Base64(IV + ciphertext)
        Format: "OG46qEz/Xp/t16u1lihK..." (starts with base64-encoded IV)

    Raises:
        RuntimeError: If pycryptodome is not installed

    Example:
        >>> sign = "C4C0283EF2420F03624068553CC8783C"
        >>> app_secret = "4ECvVs13enL5AiYSmscNjvlaisklQDz7vWPCCWXcEFjhWfTmLT"
        >>> plaintext = '{"device_id":"abc","product_id":"T53NN8","command":{"power":1}}'
        >>> encrypted = encrypt_command_payload(sign, app_secret, plaintext)
        >>> encrypted.startswith("OG46qEz")  # IV prefix in base64
        True
    """
    if not HAS_CRYPTO:
        raise RuntimeError(
            "pycryptodome not installed. Install with: pip install pycryptodome"
        )

    # Fixed IV from decompiled APK (com/rongwei/library/utils/AESEncrypt.java)
    # This IV is hardcoded in the official app and never changes
    iv = bytes(
        [56, 110, 58, 168, 76, 255, 94, 159, 237, 215, 171, 181, 150, 40, 74, 166]
    )

    # Key derivation: SHA-256(f"{sign},{app_secret}")[:32] as UTF-8 bytes
    # Example: "C4C0...83C,4ECv...XcEFjhWfTmLT" → SHA-256 → first 32 hex chars → UTF-8 encode
    key_material = f"{sign},{app_secret}".encode("utf-8")
    key_hex = hashlib.sha256(key_material).hexdigest()[
        :32
    ]  # First 16 bytes as hex string
    key = key_hex.encode("utf-8")  # 32 bytes (UTF-8 encoding of hex string)

    # Encrypt with AES-256-CBC
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    ciphertext = cipher.encrypt(padded)

    # Return base64(IV + ciphertext)
    # The IV is prepended even though it's fixed (matches official app behavior)
    result = base64.b64encode(iv + ciphertext).decode("utf-8")

    _LOGGER.debug("Encrypted payload (first 20 chars): %s...", result[:20])
    return result


def decrypt_command_payload(sign: str, app_secret: str, ciphertext: str) -> str:
    """
    Decrypt command payload (inverse of encrypt_command_payload).

    This is primarily used for testing and debugging to verify encryption correctness.
    The v2 API does not return encrypted responses - this is only for validating
    that our encryption matches the official app's behavior.

    Args:
        sign: Same MD5 signature used for encryption
        app_secret: Same APP_SECRET constant
        ciphertext: Base64-encoded encrypted data

    Returns:
        Decrypted plaintext string

    Raises:
        RuntimeError: If pycryptodome is not installed

    Example:
        >>> encrypted = encrypt_command_payload(sign, app_secret, plaintext)
        >>> decrypted = decrypt_command_payload(sign, app_secret, encrypted)
        >>> decrypted == plaintext
        True
    """
    if not HAS_CRYPTO:
        raise RuntimeError(
            "pycryptodome not installed. Install with: pip install pycryptodome"
        )

    # Derive key the same way as encrypt
    key_material = f"{sign},{app_secret}".encode("utf-8")
    key_hex = hashlib.sha256(key_material).hexdigest()[:32]
    key = key_hex.encode("utf-8")

    # Decode base64 and extract IV + ciphertext
    data = base64.b64decode(ciphertext)
    iv = data[:16]  # First 16 bytes are the IV
    ct = data[16:]  # Remaining bytes are ciphertext

    # Decrypt
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_plaintext = cipher.decrypt(ct)
    plaintext = unpad(padded_plaintext, AES.block_size)

    return plaintext.decode("utf-8")
