import sys
import PySide2
from Model.Model import Model
from Model.Model import LaserSettings
from ConfigFiles.TestSettings import TestSettings
from ConfigFiles.MachineSettings import MachineSettings
from View.PyQtUI import MainWindow
from PySide2 import QtWidgets


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
    window = MainWindow(m)
    app.exec_()