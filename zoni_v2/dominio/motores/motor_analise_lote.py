# -*- coding: utf-8 -*-
"""Motor integrado de análise de lote para o núcleo Zôni v2."""

from dataclasses import dataclass
from typing import Optional

from qgis.core import QgsGeometry

from .zoneamento_resolvedor import ZoneamentoResolvedor, ZonaResolvida

from ...infraestrutura.espacial.intersecao_zoneamento import ( ResultadoZoneamento, intersecao_zoneamento, )
from ...infraestrutura.espacial.intersecao_app import intersecao_app, ResultadoAPP
from ...infraestrutura.espacial.intersecao_risco import intersecao_risco, ResultadoRisco
from ...infraestrutura.espacial.zoneamento_lote import ( calcular_zoneamento_incidente, ResultadoZoneamentoGeom, )
from ...infraestrutura.espacial.config_camadas import obter_camada
from ...infraestrutura.espacial.testadas import ( calcular_testadas_e_logradouros, ResultadoTestadas, DEFAULT_MAX_DIST_TESTADA_M, )
from ...infraestrutura.espacial.intersecao_inclinacao import ( analisar_inclinacao_terreno, ResultadoInclinacao )
from ..regras.regras_zoneamento import (
    avaliar_edificacao_na_zona,
    ResultadoAvaliacaoZona,
)


# --------------------------------------------------------------------
# Cenários e resultados
# --------------------------------------------------------------------


@dataclass
class CenarioEdificacao:
    area_lote_m2: float
    area_construida_total_m2: Optional[float] = None
    area_ocupada_projecao_m2: Optional[float] = None
    area_permeavel_m2: Optional[float] = None
    altura_maxima_m: Optional[float] = None
    numero_pavimentos: Optional[int] = None


@dataclass
class ResultadoAnaliseLote:
    """
    Resultado consolidado da análise de um lote/gleba.

    - zoneamento_intersecao: resultado "bruto" da interseção com a camada de zoneamento.
    - zoneamento_avaliacao: avaliação numérica em uma zona de referência (CA, TO, etc.).
    - app / risco: resultados das interseções ambientais.
    - zoneamento_geom: decomposição geométrica multi-zona (zonas + áreas incidentes).
    - zona_resolvida: saída do ZoneamentoResolvedor (zona_principal/zona_referencia,
      notas, parâmetros).
    - testadas: resultado do módulo de testadas/limites.
    - inclinacao: resultado da análise de inclinação do terreno (NOVO).
    """
    zoneamento_intersecao: ResultadoZoneamento
    zoneamento_avaliacao: Optional[ResultadoAvaliacaoZona]
    app: ResultadoAPP
    risco: ResultadoRisco
    zoneamento_geom: Optional[ResultadoZoneamentoGeom] = None
    zona_resolvida: Optional[ZonaResolvida] = None
    testadas: Optional[ResultadoTestadas] = None
    inclinacao: Optional[ResultadoInclinacao] = None
    detectou_frente_nota_10: bool = False
    detectou_frente_nota_37: bool = False
    nome_via_nota_10: Optional[str] = None


# --------------------------------------------------------------------
# Função principal
# --------------------------------------------------------------------


def analisar_lote(
    geom_lote: QgsGeometry,
    cenario: CenarioEdificacao,
    caminho_parametros_zoneamento: str,
    nota10_confirmada: bool = False,
    max_dist_testada_m: float = DEFAULT_MAX_DIST_TESTADA_M,
) -> ResultadoAnaliseLote:
    """
    Analisa um lote/gleba em quatro grandes blocos:

    1) Interseções básicas: zoneamento, APP, risco.
    2) Zoneamento geométrico + testadas/logradouros.
    3) Resolução de regras de sobreposição (ZoneamentoResolvedor) +
       avaliação numérica em uma zona de referência (CA, TO, etc.).
    4) Análise de inclinação do terreno (NOVO).
    """

    if geom_lote is None or geom_lote.isEmpty():
        raise ValueError("Geometria do lote inválida ou vazia.")

    # Camadas necessárias, obtidas do registro central (config_camadas)
    camada_zoneamento = obter_camada("zoneamento")
    camada_lotes = obter_camada("lotes")
    camada_logradouros = obter_camada("logradouros")
    camada_inclinacao = obter_camada("app_inclinacao")  # NOTA: chave correta

    print(f"=== DEBUG INCLINAÇÃO ===")
    print(f"Camada de inclinação: {camada_inclinacao}")
    if camada_inclinacao:
        print(f"  Nome: {camada_inclinacao.name()}")
        print(f"  Tipo: {camada_inclinacao.type()}")
        print(f"  É válida? {camada_inclinacao.isValid()}")
        print(f"  CRS: {camada_inclinacao.crs().authid() if camada_inclinacao.crs() else 'None'}")
        print(f"  Extensão: {camada_inclinacao.extent().toString()}")
        print(f"  Resolução: {camada_inclinacao.rasterUnitsPerPixelX()} x {camada_inclinacao.rasterUnitsPerPixelY()}")
    else:
        print("  Camada de inclinação é None!")

    # ------------------------------------------------------------------
    # 1) Interseções básicas
    # ------------------------------------------------------------------
    res_zon = intersecao_zoneamento(geom_lote)
    res_app = intersecao_app(geom_lote)
    res_risco = intersecao_risco(geom_lote)

    # Garante que exista lista de mensagens em res_zon
    if not hasattr(res_zon, "mensagens") or res_zon.mensagens is None:
        try:
            res_zon.mensagens = []
        except Exception:
            # se for imutável por algum motivo, ignora
            pass

    # ------------------------------------------------------------------
    # 2) Zoneamento geométrico + testadas/logradouros
    # ------------------------------------------------------------------
    res_geom: Optional[ResultadoZoneamentoGeom] = None
    res_testadas: Optional[ResultadoTestadas] = None

    # 2.1) Geometria do zoneamento incidente (multi-zona)
    if camada_zoneamento is not None:
        try:
            res_geom = calcular_zoneamento_incidente(
                lote_geom=geom_lote,
                camada_zoneamento=camada_zoneamento,
            )
        except Exception:
            res_geom = None

    # 2.2) Testadas, limites e associação a logradouros
    res_testadas: Optional[ResultadoTestadas] = None

    if camada_lotes is not None:
        try:
            res_testadas = calcular_testadas_e_logradouros(
                lote_geom=geom_lote,
                camada_lotes=camada_lotes,
                camada_logradouros=camada_logradouros,  # pode ser None
                max_dist_m=max_dist_testada_m,
            )
        except Exception as exc:
            res_testadas = None
            # opcional: deixar um rastro em mensagens
            try:
                res_zon.mensagens.append(
                    f"Falha ao calcular testadas/logradouros: {exc}"
                )
            except Exception:
                pass

    # 2.3) Detecção de frentes especiais (Notas 10 e 37)
    detectou_frente_nota_10 = False
    detectou_frente_nota_37 = False
    nome_via_nota_10 = None

    if res_testadas and res_testadas.testadas_por_logradouro:
        for nome_logradouro in res_testadas.testadas_por_logradouro.keys():
            nome_norm = nome_logradouro.lower().strip()

            if "sebastião manoel coelho" in nome_norm:
                detectou_frente_nota_10 = True
                nome_via_nota_10 = nome_logradouro

            if "lúcio joaquim mendes" in nome_norm:
                detectou_frente_nota_37 = True


    # ------------------------------------------------------------------
    # 3) Resolução de zoneamento (rulebook) + avaliação numérica
    # ------------------------------------------------------------------
    zona_resolvida: Optional[ZonaResolvida] = None
    res_av_zon: Optional[ResultadoAvaliacaoZona] = None

    # 3.1) Resolve regras de sobreposição / notas a partir do JSON
    if res_geom is not None:
        resolvedor = ZoneamentoResolvedor(caminho_parametros_zoneamento)
        try:
            zona_resolvida = resolvedor.resolver(
                res_zon=res_zon,
                res_geom=res_geom,
                nota10_ativada=nota10_ativada,
                nota37_ativada=nota37_ativada,
            )

        except Exception:
            zona_resolvida = None

    # 3.2) Integra mensagens do resolvedor ao resultado de zoneamento
    if zona_resolvida is not None:
        # Notas ativas (10, 37, etc.)
        if getattr(zona_resolvida, "notas_ativas", None):
            try:
                res_zon.mensagens.append(
                    "Notas do Anexo III aplicadas: "
                    + ", ".join(zona_resolvida.notas_ativas)
                )
            except Exception:
                pass

        # Motivo / descrição da regra aplicada (propriedade opcional)
        if getattr(zona_resolvida, "motivo", None):
            try:
                res_zon.mensagens.append(zona_resolvida.motivo)
            except Exception:
                pass

        # Tipo de regra (rótulo interno)
        if (
            getattr(zona_resolvida, "tipo_regra", None)
            and zona_resolvida.tipo_regra != "NAO_DEFINIDA"
        ):
            try:
                res_zon.mensagens.append(
                    f"Regime de aplicação definido pela regra: "
                    f"{zona_resolvida.tipo_regra}."
                )
            except Exception:
                pass

        # Opcional: alinhar a zona "bruta" à zona de referência
        if getattr(zona_resolvida, "zona_principal", None):
            try:
                res_zon.zona = zona_resolvida.zona_principal
            except Exception:
                # se o campo for somente leitura, ignora
                pass

    # 3.3) Avaliação numérica dos índices urbanísticos
    if zona_resolvida is not None and getattr(zona_resolvida, "zona_principal", None):
        parametros = getattr(zona_resolvida, "parametros", None)

        if parametros is not None:
            # Avaliação usando a zona de referência (zona_principal) e os
            # parâmetros já carregados a partir do JSON de zoneamento.
            res_av_zon = avaliar_edificacao_na_zona(
                zona=zona_resolvida.zona_principal,
                parametros=parametros,
                area_lote_m2=cenario.area_lote_m2,
                area_construida_total_m2=cenario.area_construida_total_m2,
                area_ocupada_projecao_m2=cenario.area_ocupada_projecao_m2,
                area_permeavel_m2=cenario.area_permeavel_m2,
                altura_maxima_m=cenario.altura_maxima_m,
                numero_pavimentos=cenario.numero_pavimentos,
            )
        else:
            # Zona de referência definida mas sem parâmetros no JSON
            try:
                res_zon.mensagens.append(
                    f"Parâmetros urbanísticos da zona "
                    f"'{zona_resolvida.zona_principal}' "
                    f"não encontrados no arquivo de parâmetros."
                )
            except Exception:
                pass
    else:
        # Não foi possível obter uma zona de referência
        try:
            res_zon.mensagens.append(
                "Não foi possível definir zona de referência para "
                "avaliação numérica dos índices urbanísticos."
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 4) Análise de inclinação do terreno (NOVO)
    # ------------------------------------------------------------------
    res_inclinacao: Optional[ResultadoInclinacao] = None
    
    if camada_inclinacao is not None:
        print(f"DEBUG: Iniciando análise de inclinação com camada '{camada_inclinacao.name()}'")
        try:
            res_inclinacao = analisar_inclinacao_terreno(
                lote_geom=geom_lote,
                camada_inclinacao=camada_inclinacao,
                area_lote_m2=cenario.area_lote_m2
            )
            
            # Adicionar mensagem sobre APP por inclinação se detectado
            if res_inclinacao and hasattr(res_inclinacao, 'tem_app_por_inclinacao') and res_inclinacao.tem_app_por_inclinacao:
                try:
                    res_zon.mensagens.append(
                        "Detectada APP por inclinação do terreno (>45°)."
                    )
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"DEBUG: Erro na análise de inclinação: {e}")
            # Se houver erro, ainda assim continuamos, mas adicionamos uma mensagem
            try:
                res_zon.mensagens.append(
                    f"Erro na análise de inclinação do terreno: {e}"
                )
            except Exception:
                pass
            res_inclinacao = None
    else:
        print("DEBUG: camada_inclinacao é None, não será feita análise de inclinação")
        # Criar dados de exemplo para teste
        print("AVISO: Usando dados de exemplo para inclinação (camada não encontrada)")
        
        # Dados de exemplo para teste
        faixas_exemplo = [
            {"faixa": "≤ 3°", "area_m2": cenario.area_lote_m2 * 0.4, "percentual": 40.0, "cor": "#1a9641", "app": False},
            {"faixa": "3° - 8°", "area_m2": cenario.area_lote_m2 * 0.25, "percentual": 25.0, "cor": "#fbfdbc", "app": False},
            {"faixa": "8° - 15°", "area_m2": cenario.area_lote_m2 * 0.15, "percentual": 15.0, "cor": "#fee4a1", "app": False},
            {"faixa": "15° - 30°", "area_m2": cenario.area_lote_m2 * 0.10, "percentual": 10.0, "cor": "#fec981", "app": False},
            {"faixa": "30° - 45°", "area_m2": cenario.area_lote_m2 * 0.07, "percentual": 7.0, "cor": "#fdae61", "app": False},
            {"faixa": "> 45° (APP)", "area_m2": cenario.area_lote_m2 * 0.03, "percentual": 3.0, "cor": "#d7191c", "app": True},
        ]
        
        area_app_exemplo = cenario.area_lote_m2 * 0.03
        percentual_app_exemplo = 3.0
        
        # Criar objeto ResultadoInclinacao com dados de exemplo
        res_inclinacao = ResultadoInclinacao(
            faixas=faixas_exemplo,
            area_total_m2=cenario.area_lote_m2,
            area_app_inclinacao_m2=round(area_app_exemplo, 2),
            percentual_app_inclinacao=round(percentual_app_exemplo, 2),
            mensagens=["Dados de exemplo - Camada de inclinação não encontrada no projeto"],
            tem_app_por_inclinacao=True if area_app_exemplo > 0 else False
        )

    # ------------------------------------------------------------------
    # Retorno final consolidado
    # ------------------------------------------------------------------
    return ResultadoAnaliseLote(
        zoneamento_intersecao=res_zon,
        zoneamento_avaliacao=res_av_zon,
        app=res_app,
        risco=res_risco,
        zoneamento_geom=res_geom,
        zona_resolvida=zona_resolvida,
        testadas=res_testadas,
        inclinacao=res_inclinacao,
        detectou_frente_nota_10 = detectou_frente_nota_10,
        detectou_frente_nota_37 = detectou_frente_nota_37,
        nome_via_nota_10 = nome_via_nota_10,
    )

class MotorAnaliseLote:
    def __init__(
        self,
        regras_zoneamento,
        regras_app,
        regras_risco,
        geometria_utils,
        interseccao_service,
        testadas_service,
        validador,
    ):
        self.regras_zoneamento = regras_zoneamento
        self.regras_app = regras_app
        self.regras_risco = regras_risco
        self.geometria_utils = geometria_utils
        self.interseccao_service = interseccao_service
        self.testadas_service = testadas_service
        self.validador = validador

    def analisar(
        self,
        geom_lote,
        cenario,
        caminho_parametros_zoneamento,
        nota10_ativada=False,
        nota37_ativada=False,
        max_dist_testada_m=DEFAULT_MAX_DIST_TESTADA_M,
    ):
        return analisar_lote(
            geom_lote,
            cenario,
            caminho_parametros_zoneamento,
            nota10_ativada,
            nota37_ativada,
            max_dist_testada_m,
        )
