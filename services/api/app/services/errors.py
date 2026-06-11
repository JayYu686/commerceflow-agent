from dataclasses import dataclass


@dataclass
class NotFoundError(Exception):
    resource: str
    identifier: str

    @property
    def message(self) -> str:
        return f"{self.resource} not found"


@dataclass
class ConflictError(Exception):
    code: str
    message: str
    existing_identifier: str | None = None
