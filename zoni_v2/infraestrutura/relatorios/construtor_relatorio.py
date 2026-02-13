"""Montagem de contexto de relatório a partir da análise de lote."""

import unicodedata
from typing import Dict, Any, List, Union

from ...dominio.motores.motor_analise_lote import ResultadoAnaliseLote


def _normalizar_chave(chave: str) -> str:
    """Remove acentos, converte para minúsculas e remove pontuação comum."""
    chave = unicodedata.normalize('NFKD', chave).encode('ASCII', 'ignore').decode('utf-8')
    return chave.lower().replace(' ', '_').replace('.', '').replace('º', '')


def _buscar_valor_flexivel(dados: Dict, chaves_possiveis: List[str]) -> Any:
    """Procura por várias grafias de uma chave, incluindo versão normalizada."""
    # Primeiro tenta as chaves exatas
    for chave in chaves_possiveis:
        valor = dados.get(chave)
        if valor not in (None, '', ' ', 'null'):
            return valor

    # Se não achou, tenta normalizar todas as chaves do dicionário e comparar
    norm_dados = {_normalizar_chave(k): v for k, v in dados.items()}
    for chave in chaves_possiveis:
        chave_norm = _normalizar_chave(chave)
        if chave_norm in norm_dados:
            valor = norm_dados[chave_norm]
            if valor not in (None, '', ' ', 'null'):
                return valor
    return None


def _montar_identificacao(dados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai os dados cadastrais do dicionário de atributos do lote,
    tentando múltiplas grafias comuns para cada campo.
    """
    mapa = {
        'id': ['fid', 'id', 'objectid'],
        'inscricao_imobiliaria': ['inscr_imob', 'inscricao_imobiliaria', 'inscricao'],
        'numero_cadastral': ['nr_cadastr', 'numero_cadastral', 'cadastro'],
        'matricula': ['matrícula', 'matricula', 'Matrícula'],
        'proprietario': ['propriet.', 'proprietario', 'proprietário', 'propriet', 'Propriet.'],
        'bairro': ['bairro', 'Bairro'],
        'logradouro': ['logradouro', 'Logradouro', 'rua', 'Rua'],
        'numero': ['número', 'numero', 'Número', 'num'],
        'loteamento': ['loteamento', 'Loteamento'],
        'quadra': ['quadra', 'Quadra'],
        'lote': ['lote', 'Lote'],
        'status_imovel': ['status', 'Status'],
        'observacoes_cadastrais': ['obs', 'Obs', 'observacoes', 'Observações'],
        'area_m2': ['area_m2', 'area', 'Area_m2', 'área', 'Área'],
    }

    resultado = {}
    for campo_alvo, chaves_possiveis in mapa.items():
        valor = _buscar_valor_flexivel(dados, chaves_possiveis)
        resultado[campo_alvo] = valor

    # Fallback para área: procura qualquer chave que contenha 'area'
    if resultado['area_m2'] is None:
        for k, v in dados.items():
            if 'area' in _normalizar_chave(k):
                try:
                    resultado['area_m2'] = float(str(v).replace(',', '.'))
                    break
                except:
                    pass
    return resultado


def _parametros_para_dict(params: Any) -> Dict[str, Any]:
    """Converte um ParametrosZona em dict simples para uso no relatório."""
    parametros_dict: Dict[str, Any] = {}
    if params is None:
        return parametros_dict

    for nome in ["CA_min", "CA_bas", "CA_max", "Tperm", "Tocup",
                 "Npav_bas", "Npav_max", "Gab_bas", "Gab_max"]:
        if hasattr(params, nome):
            parametros_dict[nome] = getattr(params, nome)

    extras: Dict[str, Any] = {}
    for attr_name, key in [
        ("RF", "RF"), ("RFU", "RFU"), ("RL", "RL"), ("RLF", "RLF"),
        ("HEMB", "HEMB"), ("AEMax", "AEMax"),
        ("vagas_min", "vagas_min"), ("vagas", "vagas")
    ]:
        if hasattr(params, attr_name):
            extras[key] = getattr(params, attr_name)

    if extras:
        parametros_dict["extras"] = extras
    return parametros_dict


def _processar_faixas_inclinacao(faixas) -> List[Dict[str, Any]]:
    """Processa faixas de inclinação independentemente do formato."""
    resultado = []
    if not faixas:
        return resultado

    if isinstance(faixas, list):
        for item in faixas:
            if isinstance(item, dict):
                resultado.append({
                    'faixa': item.get('faixa', ''),
                    'area_m2': float(item.get('area_m2', 0)),
                    'percentual': float(item.get('percentual', 0)),
                    'cor': item.get('cor', '#FFFFFF'),
                    'app': bool(item.get('app', False))
                })
            elif hasattr(item, '__dict__'):
                resultado.append({
                    'faixa': getattr(item, 'faixa', ''),
                    'area_m2': float(getattr(item, 'area_m2', 0)),
                    'percentual': float(getattr(item, 'percentual', 0)),
                    'cor': getattr(item, 'cor', '#FFFFFF'),
                    'app': bool(getattr(item, 'app', False))
                })
    elif isinstance(faixas, dict):
        for key, value in faixas.items():
            if isinstance(value, dict):
                resultado.append({
                    'faixa': value.get('faixa', str(key)),
                    'area_m2': float(value.get('area_m2', 0)),
                    'percentual': float(value.get('percentual', 0)),
                    'cor': value.get('cor', '#FFFFFF'),
                    'app': bool(value.get('app', False))
                })
    return resultado


def construir_contexto_relatorio(
    dados_lote: Union[Dict[str, Any], List[Dict[str, Any]]],
    analise: ResultadoAnaliseLote,
) -> Dict[str, Any]:
    """Constrói o dicionário de contexto consumido pelo renderizador_html."""
    ctx: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # 1) Identificação / dados cadastrais
    # ------------------------------------------------------------------
    if isinstance(dados_lote, list):
        ctx["identificacao"] = [_montar_identificacao(d) for d in dados_lote]
    else:
        ctx["identificacao"] = _montar_identificacao(dados_lote)

    # ------------------------------------------------------------------
    # 2) Zoneamento – interseção geométrica bruta
    # ------------------------------------------------------------------
    zon = analise.zoneamento_intersecao
    ctx["zoneamento"] = {
        "zona": getattr(zon, "zona", None),
        "macrozona": getattr(zon, "macrozona", None),
        "eixos": getattr(zon, "eixos", None),
        "especiais": getattr(zon, "especiais", None),
        "mensagens": getattr(zon, "mensagens", []),
    }

    # ------------------------------------------------------------------
    # 3) Zoneamento resolvido (multi-zona)
    # ------------------------------------------------------------------
    zr = getattr(analise, "zona_resolvida", None)
    if zr is not None:
        zonas_ctx = []
        for za in getattr(zr, "zonas_aplicadas", []) or []:
            param_dict = _parametros_para_dict(getattr(za, "parametros", None))
            zonas_ctx.append({
                "codigo": getattr(za, "codigo", None),
                "tipo": getattr(za, "tipo", None),
                "area_m2": getattr(za, "area_m2", 0.0),
                "percentual_area": getattr(za, "percentual_area", 0.0),
                "notas": getattr(za, "notas", []),
                "origem": getattr(za, "origem", None),
                "parametros": param_dict,
            })

        ctx["zoneamento_resolvido"] = {
            "zonas": zonas_ctx,
            "notas_ativas": getattr(zr, "notas_ativas", []),
            "tipo_regra": getattr(zr, "tipo_regra", None),
            "resumo": getattr(zr, "resumo", ""),
            "observacoes": getattr(zr, "observacoes", []),
            "macrozona": getattr(zr, "macrozona", None),
            "eixos": getattr(zr, "eixos", []),
            "especiais": getattr(zr, "especiais", []),
            "zona_referencia": getattr(zr, "zona_principal", None),
            "zonas_incidentes": getattr(zr, "zonas_incidentes", []),
        }
    else:
        ctx["zoneamento_resolvido"] = {
            "zonas": [], "notas_ativas": [], "tipo_regra": None,
            "resumo": "", "observacoes": [], "macrozona": None,
            "eixos": [], "especiais": [], "zona_referencia": None,
            "zonas_incidentes": [],
        }

    # ------------------------------------------------------------------
    # 4) Avaliação de índices (legado)
    # ------------------------------------------------------------------
    if getattr(analise, "zoneamento_avaliacao", None) is not None:
        av = analise.zoneamento_avaliacao
        params = getattr(av, "parametros", None)
        parametros_dict = _parametros_para_dict(params)
        ctx["indices"] = {
            "zona": getattr(av, "zona", None),
            "conforme": getattr(av, "conforme", None),
            "pendencias": getattr(av, "pendencias", []),
            "observacoes": getattr(av, "observacoes", []),
            "parametros": parametros_dict,
        }
    else:
        ctx["indices"] = {
            "zona": None, "conforme": None,
            "pendencias": [], "observacoes": [], "parametros": {},
        }

    # ------------------------------------------------------------------
    # 5) Testadas / limites
    # ------------------------------------------------------------------
    testadas = getattr(analise, "testadas", None)
    if testadas is not None:
        try:
            ctx["testadas_por_logradouro"] = getattr(testadas, "testadas_por_logradouro", {}) or {}
            ctx["confrontantes_por_proprietario"] = getattr(testadas, "confrontantes_por_proprietario", {}) or {}
            segmentos = getattr(testadas, "segmentos", []) or []
            ctx["segmentos_limites"] = [
                {
                    "id_segmento": getattr(s, "id_segmento", None),
                    "comprimento_m": getattr(s, "comprimento_m", None),
                    "logradouro": getattr(s, "logradouro", None),
                    "tipo_limite": getattr(s, "tipo_limite", None),
                    "confrontante": getattr(s, "confrontante", None),
                }
                for s in segmentos
            ]
            ctx["testada_principal"] = (
                max(ctx["testadas_por_logradouro"].items(), key=lambda kv: kv[1])[0]
                if ctx["testadas_por_logradouro"] else None
            )
        except Exception:
            ctx["testadas_por_logradouro"] = {}
            ctx["confrontantes_por_proprietario"] = {}
            ctx["segmentos_limites"] = []
            ctx["testada_principal"] = None
    else:
        ctx["testadas_por_logradouro"] = {}
        ctx["confrontantes_por_proprietario"] = {}
        ctx["segmentos_limites"] = []
        ctx["testada_principal"] = None

    # ------------------------------------------------------------------
    # 6) APP
    # ------------------------------------------------------------------
    app = analise.app
    ctx["ambiente"] = {
        "em_app": getattr(app, "em_app", None),
        "em_app_faixa_nuic": getattr(app, "em_app_faixa_nuic", None),
        "em_app_manguezal": getattr(app, "em_app_manguezal", None),
        "largura_faixa_m": getattr(app, "largura_faixa_m", None),
        "tipos_app": getattr(app, "tipos_app", []),
        "notas": getattr(app, "notas", []),
    }

    # ------------------------------------------------------------------
    # 7) Risco
    # ------------------------------------------------------------------
    risco = analise.risco
    ctx["risco"] = {
        "classe_inundacao": getattr(risco, "classe_inundacao", None),
        "classe_movimento_massa": getattr(risco, "classe_movimento_massa", None),
        "flags": getattr(risco, "flags", []),
        "notas": getattr(risco, "notas", []),
    }

    # ------------------------------------------------------------------
    # 8) Inclinação do terreno
    # ------------------------------------------------------------------
    if hasattr(analise, 'inclinacao') and analise.inclinacao is not None:
        inclinacao = analise.inclinacao
        ctx["inclinacao"] = {
            "faixas": [],
            "area_total_m2": 0.0,
            "area_app_inclinacao_m2": 0.0,
            "percentual_app_inclinacao": 0.0,
            "tem_app_por_inclinacao": False,
            "mensagens": ["Análise de inclinação realizada"],
            "em_analise": True
        }

        if hasattr(inclinacao, 'faixas'):
            ctx["inclinacao"]["faixas"] = _processar_faixas_inclinacao(inclinacao.faixas)
            ctx["inclinacao"]["area_total_m2"] = float(getattr(inclinacao, 'area_total_m2', 0))
            ctx["inclinacao"]["area_app_inclinacao_m2"] = float(getattr(inclinacao, 'area_app_inclinacao_m2', 0))
            ctx["inclinacao"]["percentual_app_inclinacao"] = float(getattr(inclinacao, 'percentual_app_inclinacao', 0))
            ctx["inclinacao"]["tem_app_por_inclinacao"] = bool(getattr(inclinacao, 'tem_app_por_inclinacao', False))
            mensagens = getattr(inclinacao, 'mensagens', [])
            if mensagens:
                ctx["inclinacao"]["mensagens"] = mensagens
        elif isinstance(inclinacao, dict):
            ctx["inclinacao"]["faixas"] = _processar_faixas_inclinacao(inclinacao.get('faixas', []))
            ctx["inclinacao"].update({
                "area_total_m2": float(inclinacao.get('area_total_m2', 0)),
                "area_app_inclinacao_m2": float(inclinacao.get('area_app_inclinacao_m2', 0)),
                "percentual_app_inclinacao": float(inclinacao.get('percentual_app_inclinacao', 0)),
                "tem_app_por_inclinacao": bool(inclinacao.get('tem_app_por_inclinacao', False)),
                "mensagens": inclinacao.get('mensagens', ["Análise de inclinação realizada"])
            })
    else:
        ctx["inclinacao"] = {
            "faixas": [],
            "area_total_m2": 0.0,
            "area_app_inclinacao_m2": 0.0,
            "percentual_app_inclinacao": 0.0,
            "tem_app_por_inclinacao": False,
            "mensagens": ["Não foi possível analisar a inclinação do terreno"],
            "em_analise": False
        }

    # ------------------------------------------------------------------
    # 9) Área da gleba unificada (para relatório, se existir)
    # ------------------------------------------------------------------
    ctx["area_gleba_unificada"] = getattr(analise, "area_gleba_unificada", None)

    return ctx


class ConstrutorRelatorio:
    """Fachada simples para construção de relatórios."""
    def __init__(self):
        pass
    def construir(self, dados_lote, analise):
        return construir_contexto_relatorio(dados_lote, analise)