"""
Normalização de telefones brasileiros — fonte de verdade única.
Usado por whatsapp_service (envio) e otp_service (login).
"""


def normalizar_telefone_br(telefone: str) -> str:
    """
    Retorna número apenas com dígitos + código do Brasil (55).

    Exemplos:
        "(11) 99999-9999" -> "5511999999999"
        "11999999999"     -> "5511999999999"
        "5511999999999"   -> "5511999999999"
        "+55 11 99999-9999" -> "5511999999999"
    """
    numero = ''.join(filter(str.isdigit, telefone or ""))
    if not numero.startswith('55'):
        numero = '55' + numero
    return numero
