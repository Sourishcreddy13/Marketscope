import jwt
import pytest

from app.core.config import ConfigurationError, resolve_jwt_secret


@pytest.mark.nfr04
def test_missing_secret_fails_startup_outside_test_environment():
    for environment in ("development", "production", "staging"):
        with pytest.raises(ConfigurationError):
            resolve_jwt_secret(environment, None)
        with pytest.raises(ConfigurationError):
            resolve_jwt_secret(environment, "   ")


@pytest.mark.nfr04
def test_short_and_placeholder_secrets_are_rejected():
    with pytest.raises(ConfigurationError):
        resolve_jwt_secret("development", "too-short")
    with pytest.raises(ConfigurationError):
        resolve_jwt_secret("development", "marketscope-local-development-secret-change-me")
    with pytest.raises(ConfigurationError):
        resolve_jwt_secret("development", "change-this-local-secret-before-sharing-the-repository")


@pytest.mark.nfr04
def test_strong_secret_is_accepted_and_test_secret_is_test_only():
    strong = "k3Jv9-Qm2x_Zt7LpR4yWc8NbHs5UdEa1GfTq0OiXvM"
    assert resolve_jwt_secret("production", strong) == strong
    assert resolve_jwt_secret("test", None)  # built-in test secret exists...
    with pytest.raises(ConfigurationError):  # ...but only for ENVIRONMENT=test
        resolve_jwt_secret("development", None)


@pytest.mark.nfr04
def test_token_forged_with_the_old_repository_secret_is_rejected(client):
    forged = jwt.encode(
        {"sub": "any-admin-id", "role": "ADMIN"},
        "marketscope-local-development-secret-change-me",
        algorithm="HS256",
    )
    response = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
