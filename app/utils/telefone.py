"""
Normalização de telefones brasileiros — fonte de verdade única.
Usado por whatsapp_service (envio), otp_service (login) e (futuramente) handlers.

Formato canônico: SEM o "9 extra" de celular brasileiro.
Motivo: o WhatsApp/UazAPI usa o JID legado (12 dígitos: 55 + DDD + 8 dígitos),
mesmo pra celulares pós-Anatel. Manter o bot e o painel num formato único
evita duplicação de usuário entre os dois canais (login OTP × mensagem do bot).

Regra:
    1. Retira tudo que não é dígito.
    2. Acrescenta '55' se não começar com '55'.
    3. Se o resultado tem 13 dígitos E o 5º dígito (índice 4) é '9',
       remove esse '9' — é o "9 extra" de celular brasileiro.
    4. Retorna a string final.

Exemplos:
    "(34) 99943-4613"     -> "553499434613"
    "5534999434613"       -> "553499434613"
    "553499434613"        -> "553499434613"  (já canônico)
    "3499434613"          -> "553499434613"
    "+55 11 99999-9999"   -> "551199999999"
    "(11) 3322-1100"      -> "551133221100"  (fixo, não tem '9 extra')
"""


def normalizar_telefone_br(telefone: str) -> str:
    numero = ''.join(filter(str.isdigit, telefone or ""))

    if not numero.startswith('55'):
        numero = '55' + numero

    # Remove o "9 extra" de celular: 55 + DDD(2) + 9 + 8 dígitos → 55 + DDD(2) + 8 dígitos
    # Fixos têm primeiro dígito 2-5 e nunca caem nessa regra.
    if len(numero) == 13 and numero[4] == '9':
        numero = numero[:4] + numero[5:]

    return numero
