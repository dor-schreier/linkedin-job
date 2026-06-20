import logging
import logging.config
import os
from datetime import datetime
from pathlib import Path


def configure_logging(log_dir: str = "logs") -> Path:
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    session_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_path / f"app-{session_ts}.log"

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    uvicorn_level = os.getenv("LOG_LEVEL_UVICORN", "WARNING").upper()

    fmt = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": fmt},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "standard",
            },
            "file": {
                "class": "logging.FileHandler",
                "filename": str(log_file),
                "encoding": "utf-8",
                "formatter": "standard",
            },
        },
        "loggers": {
            "app.scraper": {"level": level},
            "app.scrapers": {"level": level},
            "app.services.llm_service": {"level": level},
            "app.services.scheduler": {"level": level},
            "app.services": {"level": level},
            "app.routes": {"level": level},
            "app.repository": {"level": level},
            "app.database": {"level": level},
            "uvicorn": {"level": uvicorn_level},
            "uvicorn.access": {"level": uvicorn_level},
            "apscheduler": {"level": uvicorn_level},
            # httpx logs every request at INFO ("HTTP Request: GET ... 403");
            # noisy during cleanup URL checks, so keep it at WARNING.
            "httpx": {"level": uvicorn_level},
        },
        "root": {
            "level": level,
            "handlers": ["console", "file"],
        },
    })

    return log_file
