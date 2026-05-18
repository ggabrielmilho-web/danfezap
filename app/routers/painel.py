"""
Endpoints do painel web (Fase 2 — Painel Pro).

Todos protegidos por Depends(usuario_logado).

GET /api/painel/me                              → info do usuário (sem 403, frontend mostra mensagem amigável)
GET /api/painel/consultas?inicio=&fim=&sucesso= → lista paginada de consultas próprias
GET /api/painel/consultas/{id}/pdf              → re-download PDF via consultar_com_fallback
GET /api/painel/consultas/{id}/xml              → re-download XML idem
GET /api/painel/consultas/export.csv            → CSV das consultas (mesmos filtros)
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Consulta, Usuario
from ..services.auth_service import usuario_logado
from ..services.danfe import consultar_com_fallback
from ..utils.csv_export import gerar_csv_consultas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/painel", tags=["painel"])


# Limite hard pra export CSV — acima disso obriga refinar filtro
_CSV_MAX_LINHAS = 5000
_PAGE_DEFAULT = 50
_PAGE_MAX = 200

_PLANOS_COM_PAINEL = ("pro", "escritorio")
_TIPOS_COM_PAINEL = ("normal",)  # Fase 3 expande pra escritorio_dono/admin

_REGEX_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _exige_acesso_painel(usuario: Usuario) -> None:
    """
    Levanta 403 se o usuário não tem painel liberado.

    Critério Fase 2: plano in {pro, escritorio} E assinatura ativa E tipo='normal'.
    Tipo escritorio_dono/admin fica bloqueado igual normal até Fase 3.
    """
    if usuario.tipo not in _TIPOS_COM_PAINEL:
        raise HTTPException(status_code=403, detail="Painel Escritório em construção. Em breve.")
    if usuario.plano not in _PLANOS_COM_PAINEL:
        raise HTTPException(status_code=403, detail="Seu plano não inclui o painel. Assine o Pro pelo WhatsApp.")
    if not usuario.assinatura_ativa:
        raise HTTPException(status_code=403, detail="Sua assinatura está inativa. Renove pelo WhatsApp.")


def _parse_data(rotulo: str, valor: Optional[str]) -> Optional[date]:
    if not valor:
        return None
    if not _REGEX_DATA.match(valor):
        raise HTTPException(status_code=400, detail=f"{rotulo} deve estar no formato YYYY-MM-DD")
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{rotulo} inválido")


def _aplicar_filtros(query, usuario: Usuario, inicio: Optional[date], fim: Optional[date], sucesso: Optional[bool]):
    query = query.filter(Consulta.usuario_id == usuario.id)
    if inicio:
        query = query.filter(Consulta.data_consulta >= datetime.combine(inicio, datetime.min.time()))
    if fim:
        # fim inclusivo: até 23:59:59 do dia
        query = query.filter(Consulta.data_consulta < datetime.combine(fim, datetime.min.time()) + timedelta(days=1))
    if sucesso is not None:
        query = query.filter(Consulta.sucesso == sucesso)
    return query


@router.get("/me")
def me(usuario: Usuario = Depends(usuario_logado)):
    """
    Info do usuário logado. NÃO levanta 403 quando sem acesso — devolve
    flag pra frontend renderizar card amigável de upsell.
    """
    pode = (
        usuario.tipo in _TIPOS_COM_PAINEL
        and usuario.plano in _PLANOS_COM_PAINEL
        and usuario.assinatura_ativa
    )
    return {
        "usuario_id": usuario.id,
        "telefone": usuario.telefone,
        "nome": usuario.nome,
        "tipo": usuario.tipo,
        "plano": usuario.plano,
        "assinatura_ativa": usuario.assinatura_ativa,
        "consultas_disponiveis": usuario.consultas_disponiveis,
        "dias_restantes": usuario.dias_restantes,
        "pode_acessar_painel": pode,
    }


@router.get("/consultas")
def listar_consultas(
    inicio: Optional[str] = Query(None, description="YYYY-MM-DD"),
    fim: Optional[str] = Query(None, description="YYYY-MM-DD"),
    sucesso: Optional[bool] = Query(None),
    limit: int = Query(_PAGE_DEFAULT, ge=1, le=_PAGE_MAX),
    offset: int = Query(0, ge=0),
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    _exige_acesso_painel(usuario)
    inicio_d = _parse_data("inicio", inicio)
    fim_d = _parse_data("fim", fim)

    base = _aplicar_filtros(db.query(Consulta), usuario, inicio_d, fim_d, sucesso)
    total = base.count()
    rows = base.order_by(Consulta.data_consulta.desc()).limit(limit).offset(offset).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": c.id,
                "data_consulta": c.data_consulta.isoformat() if c.data_consulta else None,
                "chave_nfe": c.chave_nfe,
                "sucesso": c.sucesso,
                "tentativas": c.tentativas,
                "ultimo_erro": c.ultimo_erro,
            }
            for c in rows
        ],
    }


def _buscar_consulta_do_usuario(consulta_id: int, usuario: Usuario, db: Session) -> Consulta:
    consulta = db.query(Consulta).filter(
        Consulta.id == consulta_id,
        Consulta.usuario_id == usuario.id,
    ).first()
    if not consulta:
        # 404 (não 403) pra não vazar existência de IDs de outros usuários
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    if not consulta.sucesso:
        raise HTTPException(status_code=400, detail="Consulta original falhou — não há nota para baixar.")
    return consulta


@router.get("/consultas/{consulta_id}/pdf")
async def baixar_pdf(
    consulta_id: int,
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    _exige_acesso_painel(usuario)
    consulta = _buscar_consulta_do_usuario(consulta_id, usuario, db)

    resultado = await consultar_com_fallback(consulta.chave_nfe)
    if not resultado.get("sucesso") or not resultado.get("pdf_bytes"):
        logger.warning(f"Re-download PDF falhou para chave {consulta.chave_nfe[-8:]}: {resultado.get('erro')}")
        raise HTTPException(status_code=502, detail="Falha ao re-baixar PDF. Tente novamente em instantes.")

    filename = f"DANFE_{consulta.chave_nfe[-8:]}.pdf"
    return Response(
        content=resultado["pdf_bytes"],
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/consultas/{consulta_id}/xml")
async def baixar_xml(
    consulta_id: int,
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    _exige_acesso_painel(usuario)
    consulta = _buscar_consulta_do_usuario(consulta_id, usuario, db)

    resultado = await consultar_com_fallback(consulta.chave_nfe)
    if not resultado.get("sucesso") or not resultado.get("xml_bytes"):
        logger.warning(f"Re-download XML falhou para chave {consulta.chave_nfe[-8:]}: {resultado.get('erro')}")
        raise HTTPException(status_code=502, detail="Falha ao re-baixar XML. Tente novamente em instantes.")

    filename = f"NFE_{consulta.chave_nfe[-8:]}.xml"
    return Response(
        content=resultado["xml_bytes"],
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/consultas/export.csv")
def exportar_csv(
    inicio: Optional[str] = Query(None),
    fim: Optional[str] = Query(None),
    sucesso: Optional[bool] = Query(None),
    usuario: Usuario = Depends(usuario_logado),
    db: Session = Depends(get_db),
):
    _exige_acesso_painel(usuario)
    inicio_d = _parse_data("inicio", inicio)
    fim_d = _parse_data("fim", fim)

    base = _aplicar_filtros(db.query(Consulta), usuario, inicio_d, fim_d, sucesso)
    total = base.count()
    if total > _CSV_MAX_LINHAS:
        raise HTTPException(
            status_code=400,
            detail=f"Resultado tem {total} linhas (limite {_CSV_MAX_LINHAS}). Refine o filtro de data.",
        )

    rows = base.order_by(Consulta.data_consulta.desc()).all()
    csv_bytes = gerar_csv_consultas(rows)

    filename = f"consultas_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
