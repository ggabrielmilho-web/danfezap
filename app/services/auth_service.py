"""
Serviço de autenticação JWT do painel.

- gerar_jwt(usuario_id, tipo, master_id) → token HS256 com TTL JWT_TTL_HORAS
- validar_jwt(token) → payload ou HTTPException 401
- usuario_logado: dependency FastAPI pra endpoints protegidos
"""
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import config
from ..database import get_db
from ..models import Usuario

logger = logging.getLogger(__name__)


class AuthService:
    def gerar_jwt(self, usuario_id: int, tipo: str, master_id: Optional[int]) -> str:
        agora = datetime.utcnow()
        payload = {
            "usuario_id": usuario_id,
            "tipo": tipo,
            "master_id": master_id,
            "iat": agora,
            "exp": agora + timedelta(hours=config.JWT_TTL_HORAS),
        }
        return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")

    def validar_jwt(self, token: str) -> dict:
        try:
            return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expirado")
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT inválido: {e}")
            raise HTTPException(status_code=401, detail="Token inválido")


auth_service = AuthService()


def usuario_logado(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Dependency injection: extrai JWT do header Authorization,
    valida e retorna o Usuario correspondente.

    Uso nas Fases 2+:
        @router.get("/algo")
        def algo(usuario: Usuario = Depends(usuario_logado)):
            ...
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header Authorization Bearer ausente")

    token = authorization.split(" ", 1)[1].strip()
    payload = auth_service.validar_jwt(token)

    usuario = db.query(Usuario).get(payload["usuario_id"])
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário inválido ou inativo")

    return usuario
