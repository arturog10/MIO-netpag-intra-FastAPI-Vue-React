import logging
import os
from logging.handlers import RotatingFileHandler
import sys # Necesario para el StreamHandler

def setup_logging():
    """
    Configura el sistema de logging para la aplicación.
    Crea manejadores de archivo (info y error) y un manejador de consola.
    """
    # 1. Definir el directorio de logs
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    # 2. Crear el formateador
    log_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 3. Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) # Captura todo desde INFO

    # --- Manejador de Consola (StreamHandler) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) # Muestra INFO y superior en consola
    console_handler.setFormatter(log_formatter)

    # --- Manejador para todos los logs (app.log) ---
    info_handler = RotatingFileHandler(
        os.path.join(log_directory, "app.log"),
        maxBytes=1024 * 1024 * 5,  # 5 MB
        backupCount=2,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO) # Escribe INFO y superior en app.log
    info_handler.setFormatter(log_formatter)

    # --- Manejador exclusivo para errores (error.log) ---
    error_handler = RotatingFileHandler(
        os.path.join(log_directory, "error.log"),
        maxBytes=1024 * 1024 * 2,  # 2 MB
        backupCount=2,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR) # Escribe SÓLO ERROR y superior
    error_handler.setFormatter(log_formatter)

    # 4. Añadir los manejadores al logger raíz
    # Evitar duplicados
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(info_handler)
        root_logger.addHandler(error_handler)
        
    # Mensaje inicial (se escribirá en los 3 manejadores)
    logging.info("Sistema de logging configurado correctamente.")