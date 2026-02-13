# -*- coding: utf-8 -*-
"""
Textos legais padronizados utilizados pelo Zôni v2.

Fonte normativa principal:
- Lei Complementar nº 275/2025 – Município de Porto Belo/SC
- Anexo III – Zoneamento e Regras de Sobreposição

Este módulo centraliza a redação jurídica dos textos exibidos
em relatórios, evitando divergências editoriais entre versões.
"""

TEXTOS_REGRA = {

    # --------------------------------------------------------------
    # NOTAS DO ANEXO III
    # --------------------------------------------------------------

    "NOTA_10_ZEOT2": (
        "Aplicada a Nota 10 do Anexo III da Lei Complementar nº 275/2025, "
        "em razão de o empreendimento possuir acesso único pela Rua Sebastião "
        "Manoel Coelho, devendo ser observados os parâmetros urbanísticos da "
        "ZEOT2, os quais prevalecem sobre as demais zonas incidentes."
    ),

    "NOTA_37_MUQ3": (
        "Aplicada a Nota 37 do Anexo III da Lei Complementar nº 275/2025, "
        "por se tratar de lote com frente para a Rua Lúcio Joaquim Mendes, "
        "sendo o imóvel enquadrado como MUQ3, devendo ser observados os "
        "parâmetros urbanísticos correspondentes."
    ),

    # --------------------------------------------------------------
    # SETORES E EIXOS URBANOS
    # --------------------------------------------------------------

    "SETOR_PREVALECE": (
        "Identificado setor especial incidente sobre o lote. "
        "Nos termos da Lei Complementar nº 275/2025, os parâmetros "
        "urbanísticos dos setores prevalecem sobre os parâmetros "
        "de eixos urbanos nos locais em que houver conflito."
    ),

    "EIXO_PREVALECE_SOBRE_MACROZONA": (
        "Identificado eixo urbano incidente sobre o lote ({EIXO}). "
        "Nos termos do §4º do art. 3º da Lei Complementar nº 275/2025, "
        "os parâmetros urbanísticos do eixo prevalecem sobre os "
        "parâmetros da macrozona, observando-se esta no que for omisso."
    ),

    "EIXOS_COINCIDENTES": (
        "Foram identificados múltiplos eixos urbanos incidentes sobre "
        "o lote ({EIXOS}). A Lei Complementar nº 275/2025 não estabelece "
        "hierarquia entre eixos urbanos, permanecendo todos válidos e "
        "aplicáveis, devendo os parâmetros urbanísticos ser observados "
        "conforme cada frente ou área de incidência."
    ),

    # --------------------------------------------------------------
    # CASO 7 — EIXO POR TRECHO INDETERMINADO
    # --------------------------------------------------------------

    "EIXO_POR_TRECHO_INDETERMINADO": (
        "O lote possui testada para logradouro classificado como eixo urbano "
        "por trecho, conforme o Anexo III da Lei Complementar nº 275/2025. "
        "Entretanto, não foi possível identificar automaticamente o trecho "
        "específico do eixo a partir das interseções espaciais com os "
        "polígonos de zoneamento. Assim, não foram aplicados parâmetros "
        "urbanísticos de eixo, sendo observados os parâmetros da macrozona "
        "incidente, sem prejuízo de verificação técnica complementar."
    ),

    # --------------------------------------------------------------
    # ZONAS ESPECIAIS E MACROZONAS (FALLBACKS)
    # --------------------------------------------------------------

    "ZONA_ESPECIAL_PREDOMINANTE": (
        "Identificada zona especial incidente sobre o lote ({ZONA}). "
        "Na ausência de setor ou eixo aplicável, adota-se a disciplina "
        "urbanística da zona especial como referência, mantendo-se as "
        "demais zonas como condicionantes por área, conforme a Lei "
        "Complementar nº 275/2025."
    ),

    "MACROZONA_UNICA": (
        "Identificada uma única macrozona incidente sobre o lote ({ZONA}), "
        "sendo aplicáveis diretamente os parâmetros urbanísticos "
        "correspondentes, conforme a Lei Complementar nº 275/2025."
    ),

    "MACROZONA_MULTIPLA": (
        "Foram identificadas múltiplas macrozonas incidentes sobre o lote. "
        "Para fins de síntese no relatório, considera-se como referência "
        "a macrozona de maior área de incidência ({ZONA}), sem prejuízo "
        "da aplicação dos parâmetros específicos por área."
    ),
}
