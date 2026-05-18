"""
Endpoints de autenticação por OTP via WhatsApp.

POST /api/auth/otp/solicitar  body {telefone}            → dispara OTP no Zap
POST /api/auth/otp/validar    body {telefone, codigo}    → retorna JWT
"""
import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Usuario
from ..services.otp_service import otp_service
from ..services.auth_service import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Aceita qualquer combinação de dígitos/máscara — valida pela contagem de dígitos.
# Celular BR: 10 (sem 9 extra) ou 11 (com 9 extra) dígitos após DDD. Com DDI: 12 ou 13.


class OtpSolicitarBody(BaseModel):
    telefone: str

    @field_validator("telefone")
    @classmethod
    def _valida_telefone(cls, v: str) -> str:
        v = (v or "").strip()
        digitos = re.sub(r"\D", "", v)
        # Aceita: 10 ou 11 dígitos (sem DDI); 12 ou 13 (com DDI 55)
        if len(digitos) not in (10, 11, 12, 13):
            raise ValueError("telefone inválido — use DDD + número (ex: (11) 99999-9999)")
        return v


class OtpValidarBody(BaseModel):
    telefone: str
    codigo: str

    @field_validator("codigo")
    @classmethod
    def _valida_codigo(cls, v: str) -> str:
        v = (v or "").strip()
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("código deve ter exatamente 6 dígitos")
        return v


@router.post("/otp/solicitar")
async def solicitar(body: OtpSolicitarBody, db: Session = Depends(get_db)):
    resultado = await otp_service.gerar_otp(body.telefone, db)
    if not resultado["sucesso"]:
        if resultado["erro"] == "limite_excedido":
            raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 10 minutos.")
        raise HTTPException(status_code=502, detail="Falha ao enviar OTP. Tente novamente.")
    return {"enviado": True}


@router.post("/otp/validar")
def validar(body: OtpValidarBody, db: Session = Depends(get_db)):
    resultado = otp_service.validar_otp(body.telefone, body.codigo, db)
    if not resultado["valido"]:
        raise HTTPException(status_code=401, detail="Código inválido ou expirado")

    tel = resultado["telefone"]  # já normalizado

    # Auto-onboarding: cria usuário tipo=normal no primeiro login
    usuario = db.query(Usuario).filter(Usuario.telefone == tel).first()
    if not usuario:
        usuario = Usuario(telefone=tel, tipo="normal", ativo=True)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        logger.info(f"Usuário criado via OTP: id={usuario.id}, tel={tel}")

    token = auth_service.gerar_jwt(
        usuario_id=usuario.id,
        tipo=usuario.tipo or "normal",
        master_id=usuario.master_id,
    )
    return {
        "token": token,
        "tipo": usuario.tipo or "normal",
        "master_id": usuario.master_id,
        "usuario_id": usuario.id,
    }
