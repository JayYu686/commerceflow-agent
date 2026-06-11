from app.services.errors import ConflictError, NotFoundError


def test_custom_api_errors_allow_traceback_assignment() -> None:
    errors = [
        ConflictError(code="conflict", message="conflict"),
        NotFoundError(resource="thing", identifier="missing"),
    ]

    for error in errors:
        error.__traceback__ = None
