"""Agente local de escaneo para el formulario de fichas del Instituto.

Expone solamente en 127.0.0.1 y usa NAPS2.Console para acceder al controlador
WIA/TWAIN del Epson ES-60W. No almacena documentos: el PDF temporal se elimina
después de enviarlo al navegador.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import urlsplit


HOST = "127.0.0.1"
PORT = 17654
MAX_REQUEST_BYTES = 4096
SCAN_LOCK = threading.Lock()


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = application_directory()
CONFIG_PATH = BASE_DIR / "scanner-agent.json"
LOG_PATH = BASE_DIR / "scanner-agent.log"


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("instituto_scanner")
    logger.setLevel(logging.INFO)
    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    if sys.stderr is not None:
        logger.addHandler(logging.StreamHandler())
    return logger


LOGGER = configure_logging()


def load_config() -> dict:
    defaults = {
        "allowed_origins": ["http://localhost:8000", "http://127.0.0.1:8000"],
        "naps2_console": "",
        "profile": "Instituto ES-60W",
        "page_delay_ms": 10000,
        "scan_timeout_seconds": 300,
        "max_pages": 20,
    }
    if not CONFIG_PATH.exists():
        return defaults
    with CONFIG_PATH.open("r", encoding="utf-8-sig") as config_file:
        configured = json.load(config_file)
    if not isinstance(configured, dict):
        raise ValueError("scanner-agent.json debe contener un objeto JSON")
    defaults.update(configured)
    return defaults


CONFIG = load_config()


def naps2_candidates() -> list[Path]:
    configured = str(CONFIG.get("naps2_console") or "").strip()
    candidates = [Path(configured)] if configured else []
    for env_name in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(env_name)
        if not root:
            continue
        root_path = Path(root)
        candidates.extend(
            [
                root_path / "NAPS2" / "NAPS2.Console.exe",
                root_path / "Programs" / "NAPS2" / "NAPS2.Console.exe",
            ]
        )
    return candidates


def find_naps2() -> Path | None:
    return next((candidate for candidate in naps2_candidates() if candidate.is_file()), None)


def origin_allowed(origin: str | None) -> bool:
    if not origin:
        return True
    allowed = {str(item).rstrip("/") for item in CONFIG.get("allowed_origins", [])}
    return origin.rstrip("/") in allowed


class ScannerHandler(BaseHTTPRequestHandler):
    server_version = "InstitutoScanner/1.0"

    def log_message(self, message: str, *args) -> None:
        LOGGER.info("%s %s", self.address_string(), message % args)

    @property
    def request_origin(self) -> str | None:
        return self.headers.get("Origin")

    def add_cors_headers(self) -> None:
        origin = self.request_origin
        if origin and origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Expose-Headers", "X-Scan-Filename")

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.add_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reject_origin(self) -> bool:
        if origin_allowed(self.request_origin):
            return False
        self.send_json(HTTPStatus.FORBIDDEN, {"error": "Este sitio no está autorizado en scanner-agent.json."})
        return True

    def do_OPTIONS(self) -> None:
        if self.reject_origin():
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.add_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_GET(self) -> None:
        if self.reject_origin():
            return
        if urlsplit(self.path).path != "/health":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})
            return
        naps2 = find_naps2()
        self.send_json(
            HTTPStatus.OK,
            {
                "status": "ready" if naps2 else "configuration_required",
                "naps2_found": bool(naps2),
                "profile": CONFIG.get("profile", ""),
            },
        )

    def do_POST(self) -> None:
        if self.reject_origin():
            return
        if urlsplit(self.path).path != "/scan":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Ruta no encontrada."})
            return
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        if content_length < 1 or content_length > MAX_REQUEST_BYTES:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Solicitud de escaneo no válida."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
            pages = int(payload.get("pages", 1))
        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "El número de páginas no es válido."})
            return

        max_pages = int(CONFIG.get("max_pages", 20))
        if pages < 1 or pages > max_pages:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": f"Indica entre 1 y {max_pages} páginas."})
            return
        if not SCAN_LOCK.acquire(blocking=False):
            self.send_json(HTTPStatus.CONFLICT, {"error": "Ya hay un escaneo en curso."})
            return
        try:
            self.perform_scan(pages)
        finally:
            SCAN_LOCK.release()

    def perform_scan(self, pages: int) -> None:
        naps2 = find_naps2()
        if not naps2:
            self.send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "No se encontró NAPS2.Console. Instala NAPS2 o configura su ruta en scanner-agent.json."},
            )
            return

        with tempfile.TemporaryDirectory(prefix="instituto-scan-") as temp_dir:
            output_path = Path(temp_dir) / "ficha-firmada.pdf"
            command = [str(naps2), "-o", str(output_path), "-f", "--progress", "-n", str(pages)]
            profile = str(CONFIG.get("profile") or "").strip()
            if profile:
                command.extend(["-p", profile])
            if pages > 1:
                command.extend(["-d", str(int(CONFIG.get("page_delay_ms", 10000)))])
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=int(CONFIG.get("scan_timeout_seconds", 300)),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    check=False,
                )
            except subprocess.TimeoutExpired:
                self.send_json(HTTPStatus.GATEWAY_TIMEOUT, {"error": "El escaneo superó el tiempo permitido."})
                return
            except OSError as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"No se pudo iniciar NAPS2: {error}"})
                return

            if result.returncode != 0 or not output_path.is_file():
                details = (result.stderr or result.stdout or "").strip().splitlines()
                suffix = f" Detalle: {details[-1][:300]}" if details else ""
                self.send_json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {"error": "No se completó el escaneo. Revisa que el Epson esté encendido y conectado." + suffix},
                )
                return

            pdf = output_path.read_bytes()
            if not pdf.startswith(b"%PDF-"):
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "NAPS2 no generó un PDF válido."})
                return
            filename = f"ficha-firmada-{datetime.now():%Y%m%d-%H%M%S}.pdf"
            self.send_response(HTTPStatus.OK)
            self.add_cors_headers()
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("X-Scan-Filename", filename)
            self.send_header("Content-Length", str(len(pdf)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(pdf)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ScannerHandler)
    LOGGER.info("Agente de escaneo activo en http://%s:%s", HOST, PORT)
    LOGGER.info("Configuración: %s", CONFIG_PATH)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
