import sys, os

import PySide2
from Model.Model import Model
from Model.Model import LaserSettings
from ConfigFiles.TestSettings import TestSettings
from ConfigFiles.MachineSettings import MachineSettings
from View.PyQtUI import MainWindow
from PySide2 import QtWidgets
from PySide2.QtGui import QIcon
import sys
from View.stylesheet import styleSheet


try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'mycompany.myproduct.subproduct.version'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

c = TestSettings()
s = MachineSettings()
l = LaserSettings()
m = Model(s,c,l)

if __name__ == '__main__':
    PySide2.QtWidgets.QApplication.setAttribute(PySide2.QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    basedir = os.path.dirname(__file__)
    app.setWindowIcon(QIcon(os.path.join(basedir, 'View\images\laser-warning_39051.ico')))
    app.setStyleSheet(styleSheet)
    window = MainWindow(m)
    window.show()
    app.exec_()