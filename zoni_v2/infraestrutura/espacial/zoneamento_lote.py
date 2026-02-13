# -*- coding: utf-8 -*-
"""
Funções espaciais para calcular o zoneamento incidente sobre um lote/gleba
com base na LC 275/2025 (Anexo III).

Este módulo NÃO faz interpretação jurídica, apenas:
- descobre o campo de código de zona na camada de zoneamento;
- intersecta a geometria do lote com o zoneamento;
- calcula área por código de zona e percentuais.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry


# Ordem de prioridade para achar o campo de código da zona
CAMPOS_CODIGO_ZONA_CANDIDATOS = [
    "Zoneamento",
    "zoneamento",
    "ZONA",
    "zona",
    "ZONE",
    "zone",
    "CODIGO",
    "Codigo",
    "codigo",
    "COD_ZONA",
    "cod_zona",
]


# ----------------------------------------------------------------------
# MODELO DE RESULTADO
# ----------------------------------------------------------------------

@dataclass
class ResultadoZoneamentoGeom:
    """
    Resultado geométrico da interseção do lote com o zoneamento.

    zonas: lista de códigos de zona incidentes (ordenada)
    areas_por_zona: área em m² por código de zona
    area_total_zoneada: soma das áreas incidentes em m²
    percentuais: área de cada zona em relação ao total (0–100)
    """
    zonas: List[str]
    areas_por_zona: Dict[str, float]
    area_total_zoneada: float
    percentuais: Dict[str, float]


# ----------------------------------------------------------------------
# DETECÇÃO DO CAMPO DE ZONA
# ----------------------------------------------------------------------

def detectar_campo_codigo_zona(
    camada_zoneamento: QgsVectorLayer,
    campo_forcado: Optional[str] = None,
) -> Optional[str]:
    """
    Tenta identificar o campo que guarda o código da zona.

    Se 'campo_forcado' for informado e existir na camada, ele é usado.
    Caso contrário, tenta os nomes em CAMPOS_CODIGO_ZONA_CANDIDATOS.
    """
    if camada_zoneamento is None or not isinstance(camada_zoneamento, QgsVectorLayer):
        return None

    nomes_campos = [f.name() for f in camada_zoneamento.fields()]

    # Se o usuário informou um campo específico, respeitar
    if campo_forcado and campo_forcado in nomes_campos:
        return campo_forcado

    # Tentar lista de candidatos
    for nome in CAMPOS_CODIGO_ZONA_CANDIDATOS:
        if nome in nomes_campos:
            return nome

    return None


# ----------------------------------------------------------------------
# CÁLCULO DO ZONEAMENTO INCIDENTE
# ----------------------------------------------------------------------

def calcular_zoneamento_incidente(
    lote_geom: QgsGeometry,
    camada_zoneamento: QgsVectorLayer,
    campo_codigo_zona: Optional[str] = None,
) -> ResultadoZoneamentoGeom:
    """
    Calcula quais zonas incidem sobre o lote/gleba e a área incidente de cada uma.

    Pressupõe que:
    - lote_geom está em um sistema de coordenadas em metros (ex.: SIRGAS 2000 / UTM);
    - camada_zoneamento está no mesmo CRS do lote.
    """
    if lote_geom is None or lote_geom.isEmpty():
        return ResultadoZoneamentoGeom([], {}, 0.0, {})

    if camada_zoneamento is None or not isinstance(camada_zoneamento, QgsVectorLayer):
        return ResultadoZoneamentoGeom([], {}, 0.0, {})

    campo_codigo = detectar_campo_codigo_zona(camada_zoneamento, campo_codigo_zona)
    if campo_codigo is None:
        return ResultadoZoneamentoGeom([], {}, 0.0, {})

    idx_codigo = camada_zoneamento.fields().indexFromName(campo_codigo)
    if idx_codigo == -1:
        return ResultadoZoneamentoGeom([], {}, 0.0, {})

    areas_por_zona: Dict[str, float] = {}

    for feat in camada_zoneamento.getFeatures():
        geom_zona = feat.geometry()
        if geom_zona is None or geom_zona.isEmpty():
            continue

        if not geom_zona.intersects(lote_geom):
            continue

        inter = geom_zona.intersection(lote_geom)
        if inter is None or inter.isEmpty():
            continue

        area_inter = inter.area()
        if area_inter <= 0:
            continue

        cod = str(feat[idx_codigo]).strip()
        if not cod:
            continue

        areas_por_zona[cod] = areas_por_zona.get(cod, 0.0) + area_inter

    if not areas_por_zona:
        return ResultadoZoneamentoGeom([], {}, 0.0, {})

    zonas = sorted(areas_por_zona.keys())
    area_total = sum(areas_por_zona.values())

    if area_total <= 0:
        percentuais = {z: 0.0 for z in zonas}
    else:
        percentuais = {z: (areas_por_zona[z] * 100.0 / area_total) for z in zonas}

    return ResultadoZoneamentoGeom(
        zonas=zonas,
        areas_por_zona=areas_por_zona,
        area_total_zoneada=area_total,
        percentuais=percentuais,
    )


# ----------------------------------------------------------------------
# Funções auxiliares para montar dados básicos do lote
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# Função auxiliar para montar dados básicos do lote
# ----------------------------------------------------------------------
def _montar_dados_lote_basicos(feature):
    """
    Extrai dados básicos do lote para o relatório.
    Retorna um dicionário com informações essenciais.
    Usa os nomes exatos dos campos conforme a camada.
    """
    if not feature:
        return None

    field_names = [f.name() for f in feature.fields()]

    def get_valor(nome_exato):
        if nome_exato in field_names:
            val = feature[nome_exato]
            # Converte string vazia para None (para exibir "-" no relatório)
            if isinstance(val, str) and val.strip() == "":
                return None
            return val
        return None

    # Área – prioridade para campo de área, senão geometria
    area_m2 = None
    if "área" in field_names:
        area_m2 = feature["área"]
    elif "area" in field_names:
        area_m2 = feature["area"]
    if area_m2 is None:
        geom = feature.geometry()
        if geom and not geom.isEmpty():
            area_m2 = geom.area()

    dados = {
        "id": feature.id(),
        "inscricao_imobiliaria": get_valor("inscr_imob"),
        "numero_cadastral": get_valor("nr_cadastr"),
        "matricula": get_valor("Matrícula"),
        "proprietario": get_valor("Propriet."),
        "bairro": get_valor("Bairro"),
        "logradouro": get_valor("Logradouro"),
        "numero": get_valor("Número"),
        "loteamento": get_valor("Loteamento"),
        "quadra": get_valor("Quadra"),
        "lote": get_valor("Lote"),
        "status_imovel": get_valor("Status"),
        "observacoes_cadastrais": get_valor("Obs"),
        "area_m2": area_m2
    }
    return dados