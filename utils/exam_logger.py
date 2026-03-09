"""
Logger operacional para el sistema de exámenes.
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
from zoneinfo import ZoneInfo


class ExamLogger:
    """Logger simple con salida a archivo rotativo para auditoría operativa."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        logs_dir = self.base_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("examenes.operacion")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            handler = RotatingFileHandler(
                logs_dir / "operacion.log",
                maxBytes=1_500_000,
                backupCount=5,
                encoding="utf-8"
            )
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self.logger.addHandler(handler)

    def evento(
        self,
        tipo: str,
        mensaje: str,
        codigo_estudiante: str = "",
        examen_id: str = "",
        extra: Dict[str, Any] | None = None
    ) -> None:
        payload = {
            "ts": datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": tipo,
            "codigo_estudiante": codigo_estudiante,
            "examen_id": examen_id,
            "mensaje": mensaje,
            "extra": extra or {}
        }
        self.logger.info(json.dumps(payload, ensure_ascii=False))
