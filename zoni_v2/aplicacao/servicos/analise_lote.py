# -*- coding: utf-8 -*-
"""Serviço de aplicação para análise de lotes."""

from typing import List, Optional
from dataclasses import dataclass

from qgis.core import QgsFeature, QgsGeometry
from PyQt5.QtWidgets import QMessageBox

from ..container import Container
from ...dominio.motores.motor_analise_lote import (
    MotorAnaliseLote, 
    CenarioEdificacao, 
    ResultadoAnaliseLote
)
from ...infraestrutura.espacial.geometrias import GeometriaUtils
from ...infraestrutura.espacial.validadores import ValidadorGeometrias


@dataclass
class ConfiguracaoAnalise:
    """Configuração para análise de lote."""
    nota10_ativada: bool = False
    nota37_ativada: bool = False
    max_dist_testada_m: float = 20.0


class ServicoAnaliseLote:
    """Serviço de orquestração para análise de lotes."""

    def __init__(self, container: Container):
        self.container = container
        self.geometria_utils = GeometriaUtils()
        self.validador = ValidadorGeometrias()

    def analisar_lote_unico(
        self,
        feature_lote: QgsFeature,
        config: ConfiguracaoAnalise
    ) -> ResultadoAnaliseLote:
        """Analisa um único lote."""
        geometria = feature_lote.geometry()
        if not geometria or geometria.isEmpty():
            raise ValueError("Geometria do lote inválida")
        
        # Calcular área
        area_m2 = self._calcular_area_lote(feature_lote)
        
        # Criar cenário
        cenario = CenarioEdificacao(area_lote_m2=area_m2)
        
        # Executar análise
        return self.container.motor_analise.analisar(
            geometria_lote=geometria,
            cenario=cenario,
            configuracao=config
        )
    
    def analisar_gleba(
        self,
        features_lotes: List[QgsFeature],
        config: ConfiguracaoAnalise,
        parent_widget=None  # para exibir mensagem
    ) -> Optional[ResultadoAnaliseLote]:
        """
        Analisa uma gleba (múltiplos lotes contíguos).
        Retorna None se não forem contíguos (e exibe mensagem).
        """
        if not features_lotes:
            raise ValueError("Nenhum lote fornecido")
        
        # Verificar contiguidade
        if not self.validador.sao_contiguos(features_lotes):
            if parent_widget:
                QMessageBox.warning(
                    parent_widget,
                    "Zôni v2",
                    "Os lotes selecionados não são contíguos.\n\n"
                    "Selecione apenas lotes adjacentes para análise conjunta."
                )
            return None
        
        # Unir geometrias
        geometria_unificada = self.geometria_utils.unir_geometrias(features_lotes)
        if not geometria_unificada or geometria_unificada.isEmpty():
            raise ValueError("Falha ao unir geometrias")
        
        # Calcular área total
        area_total = sum(self._calcular_area_lote(f) for f in features_lotes)
        
        # Criar cenário
        cenario = CenarioEdificacao(area_lote_m2=area_total)
        
        # Executar análise
        return self.container.motor_analise.analisar(
            geometria_lote=geometria_unificada,
            cenario=cenario,
            configuracao=config
        )
    
    def gerar_relatorio(
        self,
        resultado_analise: ResultadoAnaliseLote,
        dados_lotes: List[dict]
    ) -> str:
        """Gera relatório HTML a partir do resultado da análise."""
        contexto = self.container.construtor_relatorio.construir(
            dados_lotes=dados_lotes,
            resultado_analise=resultado_analise
        )
        return self.container.renderizador_html.renderizar(contexto)
    
    def _calcular_area_lote(self, feature: QgsFeature) -> float:
        """Calcula área do lote em m²."""
        campos = feature.fields().names()
        
        if "área" in campos:
            return float(feature["área"] or 0)
        elif "area" in campos:
            return float(feature["area"] or 0)
        elif "Area_m2" in campos:
            return float(feature["Area_m2"] or 0)
        else:
            geom = feature.geometry()
            return geom.area() if geom else 0.0