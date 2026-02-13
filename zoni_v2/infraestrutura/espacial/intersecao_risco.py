"""Interseção simplificada com camadas de suscetibilidade a riscos."""

from dataclasses import dataclass, field
from typing import List, Optional

from qgis.core import QgsSpatialIndex, QgsFeatureRequest

from .config_camadas import obter_camada


@dataclass
class ResultadoRisco:
    classe_inundacao: Optional[str] = None
    classe_movimento_massa: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    notas: List[str] = field(default_factory=list)


def _verificar_classe(camada_papel, geom_lote, campos_classe=None):
    camada = obter_camada(camada_papel)
    if camada is None:
        return None, None

    indice = QgsSpatialIndex(camada.getFeatures())
    ids = indice.intersects(geom_lote.boundingBox())

    valor = None
    feicao_encontrada = None

    for feicao in camada.getFeatures(QgsFeatureRequest().setFilterFids(ids)):
        geom = feicao.geometry()
        if not geom or not geom.intersects(geom_lote):
            continue
        feicao_encontrada = feicao
        nomes = feicao.fields().names()
        if campos_classe:
            for nome in campos_classe:
                if nome in nomes:
                    valor = feicao[nome]
                    break
        break

    return valor, feicao_encontrada


def intersecao_risco(geom_lote):
    resultado = ResultadoRisco()

    classe_inund, feat_inund = _verificar_classe(
        "susc_inundacao",
        geom_lote,
        campos_classe=["CLASSE", "classe", "NIVEL", "nivel"],
    )
    if feat_inund is not None:
        resultado.classe_inundacao = str(classe_inund) if classe_inund is not None else None
        resultado.flags.append("RISCO_INUNDACAO")
        msg = "Lote em área de suscetibilidade a inundação"
        if classe_inund is not None:
            msg += f" (classe {classe_inund})."
        resultado.notas.append(msg)

    classe_mov, feat_mov = _verificar_classe(
        "susc_mov_massa",
        geom_lote,
        campos_classe=["CLASSE", "classe", "NIVEL", "nivel"],
    )
    if feat_mov is not None:
        resultado.classe_movimento_massa = str(classe_mov) if classe_mov is not None else None
        resultado.flags.append("RISCO_MOVIMENTO_MASSA")
        msg = "Lote em área de suscetibilidade a movimento de massa"
        if classe_mov is not None:
            msg += f" (classe {classe_mov})."
        resultado.notas.append(msg)

    return resultado
