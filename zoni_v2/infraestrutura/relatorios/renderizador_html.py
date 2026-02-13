"""Renderização HTML baseada em template para o relatório Zôni v2."""

import os
import json
from typing import Dict, Any, List, Union
from datetime import datetime


def _esc(valor: Any) -> str:
    if valor is None:
        return "-"
    return str(valor)


def _format_float(value: Any, decimals: int = 2) -> str:
    try:
        if value is None:
            return "-"
        if isinstance(value, str):
            s = value.strip().replace(".", "").replace(",", ".")
            value = s
        f = float(value)
        return f"{f:.{decimals}f}"
    except Exception:
        return _esc(value)


def _carregar_template_html() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "modelos", "relatorio_completo.html")
    if not os.path.exists(template_path):
        template_path = os.path.join(base_dir, "relatorio_completo.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return (
            "<html><body>"
            "<h1>Relatório Zôni v2</h1>"
            "<p>Template não encontrado.</p>"
            "</body></html>"
        )


#def _agregar_dados_cadastrais(
#    ident: Union[Dict[str, Any], List[Dict[str, Any]]]
#    area_total_override: float = None
#
#) -> Dict[str, Any]:
#    """
#    Agrega dados cadastrais de um ou mais lotes.
#    Se area_total_override for fornecido (gleba), usa esse valor como área total,
#    ignorando a soma das áreas individuais.
#    """
def _agregar_dados_cadastrais(ident, area_total_override=None):
    """
    Agrega dados cadastrais de um ou mais lotes.
    - ident: dict ou lista de dicts com os dados de identificação.
    - area_total_override: se fornecido (float), usa este valor como área total,
      ignorando a soma das áreas individuais.
    Retorna um dict com 'linhas_html', 'area_total' e 'n_lotes'.
    """
    if isinstance(ident, dict):
        ident_list = [ident]
    elif isinstance(ident, list):
        ident_list = ident
    else:
        ident_list = []

    n_lotes = len(ident_list)

#    def collect(key: str) -> List[str]:
    def collect(key):
        vals = []
        for i in ident_list:
            v = i.get(key)
            if v not in (None, "", " "):
                vals.append(str(v))
        seen = set()
        uniq = []
        for v in vals:
            if v not in seen:
                seen.add(v)
                uniq.append(v)
        return uniq

    # Coleta todos os campos cadastrais
    proprietarios = collect("proprietario")
    inscricoes = collect("inscricao_imobiliaria")
    numeros_cadastrais = collect("numero_cadastral")
    matriculas = collect("matricula")
    bairros = collect("bairro")
    logradouros = collect("logradouro")
    numeros = collect("numero")
    loteamentos = collect("loteamento")
    quadras = collect("quadra")
    lotes = collect("lote")
    status = collect("status_imovel")
    observacoes = collect("observacoes_cadastrais")

    # Área total
    if area_total_override is not None:
        area_total = area_total_override
        tem_area = True
    else:
        area_total = 0.0
        tem_area = False
        for i in ident_list:
            v = i.get("area_m2")
            if v in (None, "", " "):
                continue
            tem_area = True
            try:
                area_total += float(v)
            except Exception:
                pass

    linhas = []

#    def add_row(label: str, valores: List[str]):
    def add_row(label, valores):
        texto = ", ".join(valores) if valores else "-"
        linhas.append(f"<tr><th>{_esc(label)}</th><td>{_esc(texto)}</td></tr>")

    add_row("Proprietário(s)", proprietarios)
    add_row("Inscrição(ões) imobiliária(s)", inscricoes)
    add_row("Número(s) cadastral(is)", numeros_cadastrais)
    add_row("Matrícula(s)", matriculas)
    add_row("Bairro(s)", bairros)
    add_row("Logradouro(s)", logradouros)
    add_row("Número(s)", numeros)
    add_row("Loteamento(s)", loteamentos)
    add_row("Quadra(s)", quadras)
    add_row("Lote(s)", lotes)
    add_row("Status do(s) imóvel(is)", status)
    add_row("Observações cadastrais", observacoes)

    if tem_area:
        linhas.append(
            "<tr><th>Área total do(s) lote(s) (m²)</th>"
            f"<td>{_format_float(area_total)}</td></tr>"
        )

    if not linhas:
        linhas.append("<tr><td colspan='2'>Sem dados cadastrais disponíveis.</td></tr>")

    return {
        "linhas_html": "\n".join(linhas),
        "area_total": area_total if tem_area else None,
        "n_lotes": n_lotes,
    }


def _montar_tabela_testadas(contexto: Dict[str, Any]) -> (str, str):
    """Monta HTML da TABELA_TESTADAS e retorna também N_TESTADAS."""
    testadas = contexto.get("testadas_por_logradouro") or {}
    confrontantes = contexto.get("confrontantes_por_proprietario") or {}
    segmentos = contexto.get("segmentos_limites") or []

    linhas = []
    usou_agregado = False

    if isinstance(testadas, dict) and testadas:
        usou_agregado = True
        linhas.append("<tr><td colspan='2'><strong>Testadas por logradouro</strong></td></tr>")
        for log, ext in testadas.items():
            linhas.append(f"<tr><td>{_esc(log)}</td><td>{_format_float(ext)}</td></tr>")

    if isinstance(confrontantes, dict) and confrontantes:
        usou_agregado = True
        if linhas:
            linhas.append("<tr><td colspan='2' style='padding-top:8px;'><strong>Divisas por confrontante</strong></td></tr>")
        else:
            linhas.append("<tr><td colspan='2'><strong>Divisas por confrontante</strong></td></tr>")
        for prop, ext in confrontantes.items():
            linhas.append(f"<tr><td>{_esc(prop)}</td><td>{_format_float(ext)}</td></tr>")

    if not usou_agregado and isinstance(segmentos, list) and segmentos:
        for seg in segmentos:
            tipo = (seg.get("tipo_limite") or "").upper()
            log = seg.get("logradouro") or ""
            conf = seg.get("confrontante") or ""
            comp = seg.get("comprimento_m")

            if tipo == "TESTADA":
                desc = f"TESTADA para {_esc(log)}" if log else "TESTADA"
            else:
                desc = f"DIVISA com {_esc(conf)}" if conf else "DIVISA"
            linhas.append(f"<tr><td>{desc}</td><td>{_format_float(comp)}</td></tr>")

    n_testadas = "-"
    if isinstance(segmentos, list) and segmentos:
        n = sum(1 for s in segmentos if (s.get("tipo_limite") or "").upper() == "TESTADA")
        if n > 0:
            n_testadas = str(n)
    elif isinstance(testadas, dict) and testadas:
        n_testadas = str(len(testadas))

    if not linhas:
        linhas.append("<tr><td>-</td><td>-</td></tr>")

    return "\n".join(linhas), n_testadas


def _montar_tabela_zonas(contexto: Dict[str, Any], area_total: Any) -> (str, str, str):
    """Monta HTML da tabela de zonas e retorna (html, zona_principal, justificativa)."""
    zr = contexto.get("zoneamento_resolvido") or {}
    zonas_res = zr.get("zonas") or []

    if zonas_res:
        linhas = []
        multi = len(zonas_res) > 1

        if multi:
            linhas.append(
                "<tr><th>Zona</th><th>Área (m²)</th><th>Percentual (%)</th>"
                "<th>CA mín.</th><th>CA básico</th><th>CA máx.</th>"
                "<th>TPS</th><th>TOS</th><th>Pav. básico</th><th>Pav. máx.</th>"
                "<th>Gab. básico (m)</th><th>Gab. máx. (m)</th></tr>"
            )
        else:
            linhas.append("<tr><th>Zona</th><th>Área (m²)</th><th>Percentual (%)</th></tr>")

        for z in zonas_res:
            codigo = z.get("codigo")
            tipo = z.get("tipo")
            cod_fmt = _esc(codigo) + (f" ({_esc(tipo)})" if tipo else "")
            area = _format_float(z.get("area_m2"))
            perc = _format_float(z.get("percentual_area"), decimals=1)

            if multi:
                param = z.get("parametros") or {}
                linhas.append(
                    f"<tr><td>{cod_fmt}</td><td>{area}</td><td>{perc}</td>"
                    f"<td>{_format_float(param.get('CA_min'))}</td>"
                    f"<td>{_format_float(param.get('CA_bas'))}</td>"
                    f"<td>{_format_float(param.get('CA_max'))}</td>"
                    f"<td>{_format_float(param.get('Tperm'))}</td>"
                    f"<td>{_format_float(param.get('Tocup'))}</td>"
                    f"<td>{_esc(param.get('Npav_bas'))}</td>"
                    f"<td>{_esc(param.get('Npav_max'))}</td>"
                    f"<td>{_format_float(param.get('Gab_bas'))}</td>"
                    f"<td>{_format_float(param.get('Gab_max'))}</td></tr>"
                )
            else:
                linhas.append(f"<tr><td>{cod_fmt}</td><td>{area}</td><td>{perc}</td></tr>")

        zona_principal = zr.get("zona_referencia") or "-"
        resumo = zr.get("resumo") or ""
        observacoes = " ".join(_esc(o) for o in zr.get("observacoes") or [])
        justificativa = (resumo + " " + observacoes).strip() if resumo else observacoes
        if not justificativa:
            justificativa = "Coexistência de zonas incidentes conforme LC 275/2025 e anexos."
        return "\n".join(linhas), _esc(zona_principal), justificativa

    # Fallback
    zon = contexto.get("zoneamento", {}) or {}
    zona = zon.get("zona")

    if area_total not in (None, 0):
        area_str = _format_float(area_total)
        perc_str = "100"
    else:
        area_str = "-"
        perc_str = "-"

    linhas_fallback = ["<tr><th>Zona</th><th>Área (m²)</th><th>Percentual (%)</th></tr>"]
    if zona:
        linhas_fallback.append(f"<tr><td>{_esc(zona)}</td><td>{area_str}</td><td>{perc_str}</td></tr>")
        zona_principal = _esc(zona)
        msgs = "; ".join(_esc(m) for m in zon.get("mensagens") or [])
        justificativa = msgs or "Zona única incidente no(s) lote(s) considerado(s)."
    else:
        linhas_fallback.append("<tr><td>-</td><td>-</td><td>-</td></tr>")
        zona_principal = "-"
        justificativa = "Não foi possível identificar o zoneamento a partir dos dados fornecidos."

    return "\n".join(linhas_fallback), zona_principal, justificativa


def _montar_parametros_urbanisticos(contexto: Dict[str, Any]) -> Dict[str, str]:
    """Extrai parâmetros urbanísticos da chave 'indices'."""
    indices = contexto.get("indices")
    if not indices:
        return {k: "-" for k in ["CA_MIN", "CA_BAS", "CA_MAX_AJ", "TPS", "TOS",
                                  "RF", "RFU", "RL", "NP_BAS", "NP_MAX_AJ", "HEMB", "VAGAS"]}

    param = indices.get("parametros", {}) or {}
    extras = param.get("extras") or {}

    return {
        "CA_MIN": _format_float(param.get("CA_min")),
        "CA_BAS": _format_float(param.get("CA_bas")),
        "CA_MAX_AJ": _format_float(param.get("CA_max")),
        "TPS": _format_float(param.get("Tperm")),
        "TOS": _format_float(param.get("Tocup")),
        "RF": _esc(extras.get("RF")),
        "RFU": _esc(extras.get("RFU")),
        "RL": _esc(extras.get("RL") or extras.get("RLF")),
        "NP_BAS": _esc(param.get("Npav_bas")),
        "NP_MAX_AJ": _esc(param.get("Npav_max")),
        "HEMB": _esc(extras.get("HEMB") or extras.get("AEMax")),
        "VAGAS": _esc(extras.get("vagas_min") or extras.get("vagas")),
    }


def _montar_dados_app(contexto: Dict[str, Any]) -> Dict[str, str]:
    """Extrai dados de APP do contexto."""
    ambiente = contexto.get("ambiente", {})
    em_app_faixa = ambiente.get("em_app_faixa_nuic", False)
    em_app_mangue = ambiente.get("em_app_manguezal", False)
    largura = ambiente.get("largura_faixa_m")
    notas = ambiente.get("notas", [])

    return {
        "APP_FAIXA_STATUS": "Presente" if em_app_faixa else "Não identificada",
        "APP_FAIXA_CLASSE": "status-presente" if em_app_faixa else "status-ausente",
        "APP_FAIXA_LARGURA": f"{_format_float(largura)} m" if largura else "-",
        "APP_FAIXA_OBS": ("Área de APP em faixa de curso d'água." + (" " + "; ".join(notas[:2]) if notas else ""))
                         if em_app_faixa else "Sem APP de faixa de curso d'água identificada.",
        "APP_MANGUE_STATUS": "Presente" if em_app_mangue else "Não identificado",
        "APP_MANGUE_CLASSE": "status-presente" if em_app_mangue else "status-ausente",
        "APP_MANGUE_OBS": ("Área de APP de manguezal identificada." + (" " + "; ".join(notas[2:4]) if len(notas) > 2 else ""))
                          if em_app_mangue else "Sem APP de manguezal identificada.",
    }


def _montar_dados_risco(contexto: Dict[str, Any]) -> Dict[str, str]:
    """Extrai dados de Risco do contexto."""
    risco = contexto.get("risco", {})
    classe_inund = risco.get("classe_inundacao", "Não informada")
    classe_mov = risco.get("classe_movimento_massa", "Não informada")

    def classificar(classe):
        if not classe or classe in ["Não informada", "None", "null"]:
            return ("Não classificado", "status-ausente")
        s = str(classe).upper()
        if "ALTA" in s or "ALTO" in s or s in ("A", "4"):
            return ("ALTA", "status-alerta")
        if "MÉDIA" in s or "MEDIA" in s or s in ("M", "3"):
            return ("MÉDIA", "status-alerta")
        if "BAIXA" in s or "BAIXO" in s or s in ("B", "2"):
            return ("BAIXA", "status-presente")
        if "MUITO BAIXA" in s or "MB" in s or s == "1":
            return ("MUITO BAIXA", "status-presente")
        return (s, "status-ausente")

    grau_inund, cor_inund = classificar(classe_inund)
    grau_mov, cor_mov = classificar(classe_mov)

    return {
        "RISCO_INUND_CLASSE": _esc(classe_inund),
        "RISCO_INUND_GRAU": grau_inund,
        "RISCO_INUND_COR": cor_inund,
        "RISCO_INUND_RECOM": _obter_recomendacao_inundacao(classe_inund),
        "RISCO_MOV_CLASSE": _esc(classe_mov),
        "RISCO_MOV_GRAU": grau_mov,
        "RISCO_MOV_COR": cor_mov,
        "RISCO_MOV_RECOM": _obter_recomendacao_movimento(classe_mov),
    }


def _obter_recomendacao_inundacao(classe: str) -> str:
    if not classe or classe in ["Não informada", "None", "null"]:
        return "Sem informações suficientes para recomendações específicas."
    s = str(classe).upper()
    if "ALTA" in s:
        return "Requer Estudo Hidrológico e Hidráulico (EHH) detalhado. Considerar elevação do nível de piso."
    if "MÉDIA" in s or "MEDIA" in s:
        return "Recomenda-se análise hidrológica preliminar. Dimensionar drenagem para evento de 50 anos."
    if "BAIXA" in s or "BAIXO" in s:
        return "Sistema de drenagem convencional geralmente adequado."
    return "Sem recomendações específicas."


def _obter_recomendacao_movimento(classe: str) -> str:
    if not classe or classe in ["Não informada", "None", "null"]:
        return "Sem informações suficientes para recomendações específicas."
    s = str(classe).upper()
    if "ALTA" in s:
        return "Requer Estudo Geotécnico completo e projeto de contenção. Monitoramento obrigatório."
    if "MÉDIA" in s or "MEDIA" in s:
        return "Recomenda-se investigação geotécnica preliminar. Avaliar inclinação e tipo de solo."
    if "BAIXA" in s or "BAIXO" in s:
        return "Procedimentos geotécnicos padrão geralmente suficientes."
    return "Sem recomendações específicas."


def _montar_tabela_inclinacao(contexto: Dict[str, Any]) -> str:
    """Monta HTML da tabela de inclinação do terreno."""
    inclinacao = contexto.get("inclinacao", {})
    if not inclinacao:
        return "<tr><td colspan='5'>Análise de inclinação não disponível.</td></tr>"

    faixas = inclinacao.get("faixas", [])
    if not faixas:
        msg = inclinacao.get("mensagem", "Não foi possível analisar a inclinação do terreno.")
        return f"<tr><td colspan='5'>{_esc(msg)}</td></tr>"

    linhas = []
    for faixa in faixas:
        faixa_desc = faixa.get("faixa", "")
        cor = faixa.get("cor", "#FFFFFF")
        area_m2 = faixa.get("area_m2", 0.0)
        percentual = faixa.get("percentual", 0.0)
        app = faixa.get("app", False)
        app_flag = '<span class="app-flag">APP</span>' if app else ''
        cor_cell = f'<div class="inclinacao-cor" style="background-color:{cor};"></div>'
        linhas.append(
            f"<tr><td>{_esc(faixa_desc)}</td><td>{cor_cell}</td>"
            f"<td>{_format_float(area_m2)}</td><td>{_format_float(percentual, decimals=2)}%</td>"
            f"<td>{app_flag}</td></tr>"
        )

    area_app = inclinacao.get("area_app_inclinacao_m2", 0.0)
    perc_app = inclinacao.get("percentual_app_inclinacao", 0.0)
    if inclinacao.get("tem_app_por_inclinacao", False) and area_app > 0:
        linhas.append(
            f"<tr style='background-color:#f9f9f9;font-weight:bold;'>"
            f"<td colspan='2' style='text-align:right;'>Área total APP por inclinação (>45°):</td>"
            f"<td>{_format_float(area_app)}</td><td>{_format_float(perc_app, decimals=2)}%</td>"
            f"<td><span class='app-flag'>APP</span></td></tr>"
        )

    return "\n".join(linhas)


def _montar_listas_notas_separadas(contexto: Dict[str, Any]) -> Dict[str, str]:
    """Compila notas/condicionantes separadas por categoria."""
    todas = []

    # Zoneamento
    zon = contexto.get("zoneamento", {})
    todas.extend(zon.get("mensagens", []))
    zr = contexto.get("zoneamento_resolvido", {})
    if zr.get("resumo"):
        todas.append(zr["resumo"])
    todas.extend(zr.get("observacoes", []))
    if zr.get("notas_ativas"):
        todas.append(f"Notas ativas do Anexo III: {', '.join(zr['notas_ativas'])}")

    # Índices
    idx = contexto.get("indices", {})
    todas.extend(idx.get("pendencias", []))
    todas.extend(idx.get("observacoes", []))

    # APP
    amb = contexto.get("ambiente", {})
    todas.extend(amb.get("notas", []))

    # Risco
    risco = contexto.get("risco", {})
    todas.extend(risco.get("notas", []))

    # Inclinação
    inc = contexto.get("inclinacao", {})
    if isinstance(inc, dict):
        todas.extend(inc.get("mensagens", []))
        if inc.get("tem_app_por_inclinacao", False):
            area = inc.get("area_app_inclinacao_m2", 0.0)
            perc = inc.get("percentual_app_inclinacao", 0.0)
            todas.append(f"APP por inclinação do terreno (>45°): {_format_float(area)} m² ({_format_float(perc, decimals=2)}% da área).")

    # Remove duplicados
    unicas = []
    vistas = set()
    for n in todas:
        if n and n not in vistas:
            vistas.add(n)
            unicas.append(n)

    # Classificação
    anexo, cond, restr = [], [], []
    for n in unicas:
        nl = str(n).lower()
        if any(p in nl for p in ["nota", "anexo iii", "anexo 3", "zeot2", "muq3", "10", "37"]):
            anexo.append(n)
        elif any(p in nl for p in ["condicionante", "recomenda", "sugere", "aconselha", "observa"]):
            cond.append(n)
        elif any(p in nl for p in ["restri", "proibi", "impede", "penden", "problema", "erro", "falta", "inviá"]):
            restr.append(n)
        else:
            cond.append(n)

    def list_to_html(itens, padrao):
        if not itens:
            return f"<li>{padrao}</li>"
        return "\n".join(f"<li>{_esc(i)}</li>" for i in itens)

    return {
        "LISTA_NOTAS_ANEXO": list_to_html(anexo, "Nenhuma nota técnica específica aplicada."),
        "LISTA_CONDICIONANTES": list_to_html(cond, "Nenhuma condicionante identificada."),
        "LISTA_RESTRICOES": list_to_html(restr, "Nenhuma restrição crítica identificada."),
        "LISTA_NOTAS": list_to_html(unicas, "Nenhuma nota ou condicionante registrada."),
    }


def gerar_html_basico(contexto: Dict[str, Any]) -> str:
    """Gera o HTML final do relatório a partir do contexto."""
    template = _carregar_template_html()

#    ident = contexto.get("identificacao") or {}
#    dados_cad = _agregar_dados_cadastrais(ident)
#    linhas_cadastrais = dados_cad["linhas_html"]
#    area_total = dados_cad["area_total"]
#    n_lotes = dados_cad.get("n_lotes", 0)
    ident = contexto.get("identificacao") or {}
    # Se for gleba e existir área unificada no contexto, usa como override
    area_gleba = contexto.get("area_gleba_unificada")
    dados_cad = _agregar_dados_cadastrais(ident, area_total_override=area_gleba)
    linhas_cadastrais = dados_cad["linhas_html"]
    area_total = dados_cad["area_total"]
    n_lotes = dados_cad.get("n_lotes", 0)

    tabela_testadas_html, n_testadas = _montar_tabela_testadas(contexto)
    tabela_zonas_html, zona_principal, justificativa = _montar_tabela_zonas(contexto, area_total)
    tabela_inclinacao_html = _montar_tabela_inclinacao(contexto)

    params_urb = _montar_parametros_urbanisticos(contexto)
    listas_notas = _montar_listas_notas_separadas(contexto)

    testada_principal = contexto.get("testada_principal") or "-"

    if area_total not in (None, 0):
        area_lote_str = _format_float(area_total)
    else:
        base = ident[0] if isinstance(ident, list) and ident else ident
        area_lote_str = _format_float(base.get("area_m2") if base else None)

    tipo_analise = "Lote único" if n_lotes <= 1 else f"Gleba / conjunto de {n_lotes} lotes contíguos"
    n_lotes_str = str(n_lotes) if n_lotes > 0 else "1"

    dados_app = _montar_dados_app(contexto)
    dados_risco = _montar_dados_risco(contexto)

    agora = datetime.now()
    data_completa = agora.strftime("%d/%m/%Y")
    hora = agora.strftime("%H:%M")

    try:
        debug_ctx = json.dumps(contexto, ensure_ascii=False, indent=2)
        debug_ctx_html = "<pre>" + debug_ctx.replace("<", "&lt;") + "</pre>"
    except Exception:
        debug_ctx_html = "<pre>" + _esc(contexto) + "</pre>"

    placeholders = {
        "DADOS_CADASTRAIS": linhas_cadastrais,
        "AREA_LOTE": area_lote_str,
        "N_TESTADAS": n_testadas,
        "TABELA_TESTADAS": tabela_testadas_html,
        "TABELA_ZONAS": tabela_zonas_html,
        "ZONA_PRINCIPAL": zona_principal,
        "JUSTIFICATIVA": justificativa,
        "CA_MIN": params_urb["CA_MIN"],
        "CA_BAS": params_urb["CA_BAS"],
        "CA_MAX_AJ": params_urb["CA_MAX_AJ"],
        "TPS": params_urb["TPS"],
        "TOS": params_urb["TOS"],
        "RF": params_urb["RF"],
        "RFU": params_urb["RFU"],
        "RL": params_urb["RL"],
        "NP_BAS": params_urb["NP_BAS"],
        "NP_MAX_AJ": params_urb["NP_MAX_AJ"],
        "HEMB": params_urb["HEMB"],
        "VAGAS": params_urb["VAGAS"],
        "LISTA_NOTAS": listas_notas["LISTA_NOTAS"],
        "LISTA_NOTAS_ANEXO": listas_notas["LISTA_NOTAS_ANEXO"],
        "LISTA_CONDICIONANTES": listas_notas["LISTA_CONDICIONANTES"],
        "LISTA_RESTRICOES": listas_notas["LISTA_RESTRICOES"],
        "TIPO_ANALISE": tipo_analise,
        "N_LOTES": n_lotes_str,
        "TESTADA_PRINCIPAL": _esc(testada_principal),
        "APP_FAIXA_STATUS": dados_app["APP_FAIXA_STATUS"],
        "APP_FAIXA_CLASSE": dados_app["APP_FAIXA_CLASSE"],
        "APP_FAIXA_LARGURA": dados_app["APP_FAIXA_LARGURA"],
        "APP_FAIXA_OBS": dados_app["APP_FAIXA_OBS"],
        "APP_MANGUE_STATUS": dados_app["APP_MANGUE_STATUS"],
        "APP_MANGUE_CLASSE": dados_app["APP_MANGUE_CLASSE"],
        "APP_MANGUE_OBS": dados_app["APP_MANGUE_OBS"],
        "RISCO_INUND_CLASSE": dados_risco["RISCO_INUND_CLASSE"],
        "RISCO_INUND_GRAU": dados_risco["RISCO_INUND_GRAU"],
        "RISCO_INUND_COR": dados_risco["RISCO_INUND_COR"],
        "RISCO_INUND_RECOM": dados_risco["RISCO_INUND_RECOM"],
        "RISCO_MOV_CLASSE": dados_risco["RISCO_MOV_CLASSE"],
        "RISCO_MOV_GRAU": dados_risco["RISCO_MOV_GRAU"],
        "RISCO_MOV_COR": dados_risco["RISCO_MOV_COR"],
        "RISCO_MOV_RECOM": dados_risco["RISCO_MOV_RECOM"],
        "TABELA_INCLINACAO": tabela_inclinacao_html,
        "DATA_COMPLETA": data_completa,
        "HORA": hora,
        "VERSAO": "2.0.0.005",
        "DEBUG_CTX": debug_ctx_html,
    }

    html = template
    for chave, valor in placeholders.items():
        placeholder = "{" + chave + "}"
        html = html.replace(placeholder, valor if valor is not None else "-")

    html = html.replace("{if ", "<!-- if ").replace("{endif}", "-->")
    return html


class RenderizadorHTML:
    """Fachada para geração de HTML. Redireciona para a função principal."""
    def gerar_html_basico(self, contexto: dict) -> str:
        from .renderizador_html import gerar_html_basico as gerar_relatorio_completo
        return gerar_relatorio_completo(contexto)