# -*- coding: utf-8 -*-
import os
from datetime import datetime

from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextBrowser,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QHBoxLayout,
)
from qgis.PyQt.QtCore import QTimer
from qgis.core import QgsProject

# IMPORTS CORRETOS
from ...dominio.motores.motor_analise_lote import CenarioEdificacao, analisar_lote
from ...infraestrutura.relatorios.construtor_relatorio import construir_contexto_relatorio
from ...infraestrutura.relatorios.renderizador_html import gerar_html_basico
from ...infraestrutura.espacial.config_camadas import registrar_camada, MAPA_CAMADAS
from ...infraestrutura.espacial.validadores import lotes_sao_contiguos
from ...infraestrutura.espacial.geometrias import unir_geometrias
from ...infraestrutura.espacial.zoneamento_lote import _montar_dados_lote_basicos


class ControladorUI:
    def __init__(self, ui, iface):
        self.ui = ui
        self.iface = iface

        # Estado
        self.lotes_selecionados = []
        self.selection_connection = None
        self.selection_timer = None
        self.camada_lotes_atual = None
        self._enter_filter = None
        self._event_filter_target = None

        # Conectar sinais da UI
        self.ui.sinal_iniciar_selecao.connect(self.iniciar_selecao_lotes)
        self.ui.sinal_executar_analise.connect(self.executar_analise_zoni_v2)
        self.ui.combo_lotes.layerChanged.connect(self._on_camada_lotes_changed)

        # Configurar monitoramento inicial
        self._configurar_monitor_selecao()

    # ------------------------------------------------------------------ #
    # MONITORAMENTO DE SELEÇÃO                                           #
    # ------------------------------------------------------------------ #
    def _configurar_monitor_selecao(self):
        self._desconectar_monitor_selecao()

        if self.ui.combo_lotes:
            self.camada_lotes_atual = self.ui.combo_lotes.currentLayer()
            camada = self.camada_lotes_atual
        else:
            camada = None

        if camada:
            self.selection_connection = camada.selectionChanged.connect(
                self._atualizar_selecao_lotes
            )
            self._atualizar_selecao_lotes()

    def _desconectar_monitor_selecao(self):
        if self.selection_connection:
            try:
                self.selection_connection.disconnect()
            except Exception:
                pass
            self.selection_connection = None

    def _atualizar_selecao_lotes(self):
        if self.selection_timer:
            self.selection_timer.stop()

        self.selection_timer = QTimer()
        self.selection_timer.setSingleShot(True)
        self.selection_timer.timeout.connect(self._processar_atualizacao_selecao)
        self.selection_timer.start(100)

    def _processar_atualizacao_selecao(self):
        if self.ui.combo_lotes:
            camada = self.ui.combo_lotes.currentLayer()
        else:
            camada = None

        if camada:
            if camada != self.camada_lotes_atual:
                self.camada_lotes_atual = camada
                self._configurar_monitor_selecao()
                return

            selecionadas = list(camada.getSelectedFeatures())

            if selecionadas:
                self.lotes_selecionados = selecionadas
                self.ui.botao_analisar.setEnabled(True)
                count = len(selecionadas)
                mensagem = f"{count} lote(s) selecionado(s) na camada '{camada.name()}'"
                self.iface.messageBar().pushInfo("Zôni v2", mensagem)
            else:
                self.lotes_selecionados = []
                self.ui.botao_analisar.setEnabled(False)

        self.selection_timer = None

    def _on_camada_lotes_changed(self):
        self._configurar_monitor_selecao()

    # ------------------------------------------------------------------ #
    # SELEÇÃO DE LOTES                                                   #
    # ------------------------------------------------------------------ #
    def iniciar_selecao_lotes(self):
        camada_lotes = self.ui.combo_lotes.currentLayer()

        if camada_lotes is None:
            self.iface.messageBar().pushWarning(
                "Zôni v2",
                "Nenhuma camada de lotes selecionada no menu. Escolha uma camada.",
            )
            return

        node = QgsProject.instance().layerTreeRoot().findLayer(camada_lotes.id())
        if node is not None:
            node.setItemVisibilityChecked(True)

        self.iface.layerTreeView().setCurrentLayer(camada_lotes)
        self.iface.setActiveLayer(camada_lotes)

        self.ui.hide()
        self.iface.actionSelectRectangle().trigger()

        # Import corrigido com caminho absoluto
        from ...interface.qt.zoni_dialog import EnterKeyFilter

        self._enter_filter = EnterKeyFilter(self.finalizar_selecao_lotes)
        alvo = self.iface.mapCanvas()
        alvo.installEventFilter(self._enter_filter)
        self._event_filter_target = alvo

    def finalizar_selecao_lotes(self):
        if self._event_filter_target and self._enter_filter:
            self._event_filter_target.removeEventFilter(self._enter_filter)

        from qgis.PyQt.QtWidgets import QApplication

        QApplication.processEvents()
        self.iface.mapCanvas().refresh()
        QApplication.processEvents()

        camada_lotes = self.ui.combo_lotes.currentLayer()

        if camada_lotes is None:
            self.iface.messageBar().pushWarning(
                "Zôni v2",
                "Camada de lotes não encontrada ao finalizar seleção.",
            )
            self.ui.show()
            return

        selecionados = list(camada_lotes.getSelectedFeatures())

        if not selecionados:
            self.iface.messageBar().pushWarning(
                "Zôni v2",
                "Nenhum lote selecionado.",
            )
            self.ui.show()
            return

        self.lotes_selecionados = selecionados
        self.ui.botao_analisar.setEnabled(True)

        self.ui.show()
        self.ui.raise_()
        self.ui.activateWindow()

        self._configurar_monitor_selecao()

    # ------------------------------------------------------------------ #
    # HELPERS DE CAMADA                                                  #
    # ------------------------------------------------------------------ #
    def _layer(self, combo, chave):
        if combo is not None:
            lyr = combo.currentLayer()
            if lyr:
                return lyr
        return MAPA_CAMADAS.get(chave)

    def _obter_camada_lotes_atual(self):
        return self.ui.combo_lotes.currentLayer() if self.ui.combo_lotes else None

    # ------------------------------------------------------------------ #
    # EXECUÇÃO DE ANÁLISE                                                #
    # ------------------------------------------------------------------ #
    def executar_analise_zoni_v2(self):
        """Executa a análise completa do lote/gleba."""
        # --- Imports relativos dentro da função ---
        try:
            from ...infraestrutura.espacial.geometrias import unir_geometrias
            from ...infraestrutura.espacial.validadores import lotes_sao_contiguos
            from ...dominio.motores.motor_analise_lote import (
                analisar_lote,
                CenarioEdificacao,
            )
            from ...infraestrutura.relatorios.construtor_relatorio import construir_contexto_relatorio
            from ...infraestrutura.relatorios.renderizador_html import gerar_html_basico
            from ...compartilhado.caminhos import obter_caminho_parametros
            from qgis.core import QgsFeatureRequest
        except ImportError:
            from infraestrutura.espacial.geometrias import unir_geometrias
            from infraestrutura.espacial.validadores import lotes_sao_contiguos
            from dominio.motores.motor_analise_lote import (
                analisar_lote,
                CenarioEdificacao,
            )
            from infraestrutura.relatorios.construtor_relatorio import construir_contexto_relatorio
            from infraestrutura.relatorios.renderizador_html import gerar_html_basico
            from compartilhado.caminhos import obter_caminho_parametros
            from qgis.core import QgsFeatureRequest

        # DEBUG CAMADA APP FAIXA
        camada_app_faixa = self._layer(self.ui.combo_app_nuic, "faixa_app_nuic")
        print("=== DEBUG CAMADA APP FAIXA ===")
        print(f"Camada: {camada_app_faixa}")
        if camada_app_faixa:
            print(f"  Nome: {camada_app_faixa.name()}")
            print(f"  Válida? {camada_app_faixa.isValid()}")
            print(f"  CRS: {camada_app_faixa.crs().authid()}")
            print(f"  Feições: {camada_app_faixa.featureCount()}")
        print("===============================")

        if not self.lotes_selecionados:
            camada_lotes = self._obter_camada_lotes_atual()
            if camada_lotes:
                self.lotes_selecionados = list(camada_lotes.getSelectedFeatures())

        camada_lotes = self._obter_camada_lotes_atual()
        if camada_lotes is None:
            self.iface.messageBar().pushWarning(
                "Zôni v2",
                "Camada de lotes não encontrada. Selecione uma camada no dropdown.",
            )
            return

        if not self.lotes_selecionados:
            self.iface.messageBar().pushWarning(
                "Zôni v2",
                "Nenhum lote foi selecionado. Selecione lotes na camada 'Lotes' ou use o botão 'Selecionar lote(s)'.",
            )
            return

        # Opcional: adicione aqui seus debugs se desejar, mas mantenha dentro do método.

        try:
            registrar_camada("lotes", self._layer(self.ui.combo_lotes, "lotes"))
            registrar_camada("zoneamento", self._layer(self.ui.combo_zoneamento, "zoneamento"))
            registrar_camada("logradouros", self._layer(self.ui.combo_logradouros, "logradouros"))
            registrar_camada("faixa_app_nuic", self._layer(self.ui.combo_app_nuic, "faixa_app_nuic"))
            registrar_camada("app_manguezal", self._layer(self.ui.combo_app_manguezal, "app_manguezal"))
            registrar_camada("app_inclinacao", self._layer(self.ui.combo_app_inclinacao, "app_inclinacao"))
            registrar_camada("susc_inundacao", self._layer(self.ui.combo_risco_inun, "susc_inundacao"))
            registrar_camada("susc_mov_massa", self._layer(self.ui.combo_risco_geo, "susc_mov_massa"))

        except Exception as e:
            self.iface.messageBar().pushWarning("Zôni v2", f"Erro ao registrar camadas: {e}")
            return

        # Caminho correto do JSON
        base_plugin = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        caminho_json = os.path.join(base_plugin, "infraestrutura", "dados", "parametros_zoneamento.json")

        if not os.path.exists(caminho_json):
            self.iface.messageBar().pushWarning("Zôni v2", f"Arquivo não encontrado:\n{caminho_json}")
            return

        # ============================================================
        # CASO 1 — GLEBA (múltiplos lotes contíguos)
        # ============================================================
        if len(self.lotes_selecionados) > 1:
            if not lotes_sao_contiguos(self.lotes_selecionados):
                QMessageBox.warning(
                    self.iface.mainWindow(),
                    "Zôni v2",
                    "Os lotes selecionados não são contíguos.\n\n"
                    "Selecione apenas lotes adjacentes para análise conjunta."
                )
                return

            # Unifica as geometrias (dissolve sobreposições)
            geom_unificada = unir_geometrias(self.lotes_selecionados)
            if geom_unificada is None or geom_unificada.isEmpty():
                self.iface.messageBar().pushCritical(
                    "Zôni v2",
                    "Erro ao unir geometrias dos lotes selecionados."
                )
                return

            # --- DEBUG APP FAIXA (GLEBA) ---
            camada_faixa = self._layer(self.ui.combo_app_nuic, "faixa_app_nuic")
            if camada_faixa and geom_unificada:
                bbox = geom_unificada.boundingBox()
                request = QgsFeatureRequest().setFilterRect(bbox).setLimit(100)
                features = list(camada_faixa.getFeatures(request))
                print(f"🔵 Feições da APP faixa na área da gleba: {len(features)}")
                for feat in features:
                    geom_app = feat.geometry()
                    if geom_app.intersects(geom_unificada):
                        print("  ✅ Interseção encontrada!")
                        attrs = feat.attributes()
                        fields = feat.fields().names()
                        for i, f in enumerate(fields):
                            print(f"    {f}: {attrs[i]}")
                    else:
                        print("  ❌ Feição dentro do bbox mas não intersecta")
            else:
                print("🔵 Camada de APP faixa não disponível ou geometria inválida")
            # --------------------------------------

#            # Cálculo da área total (soma dos campos de área ou área geométrica)
#            area_total = 0.0
#            for f in self.lotes_selecionados:
#                nomes = f.fields().names()
#                if "área" in nomes:
#                    area_total += f["área"] or 0.0
#                elif "area" in nomes:
#                    area_total += f["area"] or 0.0
#                else:
#                    area_total += f.geometry().area() if f.geometry() else 0.0

            # Área real da gleba = área do polígono unificado
            area_gleba = geom_unificada.area()

#            cenario = CenarioEdificacao(area_lote_m2=area_total)
            cenario = CenarioEdificacao(area_lote_m2=area_gleba)

            analise = analisar_lote(
                geom_lote=geom_unificada,
                cenario=cenario,
                caminho_parametros_zoneamento=caminho_json,
            )

            # Armazena a área da gleba no objeto de análise para uso no relatório
            analise.area_gleba_unificada = area_gleba

            # Nota 37: automática no motor (UI não faz nada)
            if getattr(analise, "detectou_frente_nota_37", False):
                pass

            # Nota 10: confirmação do usuário
            if getattr(analise, "detectou_frente_nota_10", False):
                nome_via = getattr(
                    analise,
                    "nome_via_nota_10",
                    "logradouro detectado"
                )

                aplicar = self.ui.confirmar_nota10_acesso_unico(nome_via)

                if aplicar:
                    analise.aplicar_nota_10()

            lista_dados_lote = [_montar_dados_lote_basicos(f) for f in self.lotes_selecionados]
            contexto = construir_contexto_relatorio(lista_dados_lote, analise)
            html = gerar_html_basico(contexto)
            self._mostrar_relatorio_html(html, "Relatório Zôni v2 – Gleba Unificada")
            return

        # ============================================================
        # CASO 2 — APENAS 1 LOTE
        # ============================================================
        feat_lote = self.lotes_selecionados[0]
        geom_lote = feat_lote.geometry()

        if geom_lote is None or geom_lote.isEmpty():
            self.iface.messageBar().pushWarning("Zôni v2", "Geometria do lote inválida.")
            return

        # --- DEBUG APP FAIXA (LOTE ÚNICO) ---
        camada_faixa = self._layer(self.ui.combo_app_nuic, "faixa_app_nuic")
        if camada_faixa and geom_lote:
            bbox = geom_lote.boundingBox()
            request = QgsFeatureRequest().setFilterRect(bbox).setLimit(100)
            features = list(camada_faixa.getFeatures(request))
            print(f"🔵 Feições da APP faixa na área do lote: {len(features)}")
            for feat in features:
                geom_app = feat.geometry()
                if geom_app.intersects(geom_lote):
                    print("  ✅ Interseção encontrada!")
                    attrs = feat.attributes()
                    fields = feat.fields().names()
                    for i, f in enumerate(fields):
                        print(f"    {f}: {attrs[i]}")
                else:
                    print("  ❌ Feição dentro do bbox mas não intersecta")
        else:
            print("🔵 Camada de APP faixa não disponível ou geometria inválida")
        # --------------------------------------

        nomes = feat_lote.fields().names()
        if "área" in nomes:
            area_lote = feat_lote["área"]
        elif "area" in nomes:
            area_lote = feat_lote["area"]
        else:
            area_lote = geom_lote.area()

        cenario = CenarioEdificacao(
            area_lote_m2=area_lote,
            area_construida_total_m2=None,
            area_ocupada_projecao_m2=None,
            area_permeavel_m2=None,
            altura_maxima_m=None,
            numero_pavimentos=None,
        )

        analise = analisar_lote(
            geom_lote=geom_lote,
            cenario=cenario,
            caminho_parametros_zoneamento=caminho_json,
        )

        # Nota 37: automática no motor (UI não faz nada)
        if getattr(analise, "detectou_frente_nota_37", False):
            pass

        # Nota 10: confirmação do usuário
        if getattr(analise, "detectou_frente_nota_10", False):
            nome_via = getattr(
                analise,
                "nome_via_nota_10",
                "logradouro detectado"
            )

            aplicar = self.ui.confirmar_nota10_acesso_unico(nome_via)

            if aplicar:
                analise.aplicar_nota_10()

        lista_dados_lote = [_montar_dados_lote_basicos(feat_lote)]
        contexto = construir_contexto_relatorio(lista_dados_lote, analise)
        html = gerar_html_basico(contexto)

        self._mostrar_relatorio_html(html, "Relatório Zôni v2 – Lote")

    # ------------------------------------------------------------------ #
    # EXIBIÇÃO DO RELATÓRIO                                              #
    # ------------------------------------------------------------------ #
    def _mostrar_relatorio_html(self, html: str, titulo: str):
        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle(titulo)
        layout = QVBoxLayout(dlg)

        button_layout = QHBoxLayout()

        btn_salvar_pdf = QPushButton("💾 Salvar como PDF")
        btn_salvar_pdf.clicked.connect(lambda: self._salvar_como_pdf(html, titulo))
        button_layout.addWidget(btn_salvar_pdf)

        btn_imprimir = QPushButton("🖨️ Imprimir")
        btn_imprimir.clicked.connect(lambda: self._imprimir_html(html))
        button_layout.addWidget(btn_imprimir)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(dlg.accept)
        button_layout.addWidget(btn_fechar)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        visor = QTextBrowser(dlg)
        visor.setHtml(html)
        layout.addWidget(visor)

        dlg.resize(950, 700)
        dlg.exec_()

    def _salvar_como_pdf(self, html: str, titulo: str):
        """Salva o relatório HTML como arquivo PDF."""
        from PyQt5.QtPrintSupport import QPrinter
        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_sugerido = f"Zoni_v2_{data_hora}.pdf"

        file_path, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Salvar Relatório como PDF",
            nome_sugerido,
            "Arquivos PDF (*.pdf);;Todos os arquivos (*)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(file_path)
        printer.setPageSize(QPrinter.A4)
        printer.setOrientation(QPrinter.Portrait)

        document = QTextDocument()
        document.setHtml(html)
        document.print_(printer)

        QMessageBox.information(
            self.iface.mainWindow(),
            "PDF Salvo com Sucesso",
            f"Relatório salvo como:\n{file_path}",
        )

    def _imprimir_html(self, html: str):
        """Imprime o relatório HTML."""
        from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtWidgets import QMessageBox

        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self.iface.mainWindow())

        if dialog.exec_() == QPrintDialog.Accepted:
            document = QTextDocument()
            document.setHtml(html)
            document.print_(printer)
            QMessageBox.information(
                self.iface.mainWindow(),
                "Impressão",
                "Relatório enviado para a impressora.",
            )