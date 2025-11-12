import logging
import os
from logging.handlers import RotatingFileHandler
import sys
from datetime import datetime  # <-- 1. Importar datetime

def setup_logging():
    """
    Configura el sistema de logging para la aplicación.
    Crea manejadores de archivo (info y error) y un manejador de consola.
    """
    
    # --- INICIO DE CAMBIOS ---
    
    # 2. Definir el directorio base y el directorio de hoy
    base_log_directory = "logs"
    today_str = datetime.now().strftime("%Y-%m-%d")
    log_directory = os.path.join(base_log_directory, today_str) # Ej: logs/2025-11-12

    # 3. Crear el directorio base y el diario si no existen
    if not os.path.exists(log_directory):
        os.makedirs(log_directory, exist_ok=True) # exist_ok=True evita errores si se crea entre el 'if' y el 'makedirs'
        
    # --- FIN DE CAMBIOS ---


    # 4. Crear el formateador
    log_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 5. Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) 

    # --- Manejador de Consola (StreamHandler) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO) 
    console_handler.setFormatter(log_formatter)

    # --- Manejador para todos los logs (app.log) ---
    info_handler = RotatingFileHandler(
        # 6. Usar el nuevo 'log_directory'
        os.path.join(log_directory, "app.log"),
        maxBytes=1024 * 1024 * 5,  # 5 MB
        backupCount=2,
        encoding="utf-8",
    )
    info_handler.setLevel(logging.INFO) 
    info_handler.setFormatter(log_formatter)

    # --- Manejador exclusivo para errores (error.log) ---
    error_handler = RotatingFileHandler(
        # 7. Usar el nuevo 'log_directory'
        os.path.join(log_directory, "error.log"),
        maxBytes=1024 * 1024 * 2,  # 2 MB
        backupCount=2,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR) 
    error_handler.setFormatter(log_formatter)

    # 8. Añadir los manejadores al logger raíz
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(info_handler)
        root_logger.addHandler(error_handler)
        
    logging.info("Sistema de logging configurado correctamente.")