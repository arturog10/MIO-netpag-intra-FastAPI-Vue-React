# Intranet de Gestión de Datos (NUEVA-INTRA)

Este proyecto es una aplicación web interna (Intranet) diseñada para la gestión y visualización de datos operativos. Está construida con un stack moderno, separando el backend (API) del frontend (interfaz de usuario).

- **Backend:** API robusta escrita en Python usando **FastAPI**.
- **Frontend:** Interfaz de usuario interactiva construida con **React + Vite**.

---

## 🚀 Tecnologías Utilizadas

### Backend (Python)

- **Framework:** FastAPI
- **Base de Datos:** SQL Server (conectado vía `PYODBC` y `SQLAlchemy`)
- **Autenticación:** Tokens JWT (manejados con `Passlib[bcrypt]` y `python-jose`)
- **Exportación:** `Pandas` y `openpyxl` para generar reportes en Excel.
- **Servidor:** `uvicorn`

### Frontend (JavaScript/React)

- **Framework:** React 19
- **Bundler:** Vite (con Rolldown)
- **UI Kit:** PrimeReact (principalmente `DataTable`, `Paginator`, `Dialog`, `MultiSelect`)
- **Estilos:** Tailwind CSS
- **Routing:** React Router DOM
- **HTTP Client:** Axios
- **Token Handling:** `jwt-decode`

---

## ✨ Características Principales

- **Autenticación Segura:** Sistema de login basado en Tokens JWT. Las rutas del backend están protegidas y el frontend maneja el estado de autenticación mediante Contexto.
- **Visor de Datos Dinámico:** Grilla de datos `server-side` que permite:
  - Conexión a múltiples tablas de clientes (definidas en `config.json`).
  - Paginación.
  - Ordenamiento por columna.
  - Selección y reordenamiento de columnas (Drag & Drop).
- **Filtros Avanzados:** Panel de filtros dinámico que soporta múltiples operadores (contiene, es igual, entre, etc.) y campos de calendario para fechas.
- **Gestión de Estrategias:** Los usuarios pueden guardar sus configuraciones de filtros, columnas (visibilidad y orden) y ordenamiento en la base de datos para cargarlas más tarde.
- **Exportación de Datos:** Permite exportar la vista filtrada actual a `.xlsx` (Excel) o `.csv`.
- **Panel de Administración:** Una ruta protegida (`/admin`) que permite a los administradores crear nuevos usuarios, cambiar roles y activar/desactivar cuentas.
- **Módulos Adicionales:** Vistas dedicadas para `Trazabilidad` y `Lista Negra`, con funcionalidad de tareas asíncronas para consultas largas.
- **Auditoría Completa:** Todas las acciones críticas (login, guardar/cargar estrategia, exportar, crear usuario) se registran en la tabla `AuditoriaUsuarios`.

---

## 🏗️ Estructura del Proyecto

El repositorio es un monorepo simple con dos carpetas principales:

NUEVA-INTRA/ 
│ ├── 📁 backend/ # La API de FastAPI (Python) 
│ ├── 📁 app/ 
│ │ ├── 📁 routers/ # Endpoints (data_visor.py, auth_router.py, etc.) 
│ │ ├── init.py 
│ │ ├── auth_security.py # Lógica de JWT y hashing 
│ │ ├── config.py # Carga de .env y motores de DB 
│ │ ├── database.py # Gestor de sesiones (get_db_session) 
│ │ ├── db_operations.py # Lógica SQL para Visor y Estrategias 
│ │ ├── db_user_operations.py # Lógica SQL para Usuarios y Auditoría 
│ │ ├── main.py # Archivo principal de FastAPI 
│ │ └── models.py # Modelos Pydantic 
│ ├── 📁 venv/ # Entorno virtual (ignorado por Git) 
│ ├── .env # Archivo de secretos (ignorado por Git) 
│ ├── config.json # Mapeo de tablas y DBs 
│ ├── create_admin.py # Script para crear el primer admin 
│ └── requirements.txt # (Deberías generarlo) 
│ ├── 📁 frontend/ # La aplicación de React 
│ ├── 📁 src/ 
│ │ ├── 📁 components/ # Componentes reutilizables (Visor.jsx, Navbar.jsx) 
│ │ ├── 📁 context/ # (AuthContext.jsx) 
│ │ ├── 📁 pages/ # Vistas (HomePage.jsx, VisorPage.jsx, LoginPage.jsx) 
│ │ ├── 📁 styles/ # (appStyles.js) 
│ │ ├── App.jsx # Router principal 
│ │ ├── index.css # Configuración de Tailwind 
│ │ └── main.jsx # Punto de entrada de React 
│ ├── .gitignore 
│ ├── index.html 
│ ├── package.json 
│ └── tailwind.config.js 
│ ├── .gitignore # .gitignore principal del repo 
└── README.md # Este archivo

🛠️ Configuración y Ejecución
Prerrequisitos
Node.js (v18+ recomendado)

Python (v3.10+ recomendado)

Un servidor SQL Server accesible.

1. Configuración del Backend
   Navegar a la carpeta:

Bash

cd backend
Crear entorno virtual:

Bash

python -m venv venv
Activar entorno virtual:

Windows: .\venv\Scripts\activate

Mac/Linux: source venv/bin/activate

Instalar dependencias:

(Recomendado) Crea un archivo requirements.txt con el siguiente contenido:

Plaintext

fastapi
uvicorn[standard]
sqlalchemy
pyodbc
passlib[bcrypt]
python-jose[cryptography]
pandas
openpyxl
python-dotenv
Luego, instala:

Bash

pip install -r requirements.txt
Configurar Secretos (.env):

Crea un archivo .env en la carpeta backend/.

Añade tus credenciales de base de datos y una clave secreta para JWT.

Ejemplo de .env (úsalo como plantilla):

Ini, TOML

# --- CONFIGURACIÓN DE CONEXIÓN (Clave 1) ---

DB_KEY_1=b2c
DB_DIALECT_1=mssql
DB_NAME_1=B2C

# --- CONFIGURACIÓN DE CONEXIÓN (Clave 2) ---

DB_KEY_2=b2c_oper
DB_DIALECT_2=mssql
DB_NAME_2=B2C_OPER

# --- CREDENCIALES (PARA AMBAS) ---

DB_SERVER=TU_SERVIDOR_SQL
SQL_USERNAME=TU_USUARIO
SQL_PASSWORD=TU_CONTRASENA

# --- JWT (AUTENTICACIÓN) ---

# ¡Genera una clave segura! (ej. python -c 'import secrets; print(secrets.token_hex(32))')

SECRET_KEY=tu_clave_secreta_muy_larga_y_aleatoria
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
Configurar Tablas (config.json):

# Las siguientes tablas son esenciales para que la aplicacion funcione correctamente.

CREATE TABLE Usuarios (
    id_usuario INT IDENTITY(1,1) PRIMARY KEY,
    nombre_usuario NVARCHAR(255),
    hash_password NVARCHAR(255),
    email NVARCHAR(255),
    nombre_completo NVARCHAR(255),
    rol NVARCHAR(50),
    activo INT,
    -- Campos Adicionales Solicitados
    fecha_creacion DATETIME DEFAULT GETDATE(),
    fecha_modificacion DATETIME
);

CREATE TABLE AuditoriaUsuarios (
    id INT IDENTITY(1,1) PRIMARY KEY, 
    nombre_usuario NVARCHAR(255),
    accion NVARCHAR(255),
    detalles_json NVARCHAR(MAX),
    -- Campos Adicionales Solicitados
    fecha_creacion DATETIME DEFAULT GETDATE(), -- Equivale a la fecha del evento
    fecha_modificacion DATETIME -- No suele usarse en auditoría (logs inmutables), pero se agrega por solicitud
);

CREATE TABLE Estrategias (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nombre_estrategia NVARCHAR(255),
    codigo_cliente NVARCHAR(50),
    columnas_visibles NVARCHAR(MAX),
    filtro_columnas NVARCHAR(MAX),
    filtros_aplicados NVARCHAR(MAX),
    orden_estado NVARCHAR(MAX),
    usuario_creador NVARCHAR(255),
    id_usuario_creador INT,
    fecha_creacion DATETIME DEFAULT GETDATE(), -- Ya existía en código, se refuerza el default
    activa INT,
    es_publica INT,
    -- Campos Adicionales Solicitados
    fecha_modificacion DATETIME
);

CREATE TABLE PlantillasCampanas (
    id INT IDENTITY(1,1) PRIMARY KEY,
    nombre_plantilla NVARCHAR(255),
    id_estrategia_base INT,
    reglas_validacion_json NVARCHAR(MAX),
    reglas_procesamiento_json NVARCHAR(MAX),
    modo_salida NVARCHAR(50),
    estado INT,
    usuario_creador NVARCHAR(255),
    id_usuario_creador INT,
    fecha_creacion DATETIME DEFAULT GETDATE(), -- Ya existía en código
    usuario_modificacion NVARCHAR(255), -- Ya existía en código
    id_usuario_modificacion INT, -- Ya existía en código
    fecha_modificacion DATETIME -- Ya existía en código
);

Asegúrate de que tu archivo config.json en backend/ esté actualizado con los mapeos correctos para cliente_table_map, tabla_estrategias, tabla_usuarios, etc.

Crear Primer Usuario Administrador:

Asegúrate de que tu venv esté activado.

Ejecuta el script create_admin.py y sigue las instrucciones:

Bash

python create_admin.py
Ejecutar el Backend:

Bash

uvicorn app.main:app --reload --port 8000
Tu API estará disponible en http://localhost:8000.

2. Configuración del Frontend
   Navegar a la carpeta:

Bash

cd frontend
Instalar dependencias:

Bash

npm install
Ejecutar el Frontend:

Bash

npm run dev
Abrir la Aplicación:

Abre tu navegador y ve a la dirección que te indica Vite (usualmente http://localhost:5173).

Serás redirigido a la página de login. Ingresa con el usuario administrador que creaste.
