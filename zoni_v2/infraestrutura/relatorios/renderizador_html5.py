"""Renderização do relatório final em HTML."""

import os
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

# Importar template HTML
def carregar_template_html() -> str:
    """Carrega o template HTML do relatório."""
    # Tenta encontrar o template em diferentes locais
    possiveis_caminhos = [
        # Caminho relativo ao plugin
        Path(__file__).parent / "templates" / "relatorio.html",
        Path(__file__).parent / "relatorio_template.html",
        Path(__file__).parent.parent / "templates" / "relatorio.html",
        # Caminho absoluto (para debug)
        Path(r"C:\Users\franciscore\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\zoni\templates\relatorio.html"),
    ]
    
    for caminho in possiveis_caminhos:
        if caminho.exists():
            try:
                with open(caminho, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                print(f"ERRO ao carregar template {caminho}: {e}")
                continue
    
    # Se não encontrar o template, retorna um template mínimo
    print("AVISO: Template HTML não encontrado, usando template mínimo")
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Relatório Zôni v2</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .section { margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 8px; border: 1px solid #ddd; text-align: left; }
            .app-flag { background-color: #d7191c; color: white; padding: 2px 6px; border-radius: 3px; }
            .inclinacao-cor { width: 20px; height: 20px; display: inline-block; margin-right: 8px; border: 1px solid #ccc; }
        </style>
    </head>
    <body>
        <h1>Relatório de Análise Urbanística - Zôni v2</h1>
        <p>Gerado em: {DATA_COMPLETA} às {HORA}</p>
        
        <!-- Seção de Inclinação -->
        <div class="section">
            <h2>Inclinação do Terreno</h2>
            <table>
                <tr>
                    <th width="30%">Faixa de Inclinação</th>
                    <th width="15%">Cor</th>
                    <th width="20%">Área (m²)</th>
                    <th width="15%">% da Área</th>
                    <th width="20%">Status APP</th>
                </tr>
                {TABELA_INCLINACAO}
            </table>
        </div>
        
        <!-- Debug info -->
        <div class="section">
            <h2>Informações de Debug</h2>
            <pre>{DEBUG_INFO}</pre>
        </div>
    </body>
    </html>
    """


def gerar_tabela_inclinacao(ctx: Dict[str, Any]) -> str:
    """Gera HTML para a tabela de inclinação do terreno."""
    
    inclinacao = ctx.get("inclinacao", {})
    faixas = inclinacao.get("faixas", [])
    mensagens = inclinacao.get("mensagens", [])
    
    print(f"DEBUG gerar_tabela_inclinacao: {len(faixas)} faixas encontradas")
    print(f"DEBUG gerar_tabela_inclinacao: Mensagens: {mensagens}")
    
    # Se não há faixas, mostrar mensagem de erro
    if not faixas:
        mensagem = mensagens[0] if mensagens else "Não foi possível analisar a inclinação do terreno"
        print(f"DEBUG gerar_tabela_inclinacao: Sem faixas, mostrando mensagem: {mensagem}")
        return f'''
            <tr>
                <td colspan="5" style="text-align: center; padding: 20px; color: #666;">
                    <strong>{mensagem}</strong><br>
                    <small>Camada de inclinação não disponível ou lote fora da área coberta.</small>
                </td>
            </tr>
        '''
    
    linhas = []
    for i, faixa in enumerate(faixas):
        cor = faixa.get('cor', '#cccccc')
        label = faixa.get('faixa', f'Faixa {i+1}')
        area_m2 = float(faixa.get('area_m2', 0.0))
        percentual = float(faixa.get('percentual', 0.0))
        is_app = bool(faixa.get('app', False))
        
        status_app = '<span class="app-flag">APP</span>' if is_app else '-'
        
        linha = f'''
            <tr>
                <td>{label}</td>
                <td><div class="inclinacao-cor" style="background-color: {cor};"></div></td>
                <td>{area_m2:.2f}</td>
                <td>{percentual:.2f}%</td>
                <td>{status_app}</td>
            </tr>
        '''
        linhas.append(linha)
        print(f"DEBUG gerar_tabela_inclinacao: Faixa {i+1}: {label}, {area_m2:.2f} m², APP: {is_app}")
    
    # Adicionar linha de total
    area_total = float(inclinacao.get("area_total_m2", 0.0))
    if area_total > 0:
        linhas.append(f'''
            <tr style="font-weight: bold; background-color: #f9f9f9;">
                <td>TOTAL ANALISADO</td>
                <td></td>
                <td>{area_total:.2f}</td>
                <td>100.00%</td>
                <td></td>
            </tr>
        ''')
    
    # Adicionar linha de APP se houver
    area_app = float(inclinacao.get("area_app_inclinacao_m2", 0.0))
    percentual_app = float(inclinacao.get("percentual_app_inclinacao", 0.0))
    
    if area_app > 0:
        linhas.append(f'''
            <tr style="font-weight: bold; background-color: #ffebee;">
                <td colspan="2">Área de APP por inclinação (>45°)</td>
                <td>{area_app:.2f}</td>
                <td>{percentual_app:.2f}%</td>
                <td><span class="app-flag">APP</span></td>
            </tr>
        ''')
        print(f"DEBUG gerar_tabela_inclinacao: APP detectada: {area_app:.2f} m² ({percentual_app:.2f}%)")
    
    return '\n'.join(linhas)


def gerar_html_basico(ctx: Dict[str, Any], template_html: str = None) -> str:
    """
    Substitui as marcações { ... } no template pelo conteúdo de ctx.
    
    Args:
        ctx: Contexto com dados do relatório
        template_html: Template HTML (opcional, carrega automaticamente se None)
    """
    
    # Carregar template se não fornecido
    if template_html is None:
        template_html = carregar_template_html()
    
    # Processar dados de inclinação
    tabela_inclinacao = gerar_tabela_inclinacao(ctx)
    
    # Data e hora atual
    agora = datetime.now()
    
    # Substituições principais
    substituicoes = {
        "{TABELA_INCLINACAO}": tabela_inclinacao,
        "{DATA_COMPLETA}": agora.strftime("%d/%m/%Y"),
        "{HORA}": agora.strftime("%H:%M"),
        "{VERSAO}": "2.0.0",
        "{TIPO_ANALISE}": "Lote único",
        "{DEBUG_INFO}": str(ctx.get("inclinacao", {}))[:500],  # Debug info limitada
    }
    
    # Substituições para dados cadastrais
    identificacao = ctx.get("identificacao", {})
    if isinstance(identificacao, list) and identificacao:
        identificacao = identificacao[0]
    
    substituicoes.update({
        "{AREA_LOTE}": f"{identificacao.get('area_m2', 0):.2f}" if identificacao else "0.00",
        "{N_LOTES}": "1",
        "{N_TESTADAS}": str(len(ctx.get("testadas_por_logradouro", {}))),
        "{TESTADA_PRINCIPAL}": ctx.get("testada_principal", "Não identificada"),
    })
    
    # Adicionar substituições para outras seções do seu template original
    # ... (adicione aqui as outras substituições do seu template)
    
    # Aplicar substituições no template
    html = template_html
    for key, value in substituicoes.items():
        html = html.replace(key, str(value))
    
    print(f"DEBUG gerar_html_basico: Template processado com {len(substituicoes)} substituições")
    return html


# Função de conveniência para usar com apenas o contexto
def gerar_relatorio(ctx: Dict[str, Any]) -> str:
    """Função simplificada que carrega o template automaticamente."""
    return gerar_html_basico(ctx)