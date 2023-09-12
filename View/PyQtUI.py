from PySide2 import QtWidgets
from PySide2.QtGui import *
from Model.Model import Model
from Model.OphirCom import OphirJunoCOM

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, model:Model):

        QtWidgets.QMainWindow.__init__(self)

        self.model = model
        self.junoPlusCom = OphirJunoCOM()
        self.model.connectToPlc()
        self.junoPlusCom.connectToJuno()
   