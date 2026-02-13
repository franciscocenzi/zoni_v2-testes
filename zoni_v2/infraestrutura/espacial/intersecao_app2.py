"""Interseção de lote com camadas de APP (faixa NUIC) e manguezal."""

from dataclasses import dataclass, field
from typing import List, Optional

from qgis.core import QgsSpatialIndex, QgsFeatureRequest

from .config_camadas import obter_camada


@dataclass
class ResultadoAPP:
    em_app: bool = False
    em_app_faixa_nuic: bool = False
    em_app_manguezal: bool = False

    tipos_app: List[str] = field(default_factory=list)
    largura_faixa_m: Optional[float] = None
    notas: List[str] = field(default_factory=list)


def _criar_indice(camada):
    if camada is None:
        return None
    return QgsSpatialIndex(camada.getFeatures())


def _tentar_ler_largura(feicao) -> Optional[float]:
    nomes = feicao.fields().names()
    for nome in ["LARGURA", "largura", "LARG_FAIX", "larg_faix"]:
        if nome in nomes:
            try:
                valor = feicao[nome]
                if valor is None:
                    return None
                if isinstance(valor, str):
                    v = valor.strip().replace(".", "").replace(",", ".")
                    return float(v)
                return float(valor)
            except Exception:
                return None
    return None


def intersecao_app(geom_lote):
    resultado = ResultadoAPP()

    camada_faixa = obter_camada("faixa_app_nuic")
    camada_mangue = obter_camada("app_manguezal")

    idx_faixa = _criar_indice(camada_faixa)
    idx_mangue = _criar_indice(camada_mangue)

    print("=== DEBUG intersecao_app - APP FAIXA ===")
    print(f"Camada faixa obtida: {camada_faixa}")

    if camada_faixa and idx_faixa:
        ids = idx_faixa.intersects(geom_lote.boundingBox())
        for feicao in camada_faixa.getFeatures(QgsFeatureRequest().setFilterFids(ids)):
            geom = feicao.geometry()
            if not geom or not geom.intersects(geom_lote):
                continue

            resultado.em_app = True
            resultado.em_app_faixa_nuic = True
            resultado.tipos_app.append("APP_FAIXA_NUIC")
            resultado.notas.append(
                "Lote intersecta faixa marginal de curso d'água em área urbana consolidada "
                "(camada AMFRI_PB_LLNUIAPP)."
            )

            largura = _tentar_ler_largura(feicao)
            if largura is not None:
                resultado.largura_faixa_m = max(resultado.largura_faixa_m or 0.0, largura)

        print("✅ APP FAIXA DETECTADA pela análise!")
        print(f"   em_app_faixa_auc = {resultado.em_app_faixa_auc}")
        print(f"   largura = {resultado.largura_faixa_m}")
        print(f"   notas = {resultado.notas}")

                break

    if camada_mangue and idx_mangue:
        ids = idx_mangue.intersects(geom_lote.boundingBox())
        for feicao in camada_mangue.getFeatures(QgsFeatureRequest().setFilterFids(ids)):
            geom = feicao.geometry()
            if not geom or not geom.intersects(geom_lote):
                continue

            resultado.em_app = True
            resultado.em_app_manguezal = True
            resultado.tipos_app.append("APP_MANGUEZAL")
            resultado.notas.append(
                "Lote intersecta área cadastrada como APP de manguezal "
                "(camada AMFRI_PB_Area_Manguezal)."
            )
            break

    return resultado
