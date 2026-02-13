# -*- coding: utf-8 -*-
"""
Cálculo de limites, testadas e associação a logradouros para o Zôni v2.

Este módulo contém a lógica de:

- segmentar a borda do lote/gleba em LIMITES (arestas do polígono);
- identificar quais LIMITES são TESTADAS (limites com frente para
  logradouro público: rua, avenida, servidão, praça, largo etc.);
- identificar quais LIMITES são DIVISAS (limites em confrontação com
  outros lotes, públicos ou privados);
- associar a cada TESTADA o respectivo logradouro; e
- associar a cada DIVISA o respectivo confrontante, utilizando o campo
  "proprietário" (ou similar) da camada de lotes.

Pressupõe que:
- o lote está em um CRS métrico (ex.: SIRGAS 2000 / UTM);
- as camadas de lotes e logradouros usam o mesmo CRS.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from qgis.core import (
    QgsVectorLayer,
    QgsGeometry,
    QgsPointXY,
    QgsSpatialIndex,
)

# Distância padrão máxima do "raio" lançado para tentar encontrar o logradouro
DEFAULT_MAX_DIST_TESTADA_M = 20.0


# ----------------------------------------------------------------------
# Estruturas de dados
# ----------------------------------------------------------------------


@dataclass
class SegmentoTestada:
    """
    Representa um segmento de LIMITE do terreno.

    Conceitos:
    - Limite: aresta do perímetro do lote/gleba.
    - Testada: limite que tem frente para logradouro público.
    - Divisa: limite em confrontação com outro lote (público ou privado).

    Campos:
        id_segmento: índice sequencial do segmento no perímetro.
        geom: geometria (linha) do segmento.
        comprimento_m: comprimento do segmento em metros (CRS métrico).
        logradouro: nome do logradouro, se for TESTADA (caso contrário, None).
        tipo_limite: "TESTADA" ou "DIVISA".
        confrontante: identificador do confrontante (campo "proprietário"
                      ou similar da camada de lotes), se aplicável.
    """
    id_segmento: int
    geom: QgsGeometry
    comprimento_m: float
    logradouro: Optional[str] = None
    tipo_limite: str = "DIVISA"  # "TESTADA" ou "DIVISA"
    confrontante: Optional[str] = None


@dataclass
class ResultadoTestadas:
    """
    Resultado consolidado da análise dos LIMITES do lote/gleba.

    Campos:
        segmentos: lista de todos os segmentos de limite (testadas e divisas),
                   já classificados e com eventuais logradouro/confrontante.
        testadas_por_logradouro: somatório de comprimento de TESTADAS por
                                 logradouro.
        confrontantes_por_proprietario: somatório de comprimento de DIVISAS
                                        por confrontante (campo proprietário).
    """
    segmentos: List[SegmentoTestada]
    testadas_por_logradouro: Dict[str, float]
    confrontantes_por_proprietario: Dict[str, float] = field(default_factory=dict)


# ----------------------------------------------------------------------
# Heurísticas de campos de atributo
# ----------------------------------------------------------------------


CAMPOS_NOME_LOGRADOURO = [
    "NOME",
    "nome",
    "Name",
    "NAME",
    "nm_logradouro",
    "NM_LOGRADOURO",
    "nm_lograd",
    "NM_LOGRAD",
    "TEXTO",
    "texto",
]

CAMPOS_NOME_PROPRIETARIO = [
    "proprietario",
    "proprietário",
    "PROPRIETARIO",
    "PROPRIETÁRIO",
    "Proprietario",
    "Proprietário",
    "PROPRIET",
    "propriet",
]


def _achar_campo_nome_logradouro(
    camada_logradouros: QgsVectorLayer,
) -> Optional[str]:
    """Tenta descobrir o campo que contém o nome do logradouro."""
    if camada_logradouros is None or not isinstance(camada_logradouros, QgsVectorLayer):
        return None

    nomes = {f.name() for f in camada_logradouros.fields()}
    for candidato in CAMPOS_NOME_LOGRADOURO:
        if candidato in nomes:
            return candidato

    # Se não encontrou, tenta algo com "nome" no meio
    for nome_campo in nomes:
        if "nome" in nome_campo.lower():
            return nome_campo

    return None


def _achar_campo_proprietario(
    camada_lotes: QgsVectorLayer,
) -> Optional[str]:
    """
    Tenta descobrir o campo que contém o nome do proprietário
    (ou identificador equivalente do confrontante) na camada de lotes.
    """
    if camada_lotes is None or not isinstance(camada_lotes, QgsVectorLayer):
        return None

    nomes = {f.name() for f in camada_lotes.fields()}

    # 1) tenta candidatos explícitos
    for candidato in CAMPOS_NOME_PROPRIETARIO:
        if candidato in nomes:
            return candidato

    # 2) fallback: qualquer campo que contenha "propriet" no nome
    for nome_campo in nomes:
        if "propriet" in nome_campo.lower():
            return nome_campo

    return None


# ----------------------------------------------------------------------
# Geometria: normal externa e índices espaciais
# ----------------------------------------------------------------------


def _normal_e_ponto_fora(
    seg: QgsGeometry,
    lote_geom: QgsGeometry,
) -> Optional[Tuple[Tuple[float, float], QgsPointXY]]:
    """
    Calcula a normal "para fora" do lote em relação ao segmento.

    Retorna:
        ((nx, ny), ponto_fora) ou None se não conseguir.

    Lógica espelhando a detecção robusta antiga:
    - usa o ponto médio do segmento;
    - testa as duas normais (esquerda/direita);
    - escolhe a que sai do polígono unificado do lote/gleba.
    """
    if seg is None or seg.isEmpty() or lote_geom is None or lote_geom.isEmpty():
        return None

    from qgis.core import QgsGeometry as _QgsGeometry

    length = seg.length()
    if length <= 0:
        return None

    mid = seg.interpolate(length / 2.0).asPoint()

    pl = seg.asPolyline()
    if not pl or len(pl) < 2:
        multi = seg.asMultiPolyline()
        if multi and len(multi[0]) >= 2:
            pl = multi[0]
        else:
            return None

    p1 = pl[0]
    p2 = pl[-1]

    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    n = (dx * dx + dy * dy) ** 0.5
    if n == 0:
        return None

    ux = dx / n
    uy = dy / n

    # Duas possíveis normais: esquerda e direita
    nx1, ny1 = -uy, ux
    nx2, ny2 = uy, -ux

    # deslocamento ~ 1m (CRS métrico)
    delta = 1.0
    cand1 = QgsPointXY(mid.x() + nx1 * delta, mid.y() + ny1 * delta)
    cand2 = QgsPointXY(mid.x() + nx2 * delta, mid.y() + ny2 * delta)

    g1 = _QgsGeometry.fromPointXY(cand1)
    g2 = _QgsGeometry.fromPointXY(cand2)

    inside1 = lote_geom.contains(g1)
    inside2 = lote_geom.contains(g2)

    # Se apenas um lado estiver fora, é a normal externa
    if inside1 and not inside2:
        return (nx2, ny2), cand2
    if inside2 and not inside1:
        return (nx1, ny1), cand1

    # Empate: chuta cand2 como "fora" (mesma heurística do código antigo)
    return (nx2, ny2), cand2


def _criar_indice_lotes(camada_lotes: QgsVectorLayer) -> QgsSpatialIndex:
    """
    Cria um índice espacial para os lotes.

    Usa o construtor com iterador de features (API atual).
    """
    if camada_lotes is None or not isinstance(camada_lotes, QgsVectorLayer):
        return QgsSpatialIndex()
    try:
        return QgsSpatialIndex(camada_lotes.getFeatures())
    except TypeError:
        idx = QgsSpatialIndex()
        for f in camada_lotes.getFeatures():
            g = f.geometry()
            if g is None or g.isEmpty():
                continue
            idx.addFeature(f)
        return idx


def _criar_indice_vias(
    camada_logradouros: QgsVectorLayer,
) -> Tuple[QgsSpatialIndex, Dict[int, object]]:
    """Cria índice espacial e dicionário {id: feature} para as vias."""
    if camada_logradouros is None or not isinstance(camada_logradouros, QgsVectorLayer):
        return QgsSpatialIndex(), {}

    try:
        idx = QgsSpatialIndex(camada_logradouros.getFeatures())
        vias_por_id: Dict[int, object] = {
            f.id(): f for f in camada_logradouros.getFeatures()
        }
        return idx, vias_por_id
    except TypeError:
        idx = QgsSpatialIndex()
        vias_por_id = {}
        for f in camada_logradouros.getFeatures():
            g = f.geometry()
            if g is None or g.isEmpty():
                continue
            idx.addFeature(f)
            vias_por_id[f.id()] = f
        return idx, vias_por_id


def _ponto_cai_em_algum_lote(
    pt: QgsPointXY,
    camada_lotes: QgsVectorLayer,
    index_lotes: QgsSpatialIndex,
) -> bool:
    """
    Verifica se o ponto 'pt' cai dentro de algum lote da camada.

    Como a gleba já vem unificada em lote_geom, QUALQUER lote contendo o
    ponto é tratado como lote confrontante (divisa).
    """
    if camada_lotes is None or not isinstance(camada_lotes, QgsVectorLayer):
        return False

    from qgis.core import QgsGeometry as _QgsGeometry

    pt_geom = _QgsGeometry.fromPointXY(pt)
    cand_ids = index_lotes.intersects(pt_geom.boundingBox())
    for fid in cand_ids:
        feat = camada_lotes.getFeature(fid)
        if feat is None or not feat.isValid():
            continue
        g = feat.geometry()
        if g is None or g.isEmpty():
            continue
        if g.contains(pt_geom):
            return True
    return False


def _obter_confrontante_para_ponto(
    pt: QgsPointXY,
    camada_lotes: QgsVectorLayer,
    index_lotes: QgsSpatialIndex,
    campo_proprietario: Optional[str],
) -> Optional[str]:
    """
    Dado um ponto "para fora" do lote, tenta identificar o lote confrontante
    e retorna o valor do campo de proprietário, se houver.
    """
    if (
        camada_lotes is None
        or not isinstance(camada_lotes, QgsVectorLayer)
        or campo_proprietario is None
    ):
        return None

    from qgis.core import QgsGeometry as _QgsGeometry

    pt_geom = _QgsGeometry.fromPointXY(pt)
    cand_ids = index_lotes.intersects(pt_geom.boundingBox())
    for fid in cand_ids:
        feat = camada_lotes.getFeature(fid)
        if feat is None or not feat.isValid():
            continue
        g = feat.geometry()
        if g is None or g.isEmpty():
            continue
        if not g.contains(pt_geom):
            continue

        try:
            val = feat[campo_proprietario]
        except KeyError:
            val = None

        if val is None:
            continue

        return str(val)

    return None


# ----------------------------------------------------------------------
# Segmentação da borda do lote (polígono / multipolígono)
# ----------------------------------------------------------------------


def _segmentar_borda_lote(lote_geom: QgsGeometry) -> List[QgsGeometry]:
    """
    Segmenta a borda do lote/gleba em pequenos trechos (segmentos de limite).

    Usa a representação de polígono / multipolígono (asPolygon / asMultiPolygon),
    como no código antigo, para evitar problemas com boundary().
    """
    if lote_geom is None or lote_geom.isEmpty():
        return []

    from qgis.core import QgsGeometry as _QgsGeometry

    segmentos: List[QgsGeometry] = []

    try:
        is_multi = lote_geom.isMultipart()
    except Exception:
        is_multi = False

    if is_multi:
        mpol = lote_geom.asMultiPolygon()  # [[ring1, ring2,...], ...]
        for poly in mpol:
            for ring in poly:
                n = len(ring)
                if n < 2:
                    continue
                for i in range(n - 1):
                    p1 = ring[i]
                    p2 = ring[i + 1]
                    seg = _QgsGeometry.fromPolylineXY([QgsPointXY(p1), QgsPointXY(p2)])
                    if seg and not seg.isEmpty():
                        segmentos.append(seg)
    else:
        poly = lote_geom.asPolygon()  # [ring1, ring2,...]
        for ring in poly:
            n = len(ring)
            if n < 2:
                continue
            for i in range(n - 1):
                p1 = ring[i]
                p2 = ring[i + 1]
                seg = _QgsGeometry.fromPolylineXY([QgsPointXY(p1), QgsPointXY(p2)])
                if seg and not seg.isEmpty():
                    segmentos.append(seg)

    return segmentos


# ----------------------------------------------------------------------
# Função principal
# ----------------------------------------------------------------------


def calcular_testadas_e_logradouros(
    lote_geom: QgsGeometry,
    camada_lotes: QgsVectorLayer,
    camada_logradouros: QgsVectorLayer,
    max_dist_m: float = DEFAULT_MAX_DIST_TESTADA_M,
) -> ResultadoTestadas:
    """
    Calcula LIMITES do lote/gleba, identificando TESTADAS e DIVISAS.

    Lógica:

    1) Segmentar toda a borda do lote em limites (polígono / multipolígono).
    2) Para cada segmento, calcular a normal "para fora" (ponto fora).
    3) Se o ponto "fora" cai em algum lote → DIVISA (com confrontante, se houver).
    4) Se não cai em lote, lançar um raio na direção da normal:
       - se interceptar logradouro → TESTADA (para aquele logradouro);
       - se não interceptar → DIVISA sem confrontante.

    Retorna:
        ResultadoTestadas com:
            - lista de segmentos (com tipo_limite, logradouro e confrontante);
            - somatório de comprimento de TESTADAS por logradouro;
            - somatório de comprimento de DIVISAS por confrontante.
    """
    from qgis.core import QgsGeometry as _QgsGeometry, QgsPointXY as _QgsPointXY

    if lote_geom is None or lote_geom.isEmpty():
        return ResultadoTestadas(segmentos=[], testadas_por_logradouro={})

    # Flags de validade das camadas
    tem_lotes = isinstance(camada_lotes, QgsVectorLayer)
    tem_vias = isinstance(camada_logradouros, QgsVectorLayer)

    campo_nome_log = _achar_campo_nome_logradouro(camada_logradouros) if tem_vias else None
    campo_proprietario = _achar_campo_proprietario(camada_lotes) if tem_lotes else None

    index_vias, vias_por_id = _criar_indice_vias(camada_logradouros) if tem_vias else (QgsSpatialIndex(), {})
    index_lotes = _criar_indice_lotes(camada_lotes) if tem_lotes else QgsSpatialIndex()

    segmentos_geom = _segmentar_borda_lote(lote_geom)

    resultado_segmentos: List[SegmentoTestada] = []
    testadas_por_logradouro: Dict[str, float] = {}
    confrontantes_por_proprietario: Dict[str, float] = {}

    for idx_seg, seg in enumerate(segmentos_geom, start=1):
        if seg is None or seg.isEmpty():
            continue

        comp_m = float(seg.length())
        if comp_m <= 0:
            continue

        # Valores padrão: DIVISA sem confrontante
        logradouro_atribuido: Optional[str] = None
        tipo_limite = "DIVISA"
        confrontante_atribuido: Optional[str] = None

        # 1) Normal "para fora" + ponto fora
        res_norm = _normal_e_ponto_fora(seg, lote_geom)
        if res_norm is not None:
            (nx, ny), pt_out = res_norm

            # 1.a) Primeiro verifica se o ponto fora cai em ALGUM lote
            tem_lote_confrontante = (
                tem_lotes and _ponto_cai_em_algum_lote(pt_out, camada_lotes, index_lotes)
            )

            if tem_lote_confrontante:
                # DIVISA: tenta pegar nome do confrontante, se houver campo
                if campo_proprietario is not None:
                    confrontante_atribuido = _obter_confrontante_para_ponto(
                        pt_out,
                        camada_lotes,
                        index_lotes,
                        campo_proprietario,
                    )
                tipo_limite = "DIVISA"
                logradouro_atribuido = None
            else:
                # Não há lote do lado de fora → pode ser TESTADA ou fronteira "solta"
                if tem_vias and campo_nome_log is not None:
                    seg_len = seg.length()
                    mid = seg.interpolate(seg_len / 2.0).asPoint()
                    pt_inicio = _QgsPointXY(mid.x(), mid.y())
                    pt_fim = _QgsPointXY(
                        mid.x() + nx * max_dist_m,
                        mid.y() + ny * max_dist_m,
                    )
                    raio_geom = _QgsGeometry.fromPolylineXY([pt_inicio, pt_fim])

                    candidatos = index_vias.intersects(raio_geom.boundingBox())
                    melhor_id = None
                    melhor_dist = None

                    for fid in candidatos:
                        feat_via = vias_por_id.get(fid)
                        if feat_via is None:
                            continue
                        g_via = feat_via.geometry()
                        if g_via is None or g_via.isEmpty():
                            continue
                        if not g_via.intersects(raio_geom):
                            continue

                        dist = g_via.distance(_QgsGeometry.fromPointXY(mid))
                        if melhor_dist is None or dist < melhor_dist:
                            melhor_dist = dist
                            melhor_id = fid

                    if melhor_id is not None:
                        feat_via = vias_por_id.get(melhor_id)
                        if feat_via is not None:
                            try:
                                val = feat_via[campo_nome_log]
                            except KeyError:
                                val = None
                            if val is not None:
                                logradouro_atribuido = str(val)

                if logradouro_atribuido:
                    tipo_limite = "TESTADA"
                    confrontante_atribuido = None
                else:
                    tipo_limite = "DIVISA"
                    # fronteira "solta": divisa com área não loteada / APP / mar, etc.

        # Se não conseguiu normal, permanece como DIVISA sem confrontante

        seg_testada = SegmentoTestada(
            id_segmento=idx_seg,
            geom=seg,
            comprimento_m=comp_m,
            logradouro=logradouro_atribuido,
            tipo_limite=tipo_limite,
            confrontante=confrontante_atribuido,
        )
        resultado_segmentos.append(seg_testada)

        # Agregados
        if logradouro_atribuido:
            atual = testadas_por_logradouro.get(logradouro_atribuido, 0.0)
            testadas_por_logradouro[logradouro_atribuido] = atual + comp_m

        if tipo_limite == "DIVISA" and confrontante_atribuido:
            atual_c = confrontantes_por_proprietario.get(confrontante_atribuido, 0.0)
            confrontantes_por_proprietario[confrontante_atribuido] = atual_c + comp_m

    return ResultadoTestadas(
        segmentos=resultado_segmentos,
        testadas_por_logradouro=testadas_por_logradouro,
        confrontantes_por_proprietario=confrontantes_por_proprietario,
    )

class TestadasService:
    """Fachada para serviços de testadas."""

    def calcular(self, *args, **kwargs):
        # Aqui você pode conectar com calcular_testadas_e_logradouros depois
        return None
