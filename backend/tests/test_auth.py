from q2h.auth.service import AuthService


def test_hash_and_verify_password():
    svc = AuthService()
    hashed = svc.hash_password("MyStr0ng!Pass")
    assert svc.verify_password("MyStr0ng!Pass", hashed)
    assert not svc.verify_password("wrong", hashed)


def test_create_and_decode_token():
    svc = AuthService()
    token = svc.create_access_token(user_id=1, username="admin", profile="admin")
    payload = svc.decode_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "admin"
    assert payload["profile"] == "admin"


def test_refresh_token():
    svc = AuthService()
    token = svc.create_refresh_token(user_id=42)
    payload = svc.decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "refresh"
