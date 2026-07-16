from dataclasses import dataclass, field
from enum import StrEnum

from bot_atul.db.repositories import Repository, Ticket


class IntakeStep(StrEnum):
    TITLE = "title"
    SERVICE = "service"
    URGENCY = "urgency"
    DESCRIPTION = "description"
    ATTACHMENTS = "attachments"
    REVIEW = "review"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class Attachment:
    kind: str
    file_id: str
    file_name: str | None
    caption: str | None


@dataclass
class IntakeSession:
    reporter_id: int
    services: tuple[str, ...]
    step: IntakeStep = IntakeStep.TITLE
    title: str = ""
    service: str = ""
    urgency: str = ""
    description_parts: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    _ticket: Ticket | None = field(default=None, init=False, repr=False)

    @property
    def description(self) -> str:
        return "\n".join(self.description_parts)

    def answer(self, value: str) -> None:
        value = value.strip()
        if self.step is IntakeStep.TITLE:
            if not value:
                raise ValueError("The title is required.")
            self.title = value
            self.step = IntakeStep.SERVICE
        elif self.step is IntakeStep.SERVICE:
            if value not in self.services:
                raise ValueError("Choose an available service.")
            self.service = value
            self.step = IntakeStep.URGENCY
        elif self.step is IntakeStep.URGENCY:
            if value not in {"Low", "Normal", "High", "Critical"}:
                raise ValueError("Choose a valid urgency.")
            self.urgency = value
            self.step = IntakeStep.DESCRIPTION
        elif self.step is IntakeStep.DESCRIPTION:
            if not value:
                raise ValueError("Description messages cannot be blank.")
            self.description_parts.append(value)
        else:
            raise ValueError(f"Text is not accepted during {self.step}.")

    def complete_description(self) -> None:
        if self.step is not IntakeStep.DESCRIPTION or not self.description_parts:
            raise ValueError("At least one description message is required.")
        self.step = IntakeStep.ATTACHMENTS

    def add_attachment(
        self,
        kind: str,
        file_id: str,
        file_name: str | None,
        caption: str | None,
    ) -> None:
        if self.step is not IntakeStep.ATTACHMENTS:
            raise ValueError("Attachments are not accepted now.")
        self.attachments.append(Attachment(kind, file_id, file_name, caption))

    def finish_attachments(self) -> None:
        if self.step is not IntakeStep.ATTACHMENTS:
            raise ValueError("The intake is not collecting attachments.")
        self.step = IntakeStep.REVIEW

    def summary(self) -> str:
        return (
            f"Title: {self.title}\nService: {self.service}\n"
            f"Urgency: {self.urgency}\nDescription:\n{self.description}"
        )

    def confirm(self, repository: Repository) -> Ticket:
        if self.step is not IntakeStep.REVIEW:
            raise ValueError("The intake is not ready for confirmation.")
        if self._ticket is None:
            ticket = repository.create_ticket(
                reporter_id=self.reporter_id,
                service_name=self.service,
                urgency=self.urgency,
                title=self.title,
                description=self.description,
                attachments=tuple(
                    (item.kind, item.file_id, item.file_name, item.caption)
                    for item in self.attachments
                ),
            )
            # Report only: auto-assign to the submitter so the group never needs
            # an "Assign to Me" step.
            self._ticket = repository.assign_ticket(
                ticket.number, self.reporter_id, self.reporter_id
            )
        return self._ticket

    def complete(self) -> None:
        if self.step is not IntakeStep.REVIEW or self._ticket is None:
            raise ValueError("The intake is not ready for completion.")
        self.step = IntakeStep.COMPLETE

    def cancel(self) -> None:
        self.step = IntakeStep.CANCELLED
