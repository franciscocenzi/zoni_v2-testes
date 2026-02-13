# dominio/zoneamento_resolvedor.py

from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ...infraestrutura.espacial.intersecao_zoneamento import ResultadoZoneamento
from ...infraestrutura.espacial.zoneamento_lote import ResultadoZoneamentoGeom
from ..regras.regras_zoneamento import ParametrosZona, carregar_parametros_de_arquivo


# ----------------------------------------------------------------------
#  Estruturas de dados
# ----------------------------------------------------------------------


@dataclass
class ZonaAplicada:
    """
    Representa um zoneamento efetivamente aplicado ao lote/gleba
    após as regras de sobreposição.

    - codigo: sigla da zona (ex.: "MUQ3", "EU2", "MUPA1", "ZEOT2").
    - tipo: classificação genérica ("ESPECIAL", "EIXO", "MACRO",
      "AMBIENTAL", "ORDINARIA").
    - area_m2 / percentual_area: área da zona dentro do lote e sua
      proporção relativa.
    - parametros: parâmetros urbanísticos lidos do JSON para esta zona.
    - notas: notas específicas associadas a esta zona (ex.: ["10"]).
    - origem: rótulo simples ("INTERSECCAO", "NOTA10", "NOTA37", etc.).
    """

    codigo: str
    tipo: str
    area_m2: float = 0.0
    percentual_area: float = 0.0
    parametros: Optional[ParametrosZona] = None
    notas: List[str] = field(default_factory=list)
    origem: str = "INTERSECCAO"


@dataclass
class ZonaResolvida:
    """
    Resultado consolidado da resolução de zoneamento.

    OBS: esta classe trabalha com múltiplas zonas aplicadas
    em coexistência. Os campos de “zona principal” foram mantidos
    apenas para compatibilidade com trechos antigos do código.
    """

    # Núcleo de informações
    zonas_aplicadas: List[ZonaAplicada] = field(default_factory=list)
    notas_ativas: List[str] = field(default_factory=list)
    tipo_regra: str = "NAO_DEFINIDA"
    resumo: str = ""
    observacoes: List[str] = field(default_factory=list)

    # Metadados gerais
    macrozona: Optional[str] = None
    eixos: List[str] = field(default_factory=list)
    especiais: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Campos de compatibilidade LEGADO (usados por módulos antigos)
    # ------------------------------------------------------------------
    zona_principal: Optional[str] = None        # zona de referência
    zonas_incidentes: List[str] = field(default_factory=list)
    parametros: Optional[ParametrosZona] = None  # parâmetros da zona_ref (se houver)
    motivo: str = ""


# ----------------------------------------------------------------------
#  Resolutor
# ----------------------------------------------------------------------


class ZoneamentoResolvedor:
    """
    Resolve o conjunto de zonas aplicáveis e notas a partir de:

    - ResultadoZoneamento (interseção "bruta" com camada de zoneamento),
    - ResultadoZoneamentoGeom (zonas + áreas por zona),
    - flags de Nota 10 e Nota 37 (por enquanto input manual da UI).

    Não decide mais um "zoneamento principal" conceitual; em vez disso,
    lista todas as zonas que coexistem após as regras de sobreposição.
    A zona_principal é usada apenas como referência para síntese de
    índices (motor_analise_lote + relatório).
    """

    def __init__(self, caminho_parametros_json: str):
        # Carrega uma vez a tabela de parâmetros (JSON)
        self._parametros_por_zona: Dict[str, ParametrosZona] = (
            carregar_parametros_de_arquivo(caminho_parametros_json)
        )

    # ------------------------------------------------------------------
    #  MÉTODO PÚBLICO
    # ------------------------------------------------------------------
    def resolver(
        self,
        res_zon: ResultadoZoneamento,
        res_geom: ResultadoZoneamentoGeom,
        nota10_ativada: bool = False,
        nota37_ativada: bool = False,
    ) -> ZonaResolvida:
        """
        Consolida:

        - lista de zonas incidentes + áreas (multi-zona),
        - aplicação das regras de coexistência/sobreposição,
        - notas especiais (10, 37, ...),
        - parâmetros urbanísticos por zona.

        Retorna um objeto ZonaResolvida.
        """

        # 1) Conjunto de zonas incidentes (multi-zona)
        zonas_incidentes = list(res_geom.zonas or [])
        zonas_areas = dict(res_geom.areas_por_zona or {})

        # Garante que a zona "bruta" (se houver) também esteja incluída
        if res_zon.zona and res_zon.zona not in zonas_incidentes:
            zonas_incidentes.append(res_zon.zona)
            zonas_areas.setdefault(res_zon.zona, 0.0)

        # 2) Aplica regras de coexistência/sobreposição
        (
            zonas_aplicadas,
            notas_ativas,
            tipo_regra,
            resumo,
            observacoes,
            zona_referencia,
        ) = self._resolver_sobreposicoes(
            zonas_incidentes=zonas_incidentes,
            zonas_areas=zonas_areas,
            res_zon=res_zon,
            nota10_ativada=nota10_ativada,
            nota37_ativada=nota37_ativada,
        )

        # 3) Anexa parâmetros urbanísticos do JSON para cada zona aplicada
        for za in zonas_aplicadas:
            param = self._parametros_por_zona.get(za.codigo)
            if param is not None:
                za.parametros = param

        # 4) Metadados: listas simples de eixos e zonas especiais
        eixos = [z.codigo for z in zonas_aplicadas if z.tipo == "EIXO"]
        especiais = [z.codigo for z in zonas_aplicadas if z.tipo == "ESPECIAL"]

        # 5) Campos de compatibilidade legado (zona_principal + parâmetros)
        zona_principal_legado = zona_referencia
        parametros_legado: Optional[ParametrosZona] = None
        if zona_principal_legado:
            parametros_legado = self._parametros_por_zona.get(zona_principal_legado)

        zonas_incidentes_unicas = sorted({z.codigo for z in zonas_aplicadas})

        return ZonaResolvida(
            zonas_aplicadas=zonas_aplicadas,
            notas_ativas=notas_ativas,
            tipo_regra=tipo_regra,
            resumo=resumo,
            observacoes=observacoes,
            macrozona=res_zon.macrozona,
            eixos=eixos,
            especiais=especiais,
            # LEGADO:
            zona_principal=zona_principal_legado,
            zonas_incidentes=zonas_incidentes_unicas,
            parametros=parametros_legado,
        )

    # ------------------------------------------------------------------
    #  Núcleo de regras de coexistência / sobreposição
    # ------------------------------------------------------------------
    def _resolver_sobreposicoes(
        self,
        zonas_incidentes: List[str],
        zonas_areas: Dict[str, float],
        res_zon: ResultadoZoneamento,
        nota10_ativada: bool,
        nota37_ativada: bool,
    ):
        """
        Aplica regras de coexistência/sobreposição.

        Entrada:
            - zonas_incidentes: códigos de zona incidentes (ex.: ["MUQ3", "EU2"]).
            - zonas_areas: dict {codigo: area_incidente_m2}.
            - res_zon: metadados (macrozona, eixos, especiais, zona "bruta").
            - nota10_ativada / nota37_ativada: flags vindas da UI.

        Saída:
            - zonas_aplicadas: lista de ZonaAplicada.
            - notas_ativas: lista de códigos de notas (["10"], ["37"], etc.).
            - tipo_regra: rótulo sintético do cenário dominante.
            - resumo: texto explicativo resumido.
            - observacoes: lista de textos adicionais.
            - zona_referencia: zona a ser usada como referência para índices.
        """

        zonas = [z for z in (zonas_incidentes or []) if z]
        zonas_areas = zonas_areas or {}

        if not zonas:
            resumo = "Nenhum zoneamento foi detectado sobre o lote."
            return [], [], "SEM_ZONEAMENTO", resumo, [], None

        zonas_set = set(zonas)

        # Acrescenta explicitamente eixos/especiais vindos do ResultadoZoneamento,
        # caso não estejam em zonas_incidentes (metadado).
        if getattr(res_zon, "eixos", None):
            zonas_set.update([z for z in res_zon.eixos if z])
        if getattr(res_zon, "especiais", None):
            zonas_set.update([z for z in res_zon.especiais if z])

        notas_ativas: List[str] = []
        observacoes: List[str] = []
        resumo_parts: List[str] = []
        zona_referencia: Optional[str] = None
        tipo_regra = "COEXISTENCIA_SIMPLES"

        # --------------------------------------------------------------
        # 1. Notas especiais 10 e 37
        # --------------------------------------------------------------
        if nota10_ativada:
            zonas_set.add("ZEOT2")  # garante presença da zona associada
            notas_ativas.append("10")
            resumo_parts.append(
                "Aplicada Nota 10 (empreendimento com acesso único em ZEOT2)."
            )
            tipo_regra = "NOTA_10_ZEOT2"
            zona_referencia = zona_referencia or "ZEOT2"

        if nota37_ativada:
            zonas_set.add("MUQ3")
            notas_ativas.append("37")
            resumo_parts.append(
                "Aplicada Nota 37 (lote com frente para a Rua Lúcio Joaquim Mendes em MUQ3)."
            )
            tipo_regra = (
                "NOTAS_10_E_37" if tipo_regra == "NOTA_10_ZEOT2" else "NOTA_37_MUQ3"
            )
            if zona_referencia is None:
                zona_referencia = "MUQ3"

        # --------------------------------------------------------------
        # 2. Classificação das zonas por tipo
        # --------------------------------------------------------------
        info_zonas: List[ZonaAplicada] = []
        zonas_ordenadas = sorted(zonas_set)
        area_total_incidente = sum(
            float(zonas_areas.get(z, 0.0) or 0.0) for z in zonas_ordenadas
        )

        for z in zonas_ordenadas:
            tipo = self._classificar_zona(z)
            area = float(zonas_areas.get(z, 0.0) or 0.0)
            perc = (area / area_total_incidente * 100.0) if area_total_incidente > 0 else 0.0

            origem = "INTERSECCAO"
            notas_zona: List[str] = []

            if z == "ZEOT2" and "10" in notas_ativas:
                origem = "NOTA10"
                notas_zona.append("10")
            if z == "MUQ3" and "37" in notas_ativas:
                origem = "NOTA37"
                notas_zona.append("37")

            info_zonas.append(
                ZonaAplicada(
                    codigo=z,
                    tipo=tipo,
                    area_m2=area,
                    percentual_area=perc,
                    notas=notas_zona,
                    origem=origem,
                )
            )

        # Separações úteis
        zonas_especiais = [z for z in info_zonas if z.tipo == "ESPECIAL"]
        zonas_eixos = [z for z in info_zonas if z.tipo == "EIXO"]
        zonas_ambientais = [z for z in info_zonas if z.tipo == "AMBIENTAL"]
        zonas_macro = [z for z in info_zonas if z.tipo == "MACRO"]
        zonas_ordinarias = [z for z in info_zonas if z.tipo == "ORDINARIA"]

        # --------------------------------------------------------------
        # 3. Comentários/resumo por tipo de combinação
        # --------------------------------------------------------------

        # 3.1 Zonas especiais
        if zonas_especiais:
            nomes = ", ".join(z.codigo for z in zonas_especiais)
            resumo_parts.append(
                "Zonas Especiais incidentes: "
                f"{nomes}. São consideradas regimes mais restritivos, "
                "devendo ser observadas em conjunto com os demais."
            )
            if zona_referencia is None:
                zona_referencia = max(zonas_especiais, key=lambda z: z.area_m2).codigo
                if tipo_regra == "COEXISTENCIA_SIMPLES":
                    tipo_regra = "ESPECIAL_PREDOMINANTE"

        # 3.2 Eixos / semieixos
        if zonas_eixos:
            nomes = ", ".join(z.codigo for z in zonas_eixos)
            resumo_parts.append(
                "Incidência de eixo(s)/semieixo(s): "
                f"{nomes}. Para testadas voltadas a estes logradouros, "
                "os recuos frontais deverão ser referidos ao eixo da via; "
                "para as demais frentes, prevalecem os recuos das "
                "macrozonas/zonas ordinárias correspondentes."
            )
            if zona_referencia is None:
                zona_referencia = max(zonas_eixos, key=lambda z: z.area_m2).codigo
            if tipo_regra == "COEXISTENCIA_SIMPLES":
                tipo_regra = "EIXOS_COEXISTENTES"

        # 3.3 Macrozona(s) ambientais – nunca “apagadas”
        if zonas_ambientais:
            nomes = ", ".join(z.codigo for z in zonas_ambientais)
            resumo_parts.append(
                "Macrozona(s) ambiental(is) identificada(s): "
                f"{nomes}. Esses regimes não são sobrepostos por eixos ou "
                "zonas urbanas, devendo ter suas condicionantes ambientais "
                "aplicadas proporcionalmente à área incidente."
            )

        # 3.4 Coexistência MUO / MUQ / MUCON / MEU / MUIS
        def _eh_macro_coexistencia(cod: str) -> bool:
            c = cod.upper()
            return (
                c.startswith("MUQ")
                or c.startswith("MUO")
                or c.startswith("MUCON")
                or c == "MEU"
                or c == "MUIS"
            )

        macros_coexistentes = [z for z in info_zonas if _eh_macro_coexistencia(z.codigo)]

        if len(macros_coexistentes) > 1:
            nomes = ", ".join(z.codigo for z in macros_coexistentes)
            resumo_parts.append(
                "Coexistem macrozonas urbanas do grupo MUO/MUQ/MUCON/MEU/MUIS "
                f"({nomes}). Os parâmetros urbanísticos devem ser aplicados "
                "proporcionalmente à área de cada macrozona."
            )
            if tipo_regra in ("COEXISTENCIA_SIMPLES", "EIXOS_COEXISTENTES"):
                tipo_regra = "COEXISTENCIA_MACROS_URBANAS"

        # 3.5 Caso específico MUIS + MEU – art. 29 da LC 278/2025
        codigos_presentes = {z.codigo.upper() for z in info_zonas}
        if "MUIS" in codigos_presentes and "MEU" in codigos_presentes:
            observacoes.append(
                "Há coexistência de áreas em MUIS e MEU. "
                "Aplica-se o art. 29 da LC 278/2025 quanto à transformação "
                "de área de expansão urbana em urbana, com efeitos "
                "urbanísticos e tributários imediatos."
            )

        # 3.6 Múltiplas zonas ordinárias com áreas equivalentes
        if (
            not zonas_eixos
            and not zonas_especiais
            and not zonas_macro
            and len(zonas_ordinarias) > 1
        ):
            ord_ordenadas = sorted(
                zonas_ordinarias, key=lambda z: z.area_m2, reverse=True
            )
            if len(ord_ordenadas) >= 2:
                a0 = ord_ordenadas[0].area_m2
                a1 = ord_ordenadas[1].area_m2
                if area_total_incidente > 0:
                    if abs(a0 - a1) / area_total_incidente < 0.05:
                        nomes = ", ".join(z.codigo for z in zonas_ordinarias)
                        resumo_parts.append(
                            "Foram identificadas múltiplas zonas ordinárias "
                            "com áreas equivalentes. Cada zona deve ser "
                            "aplicada na sua respectiva área de interseção, "
                            "sem eleição de uma zona única predominante "
                            "para o lote/gleba."
                        )
                        if tipo_regra == "COEXISTENCIA_SIMPLES":
                            tipo_regra = "COEXISTENCIA_ORDINARIAS_EQUIVALENTES"

        # 3.7 Se nada especial foi detectado, registra coexistência simples
        if not resumo_parts:
            resumo_parts.append(
                "Coexistência simples de zoneamentos incidentes sobre o lote, "
                "sem regra específica de prevalência codificada. Cada zona "
                "deve ser aplicada na sua área correspondente."
            )

        # 3.8 NOVO: se ainda não houve zona_referencia, usa a zona
        # com maior área (preferindo não-ambientais) apenas para síntese
        if zona_referencia is None and info_zonas:
            candidatos = [z for z in info_zonas if z.tipo != "AMBIENTAL"]
            if not candidatos:
                candidatos = info_zonas
            zona_ref = max(candidatos, key=lambda z: z.area_m2)
            zona_referencia = zona_ref.codigo
            if tipo_regra == "COEXISTENCIA_SIMPLES":
                tipo_regra = "ZONA_PREDOMINANTE"
            resumo_parts.append(
                f"Para fins de síntese dos índices urbanísticos, "
                f"adota-se a zona '{zona_referencia}' como zona de referência "
                f"por possuir maior área incidente no lote/gleba."
            )

        resumo_final = " ".join(resumo_parts)

        return info_zonas, notas_ativas, tipo_regra, resumo_final, observacoes, zona_referencia

    # ------------------------------------------------------------------
    #  Classificador de zona (ESPECIAL / EIXO / MACRO / AMBIENTAL / ORDINARIA)
    # ------------------------------------------------------------------
    def _classificar_zona(self, codigo: str) -> str:
        """
        Classificação heurística de códigos de zona.

        OBS: não codifica parâmetros nem notas; apenas identifica, de
        forma estável, o "tipo" geral para apoiar as regras de
        coexistência. Os parâmetros e notas vêm exclusivamente do JSON.
        """
        if not codigo:
            return "ORDINARIA"

        cod = codigo.strip().upper()

        # Zonas especiais (ZE..., ZEITA..., ZEOT..., etc.)
        if cod.startswith("ZE"):
            return "ESPECIAL"

        # Eixos e semieixos (EU..., EIXO..., etc.)
        if cod.startswith("EU") or cod.startswith("EIXO"):
            return "EIXO"

        # Macrozona(s) ambientais
        if cod.startswith("MUPA") or cod.startswith("MRO") or cod.startswith("MRPA"):
            return "AMBIENTAL"

        # Grupo de macrozonas urbanas principais
        if (
            cod.startswith("MUQ")
            or cod.startswith("MUO")
            or cod.startswith("MUCON")
            or cod == "MEU"
            or cod == "MUIS"
        ):
            return "MACRO"

        # Demais macrozonas genéricas
        if cod.startswith("MACRO") or cod.startswith("MZ"):
            return "MACRO"

        # Demais casos: tratadas como zonas ordinárias
        return "ORDINARIA"
