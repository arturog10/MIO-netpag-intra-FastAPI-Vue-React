import logging
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.config import config
from app.models import TokenData 

log = logging.getLogger(__name__)

# --- Configuración de JWT ---
SECRET_KEY = config.get("secret_key")
ALGORITHM = config.get("algorithm", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = config.get("access_token_expire_minutes", 60)

if not SECRET_KEY:
    log.warning("¡ADVERTENCIA DE SEGURIDAD! 'SECRET_KEY' no está definida en .env. Usando clave por defecto.")
    SECRET_KEY = "clave_secreta_por_defecto_NO_USAR_EN_PRODUCCION"

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# --- Funciones de Hashing (usando bcrypt directamente) ---

def _truncate_password_for_bcrypt(password: str) -> bytes:
    """Trunca una contraseña a 72 bytes para bcrypt."""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        log.warning(f"Contraseña truncada de {len(password_bytes)} bytes a 72 bytes")
        return password_bytes[:72]
    return password_bytes

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña plana contra un hash."""
    try:
        password_bytes = _truncate_password_for_bcrypt(plain_password)
        # bcrypt.checkpw espera bytes en ambos argumentos
        hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        log.error(f"Error al verificar contraseña: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Crea un hash de una contraseña plana."""
    try:
        password_bytes = _truncate_password_for_bcrypt(password)
        # bcrypt.gensalt() genera un salt aleatorio
        # bcrypt.hashpw() crea el hash
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Devolver como string para almacenar en BD
        return hashed.decode('utf-8')
    except Exception as e:
        log.error(f"Error al hashear contraseña: {e}")
        raise


# --- Funciones de Token JWT ---

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Crea un nuevo token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES))
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict | None:
    """Decodifica un token y devuelve el 'payload' (datos) si es válido."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        log.warning(f"Error al decodificar JWT: {e}")
        return None

# --- Dependencia de Autenticación ---

async def get_current_user_email(token: str = Depends(oauth2_scheme)) -> str:
    # ... (tu código existente está bien, pero usemos el nuevo TokenData)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    # Opcional: Validar el token data con Pydantic
    # try:
    #     token_data = TokenData(email=payload.get("sub"), rol=payload.get("rol"))
    # except ValidationError:
    #     raise credentials_exception
        
    return email # Tu función original devuelve solo el email

def decode_token(token: str) -> dict | None:
    """Decodifica un token y devuelve el 'payload' (datos) si es válido."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        log.warning(f"Error al decodificar JWT: {e}")
        return None
    
async def get_current_admin_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependencia que verifica el token y asegura que el rol es 'admin'.
    Devuelve el email del admin si es exitoso.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    admin_forbidden_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tiene permisos de administrador",
    )
    
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    rol: str = payload.get("rol")
    
    if email is None or rol is None:
        raise credentials_exception
        
    if rol != "admin":
        raise admin_forbidden_exception
        
    return email    