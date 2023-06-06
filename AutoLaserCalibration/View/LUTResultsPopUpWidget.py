
from PySide2.QtWidgets import QWidget,QTextEdit,QVBoxLayout, QLabel, QApplication, QMainWindow
import pandas as pd
import numpy as np

class LUTResultsPopUpWidget(QWidget):
    def __init__(self,lutResults:pd.DataFrame, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.summaryHeader = QLabel("Calibration Summary")
        self.lutDialog = QTextEdit()
        layout.addWidget(self.summaryHeader)
        layout.addWidget(self.lutDialog)
        self.lutDialog.setReadOnly(True)  
        PowerCalledFailure =  "Power Called Failures: " + ','.join(str(int(pixel)) for pixel in np.unique(lutResults.loc[lutResults["Status"] == "Power Called Failure"]['Pixel'].to_numpy().T))
        PowerToleranceFailure =  "Power Tolerance Failure: " + ','.join(str(int(pixel)) for pixel in np.unique(lutResults.loc[lutResults["Status"] == "Power Tolerance Failure"]['Pixel'].to_numpy().T))
        self.lutDialog.append(PowerCalledFailure)
        self.lutDialog.append(PowerToleranceFailure)
        self.show()
