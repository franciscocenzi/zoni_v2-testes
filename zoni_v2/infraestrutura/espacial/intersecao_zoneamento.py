"""Rotinas de interseção de lote com a camada de zoneamento."""

from dataclasses import dataclass, field
from typing import List, Optional

from qgis.core import QgsFeatureRequest, QgsSpatialIndex

from .config_camadas import obter_camada


@dataclass
class ResultadoZoneamento:
    zona: Optional[str] = None
    macrozona: Optional[str] = None
    eixos: List[str] = field(default_factory=list)
    especiais: List[str] = field(default_factory=list)
    mensagens: List[str] = field(default_factory=list)


def _obter_atributo(feicao, candidatos):
    nomes = feicao.fields().names()
    for nome in candidatos:
        if nome in nomes:
            return feicao[nome]
    return None


def intersecao_zoneamento(geom_lote):
    resultado = ResultadoZoneamento()

    camada_zon = obter_camada("zoneamento")
    if camada_zon is None:
        resultado.mensagens.append("Camada de zoneamento não encontrada no projeto.")
        return resultado

    indice = QgsSpatialIndex(camada_zon.getFeatures())
    ids = indice.intersects(geom_lote.boundingBox())

    melhor_feicao = None
    melhor_area = 0.0

    for feicao in camada_zon.getFeatures(QgsFeatureRequest().setFilterFids(ids)):
        geom = feicao.geometry()
        if not geom or not geom.intersects(geom_lote):
            continue
        inter = geom.intersection(geom_lote)
        area = inter.area()
        if area > melhor_area:
            melhor_area = area
            melhor_feicao = feicao

    if melhor_feicao is None:
        resultado.mensagens.append("Lote não intersecta a camada de zoneamento.")
        return resultado

    resultado.zona = _obter_atributo(
        melhor_feicao,
        ["zona", "ZONA", "Zona", "cod_zona", "COD_ZONA", "SIGLA_ZONA"],
    )
    resultado.macrozona = _obter_atributo(
        melhor_feicao,
        ["macrozona", "MACROZONA", "Macrozona", "macro", "MACRO"],
    )

    eixo_attr = _obter_atributo(melhor_feicao, ["eixo", "EIXO", "eixos", "EIXOS"])
    if eixo_attr:
        if isinstance(eixo_attr, str):
            partes = [p.strip() for p in eixo_attr.replace(",", ";").split(";") if p.strip()]
            resultado.eixos.extend(partes)
        else:
            resultado.eixos.append(str(eixo_attr))

    esp_attr = _obter_atributo(
        melhor_feicao,
        ["especial", "ESPECIAL", "zona_esp", "ZONA_ESP"],
    )
    if esp_attr:
        if isinstance(esp_attr, str):
            partes = [p.strip() for p in esp_attr.replace(",", ";").split(";") if p.strip()]
            resultado.especiais.extend(partes)
        else:
            resultado.especiais.append(str(esp_attr))

    return resultado
