# -*- coding: utf-8 -*-
"""Operações geométricas."""

from qgis.core import QgsGeometry, QgsFeature
from typing import List, Optional


def unir_geometrias(features: List[QgsFeature]) -> Optional[QgsGeometry]:
    """
    Une várias geometrias de forma robusta, com correção topológica.
    """
    if not features:
        return None

    geoms = [f.geometry() for f in features if f.geometry() and not f.geometry().isEmpty()]
    
    if not geoms:
        return None
    
    # Começa pela primeira
    uniao = geoms[0]

    # Une todas as outras
    for g in geoms[1:]:
        try:
            uniao = uniao.combine(g)
        except Exception:
            try:
                uniao = uniao.union(g)
            except Exception:
                return None

    # Corrigir topologia (comportamento clássico do QGIS)
    try:
        uniao = uniao.buffer(0, 5)  # 5 segmentos para aproximar círculo
    except Exception:
        pass

    # Se ainda estiver inválida, tentar "consertar"
    if uniao is None or uniao.isEmpty():
        return None

    if not uniao.isGeosValid():
        try:
            uniao = uniao.makeValid()
        except Exception:
            pass

    return uniao

class GeometriaUtils:
    """Utilitários geométricos."""
    @staticmethod
    def unir_geometrias(features):
        return unir_geometrias(features)
    
    @staticmethod
    def calcular_area(geom: QgsGeometry) -> float:
        return geom.area() if geom else 0.0