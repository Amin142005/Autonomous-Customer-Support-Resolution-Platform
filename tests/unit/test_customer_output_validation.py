from backend.app.core.guardrails import validate_customer_output


def test_safe_customer_reply_passes_validation():
    is_valid, violations = validate_customer_output(
        "Please follow the MFA recovery steps and contact support if it continues.",
    )

    assert is_valid
    assert violations == []


def test_empty_customer_reply_is_rejected():
    is_valid, violations = validate_customer_output("   ")

    assert not is_valid
    assert violations == ["empty_output"]


def test_internal_urls_are_rejected():
    for text in (
        "See http://127.0.0.1:8000/api/v1/tickets",
        "The backend service is at http://backend:8000/health",
        "Open https://database.internal/support",
        "Use redis://:password@redis.internal:6379",
        "View kb://internal-article#section",
    ):
        is_valid, violations = validate_customer_output(text)
        assert not is_valid
        assert "internal_url" in violations


def test_secrets_and_card_numbers_are_rejected():
    for text in (
        "Your API key: sk-live-123",
        "Authorization: Bearer bearer-secret",
        "Token=eyJhbGciOiJIUzI1NiJ9.payload.signature",
        "The stored card is 4111-1111-1111-1111",
    ):
        is_valid, violations = validate_customer_output(text)
        assert not is_valid
        assert "secret" in violations


def test_other_customer_id_is_rejected():
    is_valid, violations = validate_customer_output(
        "This result belongs to customer-999.",
        other_customer_ids=("customer-999",),
    )

    assert not is_valid
    assert violations == ["other_customer_data"]


def test_other_customer_name_is_rejected():
    is_valid, violations = validate_customer_output(
        "The other customer is Avery Morgan.",
        other_customer_names=("Avery Morgan",),
    )

    assert not is_valid
    assert violations == ["other_customer_data"]


def test_public_support_url_is_allowed():
    is_valid, violations = validate_customer_output(
        "See https://support.clouddesk.example/articles/mfa-recovery",
    )

    assert is_valid
    assert violations == []


def test_allowed_customer_context_does_not_create_false_match():
    is_valid, violations = validate_customer_output(
        "This update applies to Avery Morgan.",
        allowed_customer_name="Avery Morgan",
        allowed_customer_id="customer-123",
    )

    assert is_valid
    assert violations == []
