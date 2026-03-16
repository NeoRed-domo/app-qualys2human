"""Ed25519 detached signature verification for upgrade packages."""

import logging
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger("q2h.upgrade")


def _get_public_key_pem() -> str:
    """Load the embedded public key. Separated for testability."""
    from q2h.upgrade.public_key import PUBLIC_KEY_PEM
    return PUBLIC_KEY_PEM


def verify_signature(zip_path: Path, sig_path: Path) -> bool:
    """Verify Ed25519 detached signature of a .zip package.

    Args:
        zip_path: Path to the .zip file.
        sig_path: Path to the detached .sig file.

    Returns:
        True if signature is valid, False otherwise.

    Raises:
        FileNotFoundError: If zip_path or sig_path does not exist.
    """
    pem = _get_public_key_pem()
    public_key = serialization.load_pem_public_key(pem.encode())
    if not isinstance(public_key, Ed25519PublicKey):
        logger.error("Embedded public key is not Ed25519")
        return False

    zip_data = zip_path.read_bytes()
    signature = sig_path.read_bytes()

    try:
        public_key.verify(signature, zip_data)
        return True
    except InvalidSignature:
        logger.warning("Signature verification failed: invalid signature")
        return False
    except Exception as e:
        logger.warning("Signature verification error: %s", e)
        return False
