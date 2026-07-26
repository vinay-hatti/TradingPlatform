class PublishedStateError(RuntimeError):
    """Base error for published-state resolution."""

    def __init__(self, message: str, *, codes: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.codes = tuple(codes)


class PublishedStateUnavailableError(PublishedStateError):
    pass


class PublishedStateStaleError(PublishedStateError):
    pass


class PublishedStateNotReadyError(PublishedStateError):
    pass
