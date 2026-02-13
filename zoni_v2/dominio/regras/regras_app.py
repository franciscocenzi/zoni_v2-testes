"""Regras de interpretação para APP com base em LLNUIAPP e manguezal."""

from dataclasses import dataclass, field
from typing import List

from ...infraestrutura.espacial.intersecao_app import ResultadoAPP


@dataclass
class ResultadoRegrasAPP:
    pendencias: List[str] = field(default_factory=list)
    observacoes: List[str] = field(default_factory=list)
    observacoes_legais: List[str] = field(default_factory=list)


def aplicar_regras_app(res_app: ResultadoAPP) -> ResultadoRegrasAPP:
    r = ResultadoRegrasAPP()

    if not res_app.em_app:
        r.observacoes.append(
            "Não foi identificada incidência de APP (faixa AUC ou manguezal) "
            "nas camadas de referência AMFRI para o lote analisado."
        )
        return r

    if res_app.em_app_faixa_auc:
        txt = (
            "O lote está total ou parcialmente inserido em faixa marginal de curso d'água "
            "delimitada na camada AMFRI_PB_LLNUIAPP, correspondente às diretrizes de "
            "APP em área urbana consolidada. A ocupação, ampliação ou regularização "
            "nesta faixa depende de análise específica à luz da legislação federal "
            "aplicável e da legislação municipal."
        )
        r.pendencias.append(txt)
        if res_app.largura_faixa_m is not None:
            r.observacoes.append(
                f"Largura de faixa registrada na feição intersectante: "
                f"{res_app.largura_faixa_m:.2f} m (valor a conferir na base de dados)."
            )

    if res_app.em_app_manguezal:
        txt = (
            "O lote intersecta área cadastrada como APP de manguezal, categoria que "
            "possui proteção ambiental reforçada. Intervenções nessa área são "
            "severamente restritas, devendo ser analisadas conforme legislação "
            "ambiental federal e estadual vigente, além da legislação municipal."
        )
        r.pendencias.append(txt)

    r.observacoes_legais.append(
        "A classificação em APP em área urbana consolidada e as faixas de proteção "
        "decorrem da combinação entre legislação federal sobre APP em meio urbano, "
        "legislação de parcelamento do solo e normas municipais específicas. O "
        "presente relatório utiliza como referência as camadas oficiais fornecidas "
        "pela AMFRI e o mapeamento municipal."
    )

    return r

class RegrasAPP:
    """Fachada para regras de APP."""

    def aplicar(self, res_app: ResultadoAPP):
        return aplicar_regras_app(res_app)
