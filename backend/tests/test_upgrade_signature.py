"""Tests for Ed25519 signature verification."""

import pytest
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization


@pytest.fixture
def tmp_keys(tmp_path):
    """Generate a test keypair (NOT the production key)."""
    private_key = Ed25519PrivateKey.generate()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_pem.decode()


@pytest.fixture
def signed_package(tmp_path, tmp_keys):
    """Create a test .zip and its valid signature."""
    private_key, _ = tmp_keys
    zip_path = tmp_path / "test.zip"
    sig_path = tmp_path / "test.zip.sig"

    zip_data = b"PK\x03\x04fake zip content for testing"
    zip_path.write_bytes(zip_data)

    signature = private_key.sign(zip_data)
    sig_path.write_bytes(signature)

    return zip_path, sig_path


class TestVerifySignature:
    def test_valid_signature(self, signed_package, tmp_keys, monkeypatch):
        zip_path, sig_path = signed_package
        _, public_pem = tmp_keys

        import q2h.upgrade.signature as sig_mod
        monkeypatch.setattr(sig_mod, "_get_public_key_pem", lambda: public_pem)

        assert sig_mod.verify_signature(zip_path, sig_path) is True

    def test_tampered_zip(self, signed_package, tmp_keys, monkeypatch):
        zip_path, sig_path = signed_package
        _, public_pem = tmp_keys

        zip_path.write_bytes(b"tampered content")

        import q2h.upgrade.signature as sig_mod
        monkeypatch.setattr(sig_mod, "_get_public_key_pem", lambda: public_pem)

        assert sig_mod.verify_signature(zip_path, sig_path) is False

    def test_wrong_key(self, signed_package, monkeypatch):
        zip_path, sig_path = signed_package

        wrong_key = Ed25519PrivateKey.generate()
        wrong_pem = wrong_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        import q2h.upgrade.signature as sig_mod
        monkeypatch.setattr(sig_mod, "_get_public_key_pem", lambda: wrong_pem)

        assert sig_mod.verify_signature(zip_path, sig_path) is False

    def test_missing_signature_file(self, tmp_path, tmp_keys, monkeypatch):
        zip_path = tmp_path / "test.zip"
        zip_path.write_bytes(b"content")
        sig_path = tmp_path / "test.zip.sig"  # does not exist

        _, public_pem = tmp_keys
        import q2h.upgrade.signature as sig_mod
        monkeypatch.setattr(sig_mod, "_get_public_key_pem", lambda: public_pem)

        with pytest.raises(FileNotFoundError):
            sig_mod.verify_signature(zip_path, sig_path)

    def test_corrupted_signature(self, tmp_path, tmp_keys, monkeypatch):
        zip_path = tmp_path / "test.zip"
        sig_path = tmp_path / "test.zip.sig"
        zip_path.write_bytes(b"content")
        sig_path.write_bytes(b"not a valid signature")

        _, public_pem = tmp_keys
        import q2h.upgrade.signature as sig_mod
        monkeypatch.setattr(sig_mod, "_get_public_key_pem", lambda: public_pem)

        assert sig_mod.verify_signature(zip_path, sig_path) is False
