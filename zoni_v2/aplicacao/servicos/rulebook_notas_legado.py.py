    # ------------------------------------------------------------------
    # Rulebook de sobreposição (versão simplificada v1.0.4)
    # ------------------------------------------------------------------
    def encontrar_regra_sobreposicao(self, zonas, zonas_areas):
        """
        Aplica regras de sobreposição da LC 275/2025 + Anexo III + Notas.

        Entrada:
            - zonas: lista de códigos de zoneamento incidentes (ex.: ["MUQ2", "EU2"])
            - zonas_areas: dict {codigo: area_incidente_m2}

        Saída:
            dict com:
                - zonas_sobrepostas: lista de zonas consideradas
                - zona_principal: código da zona que prevalece (ou None)
                - tipo_regra: rótulo interno (ex.: "NOTA_10_ZEOT2", "EIXO_SOBRE_MACRO")
                - motivo: explicação textual para o usuário
        """
        zonas = list(zonas or [])
        zonas_areas = zonas_areas or {}
        zonas.sort()

        # --------------------------------------------------------------
        # 0. Se não há zona alguma intersectando, retorna mensagem simples
        # --------------------------------------------------------------
        if not zonas:
            return {
                "zonas_sobrepostas": [],
                "zona_principal": None,
                "tipo_regra": "SEM_ZONEAMENTO",
                "motivo": "Nenhum zoneamento foi detectado sobre o lote.",
            }

        # Conjunto base de zonas
        zonas_set = set(zonas)

        # --------------------------------------------------------------
        # 1. Regra específica – Nota 10 (ZEOT2 com acesso único pela Rua Sebastião)
        #    Aqui consideramos que, se o checkbox foi marcado, ZEOT2 passa a ser
        #    a zona principal, independentemente do shape.
        # --------------------------------------------------------------
        if self.chkAcessoSebastiao.isChecked():
            zonas_set.add("ZEOT2")
            zonas_list = sorted(zonas_set)
            return {
                "zonas_sobrepostas": zonas_list,
                "zona_principal": "ZEOT2",
                "tipo_regra": "NOTA_10_ZEOT2",
                "motivo": (
                    "Aplicada Nota 10 do Anexo III: empreendimento com acesso único "
                    "pela Rua Sebastião (...), prevalecendo ZEOT2 como zona principal."
                ),
            }

        # --------------------------------------------------------------
        # 2. Regra específica – Nota 37 (MUQ3 + frente para Rua Lúcio Joaquim Mendes)
        #    Há dois gatilhos:
        #      a) checkbox marcado, ou
        #      b) qualquer testada com logradouro cujo nome contenha 'LUCIO' e 'MENDES'
        # --------------------------------------------------------------
        tem_frente_lucio = False
        if self.testadas_por_logradouro:
            for nome_log in self.testadas_por_logradouro.keys():
                if not nome_log:
                    continue
                norm = self.normalize_name(nome_log)
                if "LUCIO" in norm and "MENDES" in norm:
                    tem_frente_lucio = True
                    break

        if self.chkAcessoLucio.isChecked() or tem_frente_lucio:
            zonas_set.add("MUQ3")
            zonas_list = sorted(zonas_set)
            return {
                "zonas_sobrepostas": zonas_list,
                "zona_principal": "MUQ3",
                "tipo_regra": "NOTA_37_MUQ3",
                "motivo": (
                    "Aplicada Nota 37 do Anexo III: lote com frente para a Rua "
                    "Lúcio Joaquim Mendes, prevalecendo MUQ3 como zona principal "
                    "para definição dos parâmetros urbanísticos."
                ),
            }

        # --------------------------------------------------------------
        # 3. Classificação das zonas em ESPECIAL / EIXO / MACRO / OUTRA
        # --------------------------------------------------------------
        info_zonas = []
        for z in zonas_set:
            tipo = self._classificar_zona(z)
            area = zonas_areas.get(z, 0.0)
            info_zonas.append({"codigo": z, "tipo": tipo, "area": area})

        especiais = [i for i in info_zonas if i["tipo"] == "ESPECIAL"]
        eixos = [i for i in info_zonas if i["tipo"] == "EIXO"]
        macros = [i for i in info_zonas if i["tipo"] == "MACRO"]
        outras = [i for i in info_zonas if i["tipo"] == "OUTRA"]

        zonas_list = sorted(zonas_set)

        # --------------------------------------------------------------
        # 4. Se houver Zona Especial (ZE...), ela tende a ser principal
        #    (ZEOT, outras especiais), por serem criadas como mais restritivas
        # --------------------------------------------------------------
        if especiais:
            # Escolhe a zona especial com maior área incidente
            especiais_sorted = sorted(especiais, key=lambda x: x["area"], reverse=True)
            principal = especiais_sorted[0]["codigo"]
            return {
                "zonas_sobrepostas": zonas_list,
                "zona_principal": principal,
                "tipo_regra": "ZONA_ESPECIAL_PREDOMINANTE",
                "motivo": (
                    "Foi identificada Zona Especial incidente sobre o lote. As zonas "
                    "especiais são consideradas mais restritivas e, portanto, "
                    f"{principal} foi tomada como zona principal. As demais zonas "
                    "incidentes podem ser consideradas em aspectos não cobertos "
                    "pela Zona Especial."
                ),
            }

        # --------------------------------------------------------------
        # 5. Caso com EIXO + MACROZONA (situação típica de sobreposição)
        #    Ex.: EU2 sobre MUQ2, etc.
        # --------------------------------------------------------------
        if eixos and macros:
            # Eixo principal: o de maior área incidente
            eixos_sorted = sorted(eixos, key=lambda x: x["area"], reverse=True)
            eixo_principal = eixos_sorted[0]["codigo"]

            # Lista de macrozonas base
            nomes_macros = [m["codigo"] for m in macros]

            return {
                "zonas_sobrepostas": zonas_list,
                "zona_principal": eixo_principal,
                "tipo_regra": "EIXO_SOBRE_MACRO",
                "motivo": (
                    "Foi identificada sobreposição entre Eixo e Macrozona. "
                    f"O eixo {eixo_principal} é tomado como regime principal "
                    "para parâmetros de adensamento (CA, TO, gabarito, recuo "
                    "frontal na testada do eixo). Para as demais frentes, "
                    "mantêm-se os recuos frontais mínimos definidos na(s) "
                    f"macrozona(s) base: {', '.join(nomes_macros)}."
                ),
            }

        # --------------------------------------------------------------
        # 6. Caso com apenas Eixos (sem macrozona explícita intersectando)
        # --------------------------------------------------------------
        if eixos and not macros:
            eixos_sorted = sorted(eixos, key=lambda x: x["area"], reverse=True)
            eixo_principal = eixos_sorted[0]["codigo"]
            return {
                "zonas_sobrepostas": zonas_list,
                "zona_principal": eixo_principal,
                "tipo_regra": "APENAS_EIXO",
                "motivo": (
                    "Foram identificadas apenas zonas classificadas como Eixos/semieixos. "
                    f"O eixo {eixo_principal} foi tomado como principal com base na "
                    "maior área incidente. Caso existam transições com outras zonas "
                    "não mapeadas, recomenda-se conferência manual na LC 275/2025."
                ),
            }

        # --------------------------------------------------------------
        # 7. Caso com apenas Macrozona(s)
        # --------------------------------------------------------------
        if macros and not eixos and not especiais:
            if len(macros) == 1:
                principal = macros[0]["codigo"]
                return {
                    "zonas_sobrepostas": zonas_list,
                    "zona_principal": principal,
                    "tipo_regra": "MACRO_UNICA",
                    "motivo": (
                        "Apenas uma macrozona incide sobre o lote. Ela é tomada "
                        "como zona principal para fins de parâmetros urbanísticos."
                    ),
                }
            else:
                # Mais de uma macrozona, LC omissa quanto à prevalência
                nomes_macros = [m["codigo"] for m in macros]
                return {
                    "zonas_sobrepostas": zonas_list,
                    "zona_principal": None,
                    "tipo_regra": "MACRO_MULTIPLA",
                    "motivo": (
                        "Foram identificadas múltiplas macrozonas incidentes "
                        f"({', '.join(nomes_macros)}) e não há, na LC 275/2025, "
                        "regra explícita de prevalência automática para este conjunto. "
                        "Recomenda-se considerar os parâmetros proporcionais à área "
                        "incidente de cada macrozona e complementar com análise "
                        "técnica e jurídica específica."
                    ),
                }

        # --------------------------------------------------------------
        # 8. Zonas não classificadas (OUTRA) ou combinação exótica
        # --------------------------------------------------------------
        return {
            "zonas_sobrepostas": zonas_list,
            "zona_principal": None,
            "tipo_regra": "SEM_REGRA_ESPECIFICA",
            "motivo": (
                "O conjunto de zoneamentos incidentes não se enquadra em nenhuma das "
                "regras de sobreposição codificadas nesta versão do plugin. A LC 275/2025 "
                "deve ser consultada diretamente para interpretação do caso concreto."
            ),
        }
