"""
Validador de chave de acesso da Nota Fiscal Eletrônica (NFe)
Valida estrutura e dígito verificador da chave de 44 dígitos
"""

# Códigos UF válidos (IBGE)
UFS_VALIDAS = {
    '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA',
    '16': 'AP', '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE',
    '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL', '28': 'SE',
    '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP',
    '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT',
    '52': 'GO', '53': 'DF'
}

# Modelos válidos de documento fiscal
MODELOS_VALIDOS = ['55', '57']  # 55=NFe, 57=CTe


def validar_chave_nfe(chave: str) -> dict:
    """
    Valida estrutura da chave de 44 dígitos da NFe/CTe

    Estrutura da chave:
    - Posição 1-2: UF (código IBGE: 11-53)
    - Posição 3-4: Ano (ex: 24, 25)
    - Posição 5-6: Mês (01-12)
    - Posição 7-20: CNPJ emitente (14 dígitos)
    - Posição 21-22: Modelo (55=NFe, 57=CTe)
    - Posição 23-25: Série
    - Posição 26-34: Número da nota
    - Posição 35: Forma de emissão (1-9)
    - Posição 36-43: Código numérico
    - Posição 44: Dígito verificador

    Args:
        chave: String com a chave de acesso

    Returns:
        dict: {
            "valida": True/False,
            "erro": "mensagem se inválida" ou None
        }
    """
    # Remover espaços e caracteres não numéricos
    chave = ''.join(filter(str.isdigit, chave))

    # 1. Verificar se tem exatamente 44 dígitos
    if len(chave) != 44:
        return {
            "valida": False,
            "erro": f"Chave deve ter 44 dígitos. Você digitou {len(chave)} dígitos."
        }

    # 2. Verificar UF válida (posições 0-1)
    uf = chave[0:2]
    if uf not in UFS_VALIDAS:
        return {
            "valida": False,
            "erro": f"Código UF '{uf}' inválido."
        }

    # 3. Verificar ano (posições 2-3) - apenas numérico
    ano = chave[2:4]
    if not ano.isdigit():
        return {
            "valida": False,
            "erro": "Ano inválido na chave."
        }

    # 4. Verificar mês válido (posições 4-5)
    mes = chave[4:6]
    try:
        mes_int = int(mes)
        if mes_int < 1 or mes_int > 12:
            return {
                "valida": False,
                "erro": f"Mês '{mes}' inválido. Deve ser entre 01 e 12."
            }
    except ValueError:
        return {
            "valida": False,
            "erro": "Mês inválido na chave."
        }

    # 5. Verificar CNPJ (posições 6-19) - apenas verificar se é numérico
    cnpj = chave[6:20]
    if not cnpj.isdigit() or len(cnpj) != 14:
        return {
            "valida": False,
            "erro": "CNPJ inválido na chave."
        }

    # 6. Verificar modelo válido (posições 20-21)
    modelo = chave[20:22]
    if modelo not in MODELOS_VALIDOS:
        return {
            "valida": False,
            "erro": f"Modelo '{modelo}' inválido. Deve ser 55 (NFe) ou 57 (CTe)."
        }

    # 7. Verificar forma de emissão (posição 34)
    forma_emissao = chave[34]
    try:
        forma_int = int(forma_emissao)
        if forma_int < 1 or forma_int > 9:
            return {
                "valida": False,
                "erro": f"Forma de emissão '{forma_emissao}' inválida."
            }
    except ValueError:
        return {
            "valida": False,
            "erro": "Forma de emissão inválida na chave."
        }

    # 8. Calcular e verificar dígito verificador (posição 43)
    digito_informado = chave[43]
    digito_calculado = calcular_digito_verificador(chave[0:43])

    if digito_informado != digito_calculado:
        return {
            "valida": False,
            "erro": f"Dígito verificador incorreto. Esperado: {digito_calculado}, Informado: {digito_informado}."
        }

    # Chave válida!
    return {
        "valida": True,
        "erro": None
    }


def calcular_digito_verificador(chave_sem_dv: str) -> str:
    """
    Calcula o dígito verificador da chave de acesso usando módulo 11

    Algoritmo:
    1. Multiplica cada dígito da chave pelos pesos de 2 a 9 (da direita para esquerda)
    2. Soma todos os resultados
    3. Calcula o resto da divisão por 11
    4. DV = 11 - resto (se resto for 0 ou 1, DV = 0)

    Args:
        chave_sem_dv: String com os primeiros 43 dígitos da chave

    Returns:
        str: Dígito verificador calculado (0-9)
    """
    if len(chave_sem_dv) != 43:
        raise ValueError("Chave deve ter 43 dígitos para calcular o DV")

    # Pesos de 2 a 9, repetidos da direita para esquerda
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0

    # Multiplica cada dígito pelo peso correspondente (da direita para esquerda)
    for i, digito in enumerate(reversed(chave_sem_dv)):
        peso = pesos[i % 8]  # Ciclo de 8 pesos (2-9)
        soma += int(digito) * peso

    # Calcula o resto da divisão por 11
    resto = soma % 11

    # Calcula o dígito verificador
    if resto == 0 or resto == 1:
        dv = 0
    else:
        dv = 11 - resto

    return str(dv)


def extrair_info_chave(chave: str) -> dict:
    """
    Extrai informações da chave de acesso (apenas se válida)

    Args:
        chave: String com a chave de acesso de 44 dígitos

    Returns:
        dict: Informações extraídas da chave ou None se inválida
    """
    validacao = validar_chave_nfe(chave)

    if not validacao["valida"]:
        return None

    # Remover espaços e caracteres não numéricos
    chave = ''.join(filter(str.isdigit, chave))

    return {
        "uf": UFS_VALIDAS.get(chave[0:2]),
        "codigo_uf": chave[0:2],
        "ano": f"20{chave[2:4]}",
        "mes": chave[4:6],
        "cnpj": chave[6:20],
        "modelo": "NFe" if chave[20:22] == "55" else "CTe",
        "codigo_modelo": chave[20:22],
        "serie": chave[22:25],
        "numero": chave[25:34],
        "forma_emissao": chave[34],
        "codigo_numerico": chave[35:43],
        "dv": chave[43]
    }
