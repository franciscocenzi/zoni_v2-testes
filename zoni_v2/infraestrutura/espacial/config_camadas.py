# -*- coding: utf-8 -*-
"""
Configuração de camadas com detecção inteligente por prioridades.
"""

from qgis.core import QgsProject, QgsMapLayer, QgsVectorLayer, QgsRasterLayer

# ----------------------------------------------------------------------
# CONFIGURAÇÃO COM PRIORIDADES E FILTROS
# ----------------------------------------------------------------------

CONFIG_CAMADAS_INTELIGENTE = {
    "lotes": {
        "nomes_prioritarios": ["Lotes", "Lotes_Ativos", "Cadastro_Lotes", "parcelas", "loteamento"],
        "tipo_geometria": "polygon",
        "filtro_atributos": ["matricula", "inscricao", "area"],
        "prioridade": 10,
    },
    "zoneamento": {
        "nomes_prioritarios": ["Zoneamento", "Zoneamento_LC275", "ZONEAMENTO_2025", "LC275_Zoneamento"],
        "tipo_geometria": "polygon",
        "filtro_atributos": ["ZONEAMENTO", "ZONA", "COD_ZONA"],
        "prioridade": 10,
    },
    "faixa_app_nuic": {
        "nomes_prioritarios": ["AMFRI_PB_LLNUIAPP", "Faixa_APP_NUIC", "APP_NUIC", "faixa_app"],
        "tipo_geometria": ["line", "polygon"],
        "filtro_atributos": ["tipo_app", "faixa", "nuic"],
        "prioridade": 8,
    },
    "app_manguezal": {
        "nomes_prioritarios": ["AMFRI_PB_Area_Manguezal", "Manguezal", "APP_Manguezal", "Area_Mangue"],
        "tipo_geometria": "polygon",
        "filtro_atributos": ["manguezal", "vegetacao", "tipo_app"],
        "prioridade": 8,
    },
    "app_inclinacao": {
        "nomes_prioritarios": ["MDT_SG-22-Z-D-II-2_PB.slope.graus", "Inclinacao", "Slope", "Declividade", "MDT_slope"],
        "tipo_layer": "raster",
        "filtro_banda": 1,
        "prioridade": 9,
    },
    "susc_inundacao": {
        "nomes_prioritarios": ["AMFRI_PB_Suscetibilidade_Inundacao", "Risco_Inundacao", "Inundacao", "Susceptibilidade_Inundacao"],
        "tipo_geometria": "polygon",
        "filtro_atributos": ["inundacao", "risco", "classe"],
        "prioridade": 7,
    },
    "susc_mov_massa": {
        "nomes_prioritarios": ["AMFRI_PB_Suscetibilidade_Movimento_Massa", "Risco_Deslizamento", "Movimento_Massa", "Deslizamento"],
        "tipo_geometria": "polygon",
        "filtro_atributos": ["movimento", "deslizamento", "risco", "classe"],
        "prioridade": 7,
    },
    "logradouros": {
        "nomes_prioritarios": ["Logradouros", "Ruas", "Vias", "Eixos_viarios"],
        "tipo_geometria": "line",
        "filtro_atributos": ["nome", "tipo", "codlog"],
        "prioridade": 8,
    },
}

# ----------------------------------------------------------------------
# MAPA DE CAMADAS
# ----------------------------------------------------------------------

MAPA_CAMADAS = {}

# ----------------------------------------------------------------------
# DETECÇÃO INTELIGENTE
# ----------------------------------------------------------------------

def detectar_camada_inteligente(chave, projeto=None):
    if projeto is None:
        projeto = QgsProject.instance()

    if chave not in CONFIG_CAMADAS_INTELIGENTE:
        return None

    config = CONFIG_CAMADAS_INTELIGENTE[chave]
    todas = projeto.mapLayers().values()

    candidatos = []

    for camada in todas:
        pont = 0
        nome = camada.name().lower()

        # Nome
        for i, alvo in enumerate(config.get("nomes_prioritarios", [])):
            alvo_low = alvo.lower()
            if nome == alvo_low:
                pont += 100 - i
                break
            if alvo_low in nome:
                pont += 50 - i
                break

        # Tipo layer
        if "tipo_layer" in config:
            if config["tipo_layer"] == "raster" and camada.type() == QgsMapLayer.RasterLayer:
                pont += 30
            if config["tipo_layer"] == "vector" and camada.type() == QgsMapLayer.VectorLayer:
                pont += 30

        # Geometria
        if camada.type() == QgsMapLayer.VectorLayer:
            tipo_geom = camada.geometryType()
            tipo_map = {0: "point", 1: "line", 2: "polygon"}
            tipo_str = tipo_map.get(tipo_geom)

            tipos_ok = config.get("tipo_geometria")
            if tipos_ok:
                if isinstance(tipos_ok, str):
                    tipos_ok = [tipos_ok]
                if tipo_str in tipos_ok:
                    pont += 25

            # Atributos
            campos = [f.name().lower() for f in camada.fields()]
            for filtro in config.get("filtro_atributos", []):
                if filtro.lower() in campos:
                    pont += 20
                    break

        # Raster banda
        if camada.type() == QgsMapLayer.RasterLayer and "filtro_banda" in config:
            if camada.bandCount() >= config["filtro_banda"]:
                pont += 20

        pont += config.get("prioridade", 0)

        if pont > 0:
            candidatos.append((pont, camada))

    if not candidatos:
        return None

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return candidatos[0][1]

# ----------------------------------------------------------------------
# FUNÇÃO PRINCIPAL — SEM RECURSÃO
# ----------------------------------------------------------------------

def obter_camada(chave: str):
    """
    Retorna a camada registrada, detectada automaticamente ou encontrada por nome.
    Nunca recursiva.
    """

    # 1. Já registrada manualmente?
    camada = MAPA_CAMADAS.get(chave)
    if isinstance(camada, QgsMapLayer):
        return camada

    # 2. Tentar detecção automática
    camada_auto = detectar_camada_inteligente(chave)
    if isinstance(camada_auto, QgsMapLayer):
        MAPA_CAMADAS[chave] = camada_auto
        return camada_auto

    # 3. Fallback: se o valor padrão é string, tentar buscar pelo nome
    valor = MAPA_CAMADAS.get(chave)
    if isinstance(valor, str):
        projeto = QgsProject.instance()
        for lyr in projeto.mapLayers().values():
            if lyr.name().lower() == valor.lower():
                MAPA_CAMADAS[chave] = lyr
                return lyr

    # 4. Nada encontrado
    return None

# ----------------------------------------------------------------------
# REGISTRO MANUAL
# ----------------------------------------------------------------------

def registrar_camada(chave: str, camada):
    if camada is None:
        return
    MAPA_CAMADAS[chave] = camada
