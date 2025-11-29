import logging 


def get_logger(name="hft"):
    # Instantiate the logger class
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    fmt = "%(asctime)s | %(levelname)s | %(message)s"
    handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(handler)
    return logger

# Store logs in a file (optional)
# handler = logging.FileHander("hft.log")