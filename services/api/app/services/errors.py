from dataclasses import dataclass


@dataclass(frozen=True)
class NotFoundError(Exception):
    resource: str
    identifier: str

    @property
    def message(self) -> str:
        return f"{self.resource} not found"
