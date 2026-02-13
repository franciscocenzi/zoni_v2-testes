# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QGridLayout,
    QMessageBox,
)

from qgis.PyQt.QtCore import pyqtSignal, Qt, QObject, QEvent
from qgis.gui import QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel, QgsProject

from ...infraestrutura.espacial.config_camadas import registrar_camada, MAPA_CAMADAS


class EnterKeyFilter(QObject):
    """Filtro simples para capturar ENTER e finalizar seleção."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.callback()
            return True
        return False


class ZoniDialog(QDialog):
    sinal_iniciar_selecao = pyqtSignal()
    sinal_executar_analise = pyqtSignal()
    sinal_dialogo_fechado = pyqtSignal()

    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface

        self.combo_lotes = None
        self.combo_zoneamento = None
        self.combo_logradouros = None
        self.combo_app_nuic = None
        self.combo_app_manguezal = None
        self.combo_app_inclinacao = None
        self.combo_risco_geo = None
        self.combo_risco_inun = None

        self.botao_selecionar = None
        self.botao_analisar = None

        self.chk_nota10 = None
        self.chk_nota37 = None

        self._montar_ui()

    def _montar_ui(self):
        self.setWindowTitle("Zôni v2 – Seleção de Camadas")
        layout = QVBoxLayout(self)

        MAPA_CAMADAS.clear()
        for layer in QgsProject.instance().mapLayers().values():
            name = layer.name().lower()

            if any(k in name for k in ["-lote", "gleba"]):
                registrar_camada("lotes", layer)
            if "zoneamento" in name:
                registrar_camada("zoneamento", layer)
            if "logradouros" in name:
                registrar_camada("logradouros", layer)
            if "_llnuiapp" in name:
                registrar_camada("faixa_app_nuic", layer)
            if "_area_manguezal" in name:
                registrar_camada("app_manguezal", layer)
            if "pb.slope.graus" in name:
                registrar_camada("app_inclinacao", layer)
            if "_inundacao" in name:
                registrar_camada("susc_inundacao", layer)
            if "_movimento_massa" in name:
                registrar_camada("susc_mov_massa", layer)

        layout.addWidget(QLabel("Camada de LOTES (polígonos):"))
        self.combo_lotes = QgsMapLayerComboBox()
        self.combo_lotes.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layout.addWidget(self.combo_lotes)
        self._auto_set_combo(self.combo_lotes, "lotes")

        layout.addWidget(QLabel("Camada de ZONEAMENTO (polígonos):"))
        self.combo_zoneamento = QgsMapLayerComboBox()
        self.combo_zoneamento.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layout.addWidget(self.combo_zoneamento)
        self._auto_set_combo(self.combo_zoneamento, "zoneamento")

        layout.addWidget(QLabel("Camada de LOGRADOUROS (linhas):"))
        self.combo_logradouros = QgsMapLayerComboBox()
        self.combo_logradouros.setFilters(QgsMapLayerProxyModel.LineLayer)
        layout.addWidget(self.combo_logradouros)
        self._auto_set_combo(self.combo_logradouros, "logradouros")

        app_group = QGroupBox("Camadas de APP")
        app_layout = QGridLayout(app_group)

        app_layout.addWidget(QLabel("Faixa APP - NUIC (polígonos):"), 0, 0)
        self.combo_app_nuic = QgsMapLayerComboBox()
        self.combo_app_nuic.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        app_layout.addWidget(self.combo_app_nuic, 0, 1)
        self._auto_set_combo(self.combo_app_nuic, "faixa_app_nuic")

        app_layout.addWidget(QLabel("APP - Manguezais (polígonos):"), 1, 0)
        self.combo_app_manguezal = QgsMapLayerComboBox()
        self.combo_app_manguezal.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        app_layout.addWidget(self.combo_app_manguezal, 1, 1)
        self._auto_set_combo(self.combo_app_manguezal, "app_manguezal")

        app_layout.addWidget(QLabel("APP - por Inclinação (raster):"), 2, 0)
        self.combo_app_inclinacao = QgsMapLayerComboBox()
        self.combo_app_inclinacao.setFilters(QgsMapLayerProxyModel.RasterLayer)
        app_layout.addWidget(self.combo_app_inclinacao, 2, 1)
        self._auto_set_combo(self.combo_app_inclinacao, "app_inclinacao")

        layout.addWidget(app_group)

        layout.addWidget(QLabel("Camada de RISCO – Movimentos de Massa (polígonos):"))
        self.combo_risco_geo = QgsMapLayerComboBox()
        self.combo_risco_geo.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layout.addWidget(self.combo_risco_geo)
        self._auto_set_combo(self.combo_risco_geo, "susc_mov_massa")

        layout.addWidget(QLabel("Camada de RISCO – Inundação (polígonos):"))
        self.combo_risco_inun = QgsMapLayerComboBox()
        self.combo_risco_inun.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        layout.addWidget(self.combo_risco_inun)
        self._auto_set_combo(self.combo_risco_inun, "susc_inundacao")

        layout.addWidget(
            QLabel(
                "1) Preencha todas as camadas acima.\n"
                "2) Selecione lotes diretamente na camada 'Lotes' OU use o botão abaixo.\n"
                "3) Clique em 'Analisar' para gerar o relatório.\n\n"
                "Dica: Você pode selecionar lotes antes ou depois de abrir esta janela."
            )
        )

        self.botao_selecionar = QPushButton("Selecionar lote(s) (modo especial)")
        self.botao_selecionar.setToolTip(
            "Esconde a janela e ativa a ferramenta de seleção. Pressione ENTER para concluir."
        )
        self.botao_selecionar.clicked.connect(self.sinal_iniciar_selecao.emit)
        layout.addWidget(self.botao_selecionar)

        self.botao_analisar = QPushButton("Analisar")
        self.botao_analisar.setEnabled(False)
        self.botao_analisar.clicked.connect(self.sinal_executar_analise.emit)
        layout.addWidget(self.botao_analisar)

        self.resize(520, 720)

    def _auto_set_combo(self, combo: QgsMapLayerComboBox, chave: str):
        if combo is None:
            return
        lyr = MAPA_CAMADAS.get(chave)
        if lyr is not None:
            try:
                combo.setLayer(lyr)
            except Exception:
                pass

    def confirmar_nota10_acesso_unico(self, nome_via: str) -> bool:
        """
        Pergunta ao usuário se o projeto prevê acesso único pela via detectada.
        Retorna True se SIM, False se NÃO.
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Nota 10 – Acesso viário")
        msg.setIcon(QMessageBox.Question)
        msg.setText(
            f"Foi detectado que o lote faz frente para a via:\n\n"
            f"{nome_via}\n\n"
            "O projeto prevê acesso único por esta via?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        return msg.exec() == QMessageBox.Yes

    def closeEvent(self, event):
        self.sinal_dialogo_fechado.emit()
        super().closeEvent(event)
