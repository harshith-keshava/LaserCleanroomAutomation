
from PySide2.QtWidgets import QWidget,QTextEdit,QVBoxLayout, QLabel, QApplication, QMainWindow, QDialog
import pandas as pd
import numpy as np
from ConfigFiles.TestSettings import TestSettings
from Model.Model import Model
import sys
from View.stylesheet import styleSheet
from PySide2 import QtCore  

class CriticalFailurePopUpWidget(QDialog):
    def __init__(self, model:Model,testSettings:TestSettings, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.summaryHeader = QLabel("ZERO POWER OUTPUT: The following pixels were disabled")
        self.disabledPixelsDialog = QTextEdit()
        layout.addWidget(self.summaryHeader)
        layout.addWidget(self.disabledPixelsDialog)
        self.disabledPixelsDialog.setReadOnly(True)
        failedPixelIndex = model.getCurrentPixelIndex()
        disabledPixels = [] 
        if failedPixelIndex > 1: 
            disabledPixels.append(testSettings._pixelList[failedPixelIndex - 1])
        disabledPixels.append(testSettings._pixelList[failedPixelIndex])
        if failedPixelIndex < len(testSettings._pixelList) - 2:
            disabledPixels.append(testSettings._pixelList[failedPixelIndex + 1])
        [self.disabledPixelsDialog.append("Pixel {pixelNum}".format(pixelNum=disabledPixel)) for disabledPixel in disabledPixels] 
        self.show()

   
