from PySide2.QtCore import Slot
from PySide2.QtCore import Signal as pyqtSignal
from PySide2.QtWidgets import QWidget
from PySide2.QtCore import QThread


class TracedVariable(QWidget):
    valueChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(TracedVariable, self).__init__(parent)
        self._val = 0

    @property
    def val(self):
        return self._val

    @val.setter
    def val(self, value):
        self._val = value
        self.valueChanged.emit(value)


class ThreadTracedVariable(QThread):
    valueChanged = pyqtSignal(int, name="changed") #New style signal

    def __init__(self, parent=None):
        QThread.__init__(self,parent)
        self._val = 0

    @property
    def val(self):
        return self._val

    @val.setter
    def val(self, value):
        self._val = value
        self.valueChanged.emit(value)