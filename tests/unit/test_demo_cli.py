from backend.app.cli.demo import format_demo_result, main


def test_format_demo_result_is_readable():
    assert format_demo_result(
        "CD-1002",
        "WAITING ON APPROVAL",
        "approval_id=approval-1",
    ) == "CD-1002: WAITING ON APPROVAL — approval_id=approval-1"


def test_demo_cli_accepts_supported_ticket_arguments():
    assert main(["--ticket", "CD-1002"]) in (0, 1)


def test_demo_cli_rejects_unknown_ticket_arguments():
    import pytest

    with pytest.raises(SystemExit):
        main(["--ticket", "CD-9999"])
