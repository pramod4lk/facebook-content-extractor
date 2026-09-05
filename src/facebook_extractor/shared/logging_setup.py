import logging


def configure_logging(level: str, *, verbose: bool = False) -> None:
    """Configure the standard logging module (SPEC.md §11 Logging). --verbose forces DEBUG
    regardless of LOG_LEVEL. Never call this with anything that includes a secret value."""
    effective_level = "DEBUG" if verbose else level.upper()
    logging.basicConfig(
        level=effective_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
