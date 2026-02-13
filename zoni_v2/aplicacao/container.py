# -*- coding: utf-8 -*-
"""Container de dependências para injeção."""

from dataclasses import dataclass
from typing import Optional
from qgis.core import QgsProject

from ..dominio.motores.motor_analise_lote import MotorAnaliseLote
from ..dominio.regras.regras_zoneamento import RegrasZoneamento
from ..dominio.regras.regras_app import RegrasAPP
from ..dominio.regras.regras_risco import RegrasRisco
from ..infraestrutura.espacial.geometrias import GeometriaUtils
from ..infraestrutura.espacial.interseccao import InterseccaoService
from ..infraestrutura.espacial.testadas import TestadasService
from ..infraestrutura.espacial.validadores import ValidadorGeometrias
from ..infraestrutura.relatorios.construtor_relatorio import ConstrutorRelatorio
from ..infraestrutura.relatorios.renderizador_html import RenderizadorHTML
from ..compartilhado.caminhos import CaminhosConfig


@dataclass
class Config:
    """Configurações do sistema."""
    caminho_parametros: Optional[str] = None
    max_dist_testada_m: float = 20.0


class Container:
    """Container principal de dependências."""
    
    def __init__(self):
        # Configurações
        self.config = Config()
        
        # Serviços de infraestrutura
        self.geometria_utils = GeometriaUtils()
        self.interseccao_service = InterseccaoService()
        self.testadas_service = TestadasService()
        self.validador = ValidadorGeometrias()
        
        # Regras de domínio
        self.regras_zoneamento = RegrasZoneamento()
        self.regras_app = RegrasAPP()
        self.regras_risco = RegrasRisco()
        
        # Motor de análise
        self.motor_analise = MotorAnaliseLote(
            regras_zoneamento=self.regras_zoneamento,
            regras_app=self.regras_app,
            regras_risco=self.regras_risco,
            geometria_utils=self.geometria_utils,
            interseccao_service=self.interseccao_service,
            testadas_service=self.testadas_service,
            validador=self.validador
        )
        
        # Relatórios
        self.construtor_relatorio = ConstrutorRelatorio()
        self.renderizador_html = RenderizadorHTML()
        
        # Estado
        self.projeto = QgsProject.instance()
        
    def obter_camada(self, nome_camada: str):
        """Obtém uma camada pelo nome."""
        return self.projeto.mapLayersByName(nome_camada)[0] if self.projeto.mapLayersByName(nome_camada) else None