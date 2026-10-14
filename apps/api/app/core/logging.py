import logging

# Never log farmer descriptions, coordinates, location labels or image bytes.
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT)
