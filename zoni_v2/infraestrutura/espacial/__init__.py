# -*- coding: utf-8 -*-
"""Módulo espacial - re-exporta funções principais."""

from .geometrias import unir_geometrias, GeometriaUtils
from .validadores import lotes_sao_contiguos, ValidadorGeometrias

# Você pode adicionar outras exportações conforme necessário
__all__ = [
    'unir_geometrias',
    'GeometriaUtils',
    'lotes_sao_contiguos',
    'ValidadorGeometrias',
]