# -*- coding: utf-8 -*-
"""Utilitários para gerenciamento de caminhos de arquivos."""

import os

def obter_caminho_parametros(base_dir: str) -> str:
    """Obtém o caminho do arquivo de parâmetros de zoneamento."""
    return os.path.join(
        base_dir,
        "infraestrutura",
        "dados",
        "parametros_zoneamento.json"
    )

def obter_caminho_template(base_dir: str) -> str:
    """Obtém o caminho do template HTML."""
    return os.path.join(
        base_dir,
        "infraestrutura",
        "relatorios",
        "templates",
        "relatorio_completo.html"
    )