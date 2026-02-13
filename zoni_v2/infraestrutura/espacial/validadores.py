# -*- coding: utf-8 -*-
"""Validadores geométricos - versão robusta com interseção par a par."""

from qgis.core import QgsFeature
from typing import List


def lotes_sao_contiguos(features: List[QgsFeature]) -> bool:
    """
    Verifica se os lotes são contíguus (formam uma única região conexa).

    Critério:
    - Cada lote deve tocar (intersectar) pelo menos um outro lote do conjunto.
    - Todos os lotes devem estar conectados entre si (grafo conexo).

    Implementação idêntica à versão original do plugin.
    """
    n = len(features)
    if n <= 1:
        return True

    # Extrai geometrias válidas
    geoms = []
    indices_validos = []
    for i, f in enumerate(features):
        geom = f.geometry()
        if geom and not geom.isEmpty():
            geoms.append(geom)
            indices_validos.append(i)
        else:
            # Se alguma geometria for inválida, considera não contíguo
            return False

    # Se após filtrar só restou 1 ou nenhum, retorna adequadamente
    if len(geoms) <= 1:
        return len(geoms) == n  # só é contíguo se todos eram válidos e há pelo menos 1

    # Constrói grafo de adjacência (usando intersects)
    adj = {i: [] for i in range(len(geoms))}

    for i in range(len(geoms)):
        gi = geoms[i]
        for j in range(i + 1, len(geoms)):
            gj = geoms[j]
            if gi.intersects(gj):
                adj[i].append(j)
                adj[j].append(i)

    # Verifica se o grafo é conexo a partir do primeiro vértice
    visitados = set()
    pilha = [0]

    while pilha:
        idx = pilha.pop()
        if idx in visitados:
            continue
        visitados.add(idx)
        for viz in adj[idx]:
            if viz not in visitados:
                pilha.append(viz)

    return len(visitados) == len(geoms)


class ValidadorGeometrias:
    """Validador de geometrias (compatibilidade)."""

    @staticmethod
    def sao_contiguos(features):
        return lotes_sao_contiguos(features)