"""Credential encryption and storage in database."""

from __future__ import annotations

import base64
import hashlib
import os
import platform
import sqlite3
from pathlib import Path

from cryptography.fernet import Fernet


def _get_machine_id() -> str:
    """Get a machine-specific identifier."""
    # Try Linux machine-id
    machine_id_path = Path("/etc/machine-id")
    if machine_id_path.exists():
        return machine_id_path.read_text().strip()
    
    # Fallback: combine hostname and username
    return f"{platform.node()}-{os.getenv('USER', os.getenv('USERNAME', 'unknown'))}"


def _derive_key() -> bytes:
    """Derive encryption key from machine-specific data."""
    machine_id = _get_machine_id()
    username = os.getenv("USER", os.getenv("USERNAME", "unknown"))
    
    # Combine machine ID and username
    salt = f"gitnoteline-{machine_id}-{username}"
    
    # Derive key using PBKDF2
    key = hashlib.pbkdf2_hmac(
        "sha256",
        salt.encode(),
        b"gitnoteline-salt-v1",  # Additional salt
        iterations=100000,
    )
    
    # Fernet requires 32-byte key, base64-encoded
    return base64.urlsafe_b64encode(key)


def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    key = _derive_key()
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string."""
    f = _get_fernet()
    encrypted = f.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a secret string."""
    f = _get_fernet()
    decrypted = f.decrypt(ciphertext.encode())
    return decrypted.decode()


def store_credential(conn: sqlite3.Connection, credential_id: int, secret: str) -> bool:
    """Store an encrypted credential in the database.
    
    Args:
        conn: Database connection
        credential_id: The ID of the credential record
        secret: The plaintext secret to encrypt and store
        
    Returns:
        True if stored successfully, False otherwise
    """
    try:
        encrypted = encrypt_secret(secret)
        conn.execute(
            "UPDATE credentials SET encrypted_secret = ? WHERE id = ?",
            (encrypted, credential_id),
        )
        conn.commit()
        return True
    except Exception:
        return False


def get_credential(conn: sqlite3.Connection, credential_id: int) -> str | None:
    """Retrieve and decrypt a credential from the database.
    
    Args:
        conn: Database connection
        credential_id: The ID of the credential record
        
    Returns:
        The decrypted secret, or None if not found
    """
    try:
        row = conn.execute(
            "SELECT encrypted_secret FROM credentials WHERE id = ?",
            (credential_id,),
        ).fetchone()
        
        if row and row["encrypted_secret"]:
            return decrypt_secret(row["encrypted_secret"])
        return None
    except Exception:
        return None
