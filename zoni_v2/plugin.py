# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

class ZoniV2Plugin:
    """Plugin QGIS – ponto de entrada, sem lógica de UI."""

    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialogo = None
        self.controlador = None

    def initGui(self):
        self.action = QAction(QIcon(), "Zôni v2 – Análise", self.iface.mainWindow())
        self.action.triggered.connect(self.abrir_janela_principal)
        self.iface.addPluginToMenu("Zôni v2", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("Zôni v2", self.action)
            self.iface.removeToolBarIcon(self.action)

        # Se quiser, pode limpar coisas do controlador aqui depois
        self.controlador = None
        self.dialogo = None

    def abrir_janela_principal(self):
        from .interface.qt.zoni_dialog import ZoniDialog
        from .interface.qt.controlador_ui import ControladorUI

        if self.dialogo is None:
            self.dialogo = ZoniDialog(self.iface)
            self.controlador = ControladorUI(self.dialogo, self.iface)

        self.dialogo.show()
        self.dialogo.raise_()
        self.dialogo.activateWindow()
