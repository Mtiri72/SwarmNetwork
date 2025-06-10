import logging
import json


class JSONLogFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "filename": record.filename,
            "line": record.lineno,
            "message": record.getMessage(),
            "uuid": record.name,       # e.g. AP000002
            "type": "AP"
        }
        return json.dumps(log_entry)