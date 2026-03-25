"""Estado do ciclo de vida de um email no sistema (persistência + domínio)."""


class EmailRecordStatus:
    PENDING = "pending"
    CLASSIFIED = "classified"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


# Alias semântico legado (controllers e ORM historicamente usam "EmailStatus")
EmailStatus = EmailRecordStatus
