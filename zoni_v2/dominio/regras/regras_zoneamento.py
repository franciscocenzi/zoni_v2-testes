"""Regras de zoneamento urbano – LC 275/2025 (núcleo do Zôni v2)."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List

import json


@dataclass
class ParametrosZona:
    codigo: str

    CA_min: Optional[float] = None
    CA_bas: Optional[float] = None
    CA_max: Optional[float] = None

    Tperm: Optional[float] = None
    Tocup: Optional[float] = None

    Npav_bas: Optional[int] = None
    Npav_max: Optional[int] = None

    Gab_bas: Optional[float] = None
    Gab_max: Optional[float] = None

    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoAvaliacaoZona:
    zona: str
    parametros: ParametrosZona
    conforme: bool
    pendencias: List[str] = field(default_factory=list)
    observacoes: List[str] = field(default_factory=list)
    valores_calculados: Dict[str, Any] = field(default_factory=dict)


def carregar_parametros_de_arquivo(caminho_json: str) -> Dict[str, ParametrosZona]:
    with open(caminho_json, "r", encoding="utf-8") as f:
        bruto = json.load(f)

    parametros_por_zona = {}

    for codigo, dados in bruto.items():
        indices = dados.get("indices", {}) or {}

        def _conv(valor):
            if isinstance(valor, str):
                v = valor.strip().replace(".", "").replace(",", ".")
                try:
                    return float(v)
                except Exception:
                    return None
            return valor

        p = ParametrosZona(
            codigo=codigo,
            CA_min=_conv(indices.get("CA_min")),
            CA_bas=_conv(indices.get("CA_bas")),
            CA_max=_conv(indices.get("CA_max")),
            Tperm=_conv(indices.get("Tperm")),
            Tocup=_conv(indices.get("Tocup")),
            Npav_bas=int(indices["Npav_bas"]) if "Npav_bas" in indices and indices["Npav_bas"] is not None else None,
            Npav_max=int(indices["Npav_max"]) if "Npav_max" in indices and indices["Npav_max"] is not None else None,
            Gab_bas=_conv(indices.get("Gab_bas")),
            Gab_max=_conv(indices.get("Gab_max")),
            extras={k: v for k, v in indices.items() if k not in {
                "CA_min", "CA_bas", "CA_max", "Tperm", "Tocup",
                "Npav_bas", "Npav_max", "Gab_bas", "Gab_max",
            }},
        )
        parametros_por_zona[codigo] = p

    return parametros_por_zona


def avaliar_edificacao_na_zona(
    zona: str,
    parametros: ParametrosZona,
    area_lote_m2: float,
    area_construida_total_m2: Optional[float] = None,
    area_ocupada_projecao_m2: Optional[float] = None,
    area_permeavel_m2: Optional[float] = None,
    altura_maxima_m: Optional[float] = None,
    numero_pavimentos: Optional[int] = None,
) -> ResultadoAvaliacaoZona:
    pendencias: List[str] = []
    observacoes: List[str] = []
    valores: Dict[str, Any] = {}

    if area_lote_m2 <= 0:
        raise ValueError("Área do lote deve ser maior que zero.")

    if area_construida_total_m2 is not None:
        ca_real = area_construida_total_m2 / area_lote_m2
        valores["CA_real"] = ca_real

        if parametros.CA_min is not None and ca_real < parametros.CA_min - 1e-6:
            pendencias.append(
                f"CA real ({ca_real:.2f}) inferior ao CA mínimo ({parametros.CA_min:.2f}) da zona {zona}."
            )
        if parametros.CA_max is not None and ca_real > parametros.CA_max + 1e-6:
            pendencias.append(
                f"CA real ({ca_real:.2f}) superior ao CA máximo ({parametros.CA_max:.2f}) da zona {zona}."
            )
    else:
        observacoes.append("CA não avaliado: área construída total não informada.")

    if area_ocupada_projecao_m2 is not None:
        tocup_real = area_ocupada_projecao_m2 / area_lote_m2
        valores["Tocup_real"] = tocup_real
        if parametros.Tocup is not None and tocup_real > parametros.Tocup + 1e-6:
            pendencias.append(
                f"Taxa de ocupação real ({tocup_real:.2%}) superior à máxima ({parametros.Tocup:.2%}) da zona {zona}."
            )
    else:
        observacoes.append(
            "Taxa de ocupação não avaliada: área ocupada em projeção não informada."
        )

    if area_permeavel_m2 is not None:
        tperm_real = area_permeavel_m2 / area_lote_m2
        valores["Tperm_real"] = tperm_real
        if parametros.Tperm is not None and tperm_real + 1e-6 < parametros.Tperm:
            pendencias.append(
                f"Taxa de permeabilidade real ({tperm_real:.2%}) inferior à mínima ({parametros.Tperm:.2%}) da zona {zona}."
            )
    else:
        observacoes.append(
            "Taxa de permeabilidade não avaliada: área permeável não informada."
        )

    if numero_pavimentos is not None:
        valores["Npav_real"] = numero_pavimentos
        if parametros.Npav_max is not None and numero_pavimentos > parametros.Npav_max:
            pendencias.append(
                f"Número de pavimentos ({numero_pavimentos}) superior ao máximo ({parametros.Npav_max}) da zona {zona}."
            )
    else:
        observacoes.append(
            "Número de pavimentos não informado; não foi possível avaliar limite máximo."
        )

    if altura_maxima_m is not None:
        valores["Gab_real"] = altura_maxima_m
        if parametros.Gab_max is not None and altura_maxima_m > parametros.Gab_max + 0.01:
            pendencias.append(
                f"Altura máxima ({altura_maxima_m:.2f} m) superior ao gabarito máximo ({parametros.Gab_max:.2f} m) da zona {zona}."
            )
    else:
        observacoes.append(
            "Altura máxima não informada; não foi possível avaliar gabarito."
        )

    conforme = len(pendencias) == 0

    return ResultadoAvaliacaoZona(
        zona=zona,
        parametros=parametros,
        conforme=conforme,
        pendencias=pendencias,
        observacoes=observacoes,
        valores_calculados=valores,
    )

class RegrasZoneamento:
    """Fachada para regras de zoneamento."""

    def carregar_parametros(self, caminho_json: str):
        return carregar_parametros_de_arquivo(caminho_json)

    def avaliar(
        self,
        zona: str,
        parametros: ParametrosZona,
        area_lote_m2: float,
        area_construida_total_m2=None,
        area_ocupada_projecao_m2=None,
        area_permeavel_m2=None,
        altura_maxima_m=None,
        numero_pavimentos=None,
    ):
        return avaliar_edificacao_na_zona(
            zona,
            parametros,
            area_lote_m2,
            area_construida_total_m2,
            area_ocupada_projecao_m2,
            area_permeavel_m2,
            altura_maxima_m,
            numero_pavimentos,
        )
