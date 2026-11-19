from backend.app.core.guardrails import SECRET_PATTERNS, scrub


def test_scrub_redacts_password_and_api_key_assignments():
    scrubbed = scrub(
        "Password=pass-secret API_KEY: api-secret "
        "authorization=Bearer auth-secret",
    )

    assert "[REDACTED]" in scrubbed
    assert "pass-secret" not in scrubbed
    assert "api-secret" not in scrubbed
    assert "auth-secret" not in scrubbed


def test_scrub_redacts_bearer_tokens_and_jwt_tokens():
    scrubbed = scrub(
        "Authorization Bearer abc123 "
        "JWT eyJhbGciOiJIUzI1NiJ9.payload.signature",
    )

    assert "abc123" not in scrubbed
    assert "eyJ" not in scrubbed
    assert scrubbed.count("[REDACTED]") >= 2


def test_scrub_redacts_url_credentials_and_sensitive_query_values():
    scrubbed = scrub(
        "postgresql://user:db-secret@db.example/support"
        "?api_key=query-secret&view=summary",
    )

    assert "db-secret" not in scrubbed
    assert "query-secret" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_scrub_redacts_card_numbers():
    scrubbed = scrub(
        "Card 4111 1111 1111 1111 or 378282246310005.",
    )

    assert "4111" not in scrubbed
    assert "378282246310005" not in scrubbed
    assert scrubbed.count("[REDACTED]") == 2


def test_scrub_redacts_aws_keys_and_private_key_blocks():
    scrubbed = scrub(
        "AWS_KEY=AKIAIOSFODNN7EXAMPLE "
        "-----BEGIN PRIVATE KEY-----"
        "private-key-data"
        "-----END PRIVATE KEY-----",
    )

    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "private-key-data" not in scrubbed
    assert "[REDACTED]" in scrubbed


def test_secret_patterns_is_available_for_future_memory_service():
    assert len(SECRET_PATTERNS) >= 7


def test_scrub_leaves_safe_text_unchanged():
    text = "The customer needs to finish MFA setup."

    assert scrub(text) == text
