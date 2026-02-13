# -*- coding: utf-8 -*-
"""
Regras de sobreposição de zoneamento (LC 275/2025, Anexo III).

Aqui mora apenas a "inteligência" de qual zona prevalece e por quê,
incluindo:
- Notas 10 (ZEOT2) e 37 (MUQ3);
- relação Eixo x Macrozona x Zona Especial;
- texto explicativo da regra aplicada.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import unicodedata

# ------------------------------------------------------------------
# Mapeamento normativo: logradouro → eixo / semieixo
# Fonte: LC 275/2025 / Anexo III
# ------------------------------------------------------------------

MAPA_LOGRADOURO_EIXO = {
    # EIXOS
    "AV GOVERNADOR CELSO RAMOS": "EU1",
}

MAPA_LOGRADOURO_SEMIEIXO = {
    "RUA SAO PAULO": "SEMIEIXO",
    "RUA OLINDINA PEIXOTO": "SEMIEIXO",
}

@dataclass
class ResultadoRegraSobreposicao:
    zonas_consideradas: List[str]
    zona_principal: Optional[str]
    tipo_regra: str
    motivo: str
    zonas_especiais: List[str]
    zonas_eixo: List[str]
    zonas_macros: List[str]


def _classificar_zona(codigo: str) -> str:
    """
    Classifica o código de zona em categorias amplas:

    - "ZONA ESPECIAL" e SETORES: zonas ZET, ZEITA, ZEIS, ZEOT, SETOR_MINERACAO...
    - "EIXO": zonas de eixo urbano (EIXOACESSO, EIXOORLA, EU1, EU2, EU3, EU4 ou contendo 'EIXO')
    - "SEMIEIXO": zonas de semieixo urbano ('SEMIEIXO')    
    - "MACRO": macrozonas (MUQ, MEU, MUIS, MUCON, MUO, MUPA, MRO, MRPA etc.)
    - "OUTRA": qualquer outra classificação
    """
    if not codigo:
        return "OUTRA"

    cod = codigo.upper().strip()

    # Zonas Especiais (ZE) ou SETORES (SET)
    if cod.startswith("ZE"):
        return "ESPECIAL"

    # Eixos Urbanos
    if cod.startswith(("EIXOACESSO", "EIXOORLA", "EU1", "EU2", "EU3", "EU4", "EA", "EO", "EM")) or "EIXO" in cod:
        return "EIXO"

    # Semieixos Urbanos
    if cod.startswith("SEMI"):
        return "SEMIEIXO"

    # MacrozonaS: ajuste conforme nomenclatura de Porto Belo
    if cod.startswith(("MUQ", "MEU", "MUIS", "MUCON", "MUO", "MUPA", "MRO", "MRPA")):
        return "MACRO"

    return "OUTRA"

# ------------------------------------------------------------------
# Macrozonas com regime de coexistência obrigatória
# (não são substituídas por eixo / semieixo nem entre si)
# Fonte: LC 275/2025
# ------------------------------------------------------------------

MACROZONAS_COEXISTENTES = {
    "MUO",
    "MUPA1",
    "MUPA2",
    "MRPA",
}

def _normalizar_nome_logradouro(nome: str) -> str:
    """
    Normaliza nome de logradouro para facilitar detecção de padrões.

    Passos:
    - converte para maiúsculas;
    - remove acentos/diacríticos.
    """
    if not nome:
        return ""
    texto = str(nome).upper().strip()
    # Remover acentos (ú -> u, ç -> c etc.)
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return texto


def _zona_por_logradouro(nome_logradouro: str) -> Optional[str]:
    """
    Retorna a zona de EIXO ou SEMIEIXO correspondente ao logradouro,
    conforme Anexo III da LC 275/2025.
    """
    if not nome_logradouro:
        return None

    nome_norm = _normalizar_nome_logradouro(nome_logradouro)

    # Primeiro tenta EIXO
    for padrao, zona in MAPA_LOGRADOURO_EIXO.items():
        if padrao in nome_norm:
            return zona

    # Depois tenta SEMIEIXO
    for padrao, zona in MAPA_LOGRADOURO_SEMIEIXO.items():
        if padrao in nome_norm:
            return zona

    return None


def aplicar_regra_sobreposicao(
    zonas: List[str],
    areas_por_zona: Dict[str, float],
    testadas_por_logradouro: Dict[str, float],
    nota10_ativada: bool,
    nota37_ativada: bool,
) -> ResultadoRegraSobreposicao:
    """
    Aplica o "rulebook" de sobreposição de zoneamento.

    Parâmetros:
        zonas: lista de códigos de zona incidentes (geométricos)
        areas_por_zona: área em m² por código de zona
        testadas_por_logradouro: comprimentos de testada por nome de via
        nota10_ativada: flag da Nota 10 (ZEOT2 – acesso único pela Rua Sebastião...)
        nota37_ativada: flag manual da Nota 37 (MUQ3 – acesso principal pela Lúcio Joaquim Mendes)

    Retorna:
        ResultadoRegraSobreposicao com:
            zona_principal,
            tipo_regra,
            motivo (texto),
            listas auxiliares.
    """
    zonas_unicas = sorted(set(zonas))
    if not zonas_unicas:
        return ResultadoRegraSobreposicao(
            zonas_consideradas=[],
            zona_principal=None,
            tipo_regra="SEM_ZONEAMENTO",
            motivo=(
                "Nenhuma zona do Anexo III foi identificada sobre o lote. "
                "Verificar se a camada de zoneamento está correta ou se o lote "
                "está fora da área de abrangência da LC 275/2025."
            ),
            zonas_especiais=[],
            zonas_eixo=[],
            zonas_macros=[],
        )

    # ------------------------------------------------------------------
    # 1) Nota 10 – ZEOT2 (acesso único pela Rua Sebastião...)
    # ------------------------------------------------------------------
    if nota10_ativada:
        zonas_consideradas = sorted(set(zonas_unicas + ["ZEOT2"]))
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_consideradas,
            zona_principal="ZEOT2",
            tipo_regra="NOTA_10_ZEOT2",
            motivo=(
                "Aplicada a Nota 10 do Anexo III da LC 275/2025: "
                "empreendimento com acesso único por logradouro específico "
                "na Zona ZEOT2. Para fins de índices urbanísticos e parâmetros "
                "urbanos, prevalece a disciplina da ZEOT2 sobre as demais zonas incidentes."
            ),
            zonas_especiais=["ZEOT2"] if "ZEOT2" in zonas_consideradas else [],
            zonas_eixo=[z for z in zonas_consideradas if _classificar_zona(z) == "EIXO"],
            zonas_macros=[z for z in zonas_consideradas if _classificar_zona(z) == "MACRO"],
        )

    # ------------------------------------------------------------------
    # 2.a) Nota 37 – MUQ3 (acesso principal pela Rua Lúcio Joaquim Mendes)
    #     • pode ser ativada manualmente ou deduzida pelas testadas
    # ------------------------------------------------------------------
    acesso_lucio = False

    if nota37_ativada:
        acesso_lucio = True
    else:
        # Tenta deduzir pelo nome dos logradouros de testada
        for nome_via in testadas_por_logradouro.keys():
            n = _normalizar_nome_logradouro(nome_via)
            if "LUCIO" in n and "MENDES" in n:
                acesso_lucio = True
                break

    if acesso_lucio:
        zonas_consideradas = sorted(set(zonas_unicas + ["MUQ3"]))
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_consideradas,
            zona_principal="MUQ3",
            tipo_regra="NOTA_37_MUQ3",
            motivo=(
                "Aplicada a Nota 37 do Anexo III da LC 275/2025: "
                "acesso principal do empreendimento voltado para logradouro "
                "classificado como MUQ3 (eixo). Para fins de índices urbanísticos "
                "e parâmetros de recuo frontal na testada principal, prevalece MUQ3; "
                "demais frentes e parâmetros podem observar as macrozonas incidentes."
            ),
            zonas_especiais=[z for z in zonas_consideradas if _classificar_zona(z) == "ESPECIAL"],
            zonas_eixo=["MUQ3"],
            zonas_macros=[z for z in zonas_consideradas if _classificar_zona(z) == "MACRO"],
        )

    # ------------------------------------------------------------------
    # 2.b) Dedução automática de eixo / semieixo a partir das testadas
    # ------------------------------------------------------------------
    zonas_deduzidas = []

    for nome_via in testadas_por_logradouro.keys():
        zona_logradouro = _zona_por_logradouro(nome_via)
        if zona_logradouro:
            zonas_deduzidas.append(zona_logradouro)

    if zonas_deduzidas:
        zonas_unicas = sorted(set(zonas_unicas + zonas_deduzidas))

    # ------------------------------------------------------------------
    # 3) Classificação geral das zonas incidentes
    # ------------------------------------------------------------------
    zonas_especiais: List[str] = []
    zonas_eixo: List[str] = []
    zonas_semieixo: List[str] = []
    zonas_macros: List[str] = []
    zonas_outras: List[str] = []

    for z in zonas_unicas:
        cat = _classificar_zona(z)
        if cat == "ESPECIAL":
            zonas_especiais.append(z)
        elif cat == "EIXO":
            zonas_eixo.append(z)
        elif cat == "SEMIEIXO":
            zonas_semieixo.append(z)
        elif cat == "MACRO":
            zonas_macros.append(z)
        else:
            zonas_outras.append(z)

    # Função auxiliar para pegar a zona de maior área em um conjunto
    def _zona_maior_area(codigos: List[str]) -> Optional[str]:
        if not codigos:
            return None
        melhor = None
        melhor_area = -1.0
        for cod in codigos:
            a = areas_por_zona.get(cod, 0.0)
            if a > melhor_area:
                melhor_area = a
                melhor = cod
        return melhor

    # ------------------------------------------------------------------
    # Separação de macrozonas com coexistência obrigatória
    # ------------------------------------------------------------------
    zonas_macros_fixas = [z for z in zonas_macros if z in MACROZONAS_COEXISTENTES]
    zonas_macros_variaveis = [z for z in zonas_macros if z not in MACROZONAS_COEXISTENTES]

    # ------------------------------------------------------------------
    # 4) Se existir qualquer ZONA ESPECIAL → ela prevalece
    # ------------------------------------------------------------------
    if zonas_especiais:
        zp = _zona_maior_area(zonas_especiais)
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_unicas,
            zona_principal=zp,
            tipo_regra="ZONA_ESPECIAL_PREDOMINANTE",
            motivo=(
                "Foram identificadas zonas especiais (ZE...) incidentes sobre o lote. "
                "Pelas regras de sobreposição do Anexo III, a zona especial de maior área "
                f"({zp}) prevalece para definição dos parâmetros urbanísticos principais, "
                "sem prejuízo de eventuais condicionantes adicionais de eixos ou macrozonas."
            ),
            zonas_especiais=zonas_especiais,
            zonas_eixo=zonas_eixo,
            zonas_macros=zonas_macros,
        )

    # ------------------------------------------------------------------
    # 5.a) Eixo + Macrozona: eixo prevalece, macrozona dá suporte
    # ------------------------------------------------------------------
    if zonas_eixo and zonas_macros_variaveis:
        zp = _zona_maior_area(zonas_eixo)
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_unicas,
            zona_principal=zp,
            tipo_regra="EIXO_SOBRE_MACRO",
            motivo=(
                "Foram identificadas zonas de eixo urbano em conjunto com macrozonas "
                "não protegidas por regime especial de coexistência. "
                f"O eixo {zp} prevalece para definição dos parâmetros urbanísticos "
                "principais, mantendo-se a aplicação das macrozonas variáveis nas "
                "demais áreas do lote."
            ),
            zonas_especiais=[],
            zonas_eixo=zonas_eixo,
            zonas_macros=zonas_macros,
        )
    # Eixo sempre prevalece sobre semieixo
    if zonas_eixo and zonas_semieixo:
        zp = _zona_maior_area(zonas_eixo)
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_unicas,
            zona_principal=zp,
            tipo_regra="EIXO_SOBRE_SEMIEIXO",
            motivo=(
                "Foram identificadas testadas voltadas simultaneamente para eixo e "
                "semieixo urbano. Conforme hierarquia viária da LC 275/2025, o eixo "
                f"{zp} prevalece para definição dos parâmetros urbanísticos principais."
            ),
            zonas_especiais=[],
            zonas_eixo=zonas_eixo,
            zonas_macros=zonas_macros,
        )


    # ------------------------------------------------------------------
    # 5.b) Presença de macrozonas com coexistência obrigatória
    # ------------------------------------------------------------------
    if zonas_macros_fixas:
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_unicas,
            zona_principal=_zona_maior_area(zonas_eixo) if zonas_eixo else None,
            tipo_regra="COEXISTENCIA_MACROZONAS_FIXAS",
            motivo=(
                "Foram identificadas macrozonas com regime jurídico de coexistência "
                "obrigatória (MUO, MUPA, MRPA). Conforme a LC 275/2025, essas zonas "
                "não são substituídas por eixos, semieixos ou outras macrozonas, "
                "devendo cada uma ser aplicada exclusivamente sobre sua área "
                "espacial de incidência no lote ou gleba."
            ),
            zonas_especiais=[],
            zonas_eixo=zonas_eixo,
            zonas_macros=zonas_macros,
        )


    # ------------------------------------------------------------------
    # 6) Apenas Eixos
    # ------------------------------------------------------------------
    if zonas_eixo and not zonas_macros:
        zp = _zona_maior_area(zonas_eixo)
        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_unicas,
            zona_principal=zp,
            tipo_regra="APENAS_EIXO",
            motivo=(
                "Apenas zonas de eixo urbano foram identificadas sobre o lote, sem "
                "macrozona associada na área analisada. Considera-se o eixo de maior "
                f"área ({zp}) como zona principal, devendo-se complementar a interpretação "
                "com a leitura do Plano Diretor e do Anexo III para eventuais ajustes."
            ),
            zonas_especiais=[],
            zonas_eixo=zonas_eixo,
            zonas_macros=[],
        )

    # ------------------------------------------------------------------
    # 7) Apenas Macrozona(s)
    # ------------------------------------------------------------------
    if zonas_macros and not zonas_eixo:
        if len(zonas_macros) == 1:
            zp = zonas_macros[0]
            tipo = "MACRO_UNICA"
            motivo = (
                "Foi identificada uma única macrozona sobre o lote "
                f"({zp}). Para fins de parâmetros urbanísticos, aplica-se "
                "diretamente a disciplina dessa macrozona, sem sobreposição de eixos."
            )
        else:
            zp = _zona_maior_area(zonas_macros)
            tipo = "MACRO_MULTIPLA"
            motivo = (
                "Foram identificadas múltiplas macrozonas incidentes sobre o lote. "
                f"A macrozona de maior área ({zp}) tende a ser predominante, porém a "
                "interpretação definitiva depende de análise caso a caso, observando "
                "as áreas de cada zona, a posição das testadas e o disposto na LC 275/2025."
            )

        return ResultadoRegraSobreposicao(
            zonas_consideradas=zonas_unicas,
            zona_principal=zp,
            tipo_regra=tipo,
            motivo=motivo,
            zonas_especiais=[],
            zonas_eixo=[],
            zonas_macros=zonas_macros,
        )

    # ------------------------------------------------------------------
    # 8) Demais casos (não classificados especificamente)
    # ------------------------------------------------------------------
    return ResultadoRegraSobreposicao(
        zonas_consideradas=zonas_unicas,
        zona_principal=None,
        tipo_regra="SEM_REGRA_ESPECIFICA",
        motivo=(
            "Foram identificadas zonas incidentes sobre o lote, mas o conjunto não "
            "se enquadra em nenhuma das regras específicas (Nota 10, Nota 37, eixo "
            "sobre macrozona ou presença de zona especial ZE...). A definição de zona "
            "principal deve ser feita por análise técnica, com base nas áreas relativas "
            "de cada zona e na leitura direta da LC 275/2025 e do Plano Diretor."
        ),
        zonas_especiais=zonas_especiais,
        zonas_eixo=zonas_eixo,
        zonas_macros=zonas_macros,
    )
