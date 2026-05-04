import os
import re

from tests.helpers.test_client import (
    TEST_USER_PASSWORD,
    ApiClient,
    expect_error,
    expect_ok,
    register_and_login,
    unique_email,
)


def test_email_password_registration_creates_safe_identity() -> None:
    client = ApiClient()
    email = unique_email("auth-register")
    user = expect_ok(
        client.post(
            "/api/auth/register",
            json={"email": email, "password": TEST_USER_PASSWORD, "name": "Registration Test"},
        ),
        201,
    )

    assert user["email"] == email
    assert user["name"] == "Registration Test"
    assert "passwordHash" not in user


def test_duplicate_email_registration_is_rejected() -> None:
    client = ApiClient()
    email = unique_email("auth-duplicate")
    body = {"email": email, "password": TEST_USER_PASSWORD, "name": "First Account"}

    expect_ok(client.post("/api/auth/register", json=body), 201)
    expect_error(client.post("/api/auth/register", json=body), 409, "EMAIL_ALREADY_EXISTS")


def test_login_accepts_valid_credentials_and_me_returns_current_user() -> None:
    client, email = register_and_login(unique_email("auth-login"))
    me = expect_ok(client.get("/api/me"))

    assert me["email"] == email
    assert "passwordHash" not in me


def test_invalid_login_is_rejected_and_does_not_create_session() -> None:
    client = ApiClient()
    email = unique_email("auth-invalid")
    expect_ok(
        client.post(
            "/api/auth/register",
            json={"email": email, "password": TEST_USER_PASSWORD, "name": "Invalid Login Test"},
        ),
        201,
    )

    expect_error(
        client.post("/api/auth/login", json={"email": email, "password": "wrong-password"}),
        401,
        "INVALID_CREDENTIALS",
    )
    expect_error(client.get("/api/me"), 401, "UNAUTHENTICATED")


def test_logout_invalidates_active_session() -> None:
    client, _ = register_and_login(unique_email("auth-logout"))
    expect_ok(client.get("/api/me"))
    expect_ok(client.post("/api/auth/logout"))
    expect_error(client.get("/api/me"), 401, "UNAUTHENTICATED")


def test_google_oauth_is_disabled_for_local_development() -> None:
    client = ApiClient()
    response = client.get("/api/auth/google/start")

    if os.getenv("APP_ENV", "development") == "development":
        expect_error(response, 404, "GOOGLE_OAUTH_DISABLED")
    else:
        assert response.status_code in {302, 303, 307}
        assert re.search(r"google|accounts\.google|oauth", response.headers.get("location", ""), re.I)


def test_password_reset_request_uses_safe_response_semantics() -> None:
    client = ApiClient()
    expect_ok(client.post("/api/auth/password-reset/request", json={"email": unique_email("reset")}))

