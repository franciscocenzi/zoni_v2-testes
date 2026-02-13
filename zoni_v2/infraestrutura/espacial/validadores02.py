# -*- coding: utf-8 -*-
"""Validadores geométricos."""

from qgis.core import QgsGeometry, QgsFeature
from typing import List

def lotes_sao_contiguos(features: List[QgsFeature]) -> bool:
    """
    Verifica contiguidade de forma robusta, como no plugin original:
    - Une todas as geometrias
    - Se a união for válida, considera contíguos
    - Não exige touches() lote a lote
    """
    if not features or len(features) < 2:
        return True

    # Unir todas as geometrias
    geoms = [f.geometry() for f in features if f.geometry() and not f.geometry().isEmpty()]
    if not geoms:
        return False

    uniao = geoms[0]
    for g in geoms[1:]:
        try:
            uniao = uniao.combine(g)
        except Exception:
            try:
                uniao = uniao.union(g)
            except Exception:
                return False

    # Se a união for inválida ou vazia, não são contíguos
    if uniao is None or uniao.isEmpty() or not uniao.isGeosValid():
        return False

    return True



class ValidadorGeometrias:
    """Validador de geometrias (compatibilidade)."""
    
    @staticmethod
    def sao_contiguos(features):
        return lotes_sao_contiguos(features)
