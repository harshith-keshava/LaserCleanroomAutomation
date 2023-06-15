from copy import deepcopy
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFormLayout, QLineEdit, QPushButton
from PySide2.QtGui import QPixmap
from PySide2.QtCore import Qt
from ConfigFiles.TestSettings import TestSettings
from Model.Model import Model

class SettingsWidget(QWidget):
    def __init__(self, model:Model, testSettings:TestSettings, parent=None):
        super().__init__(parent)
        self.model = model
        self.testSettings = testSettings
        self.manualTestSettingsPageLayout = QVBoxLayout()
        self.setLayout(self.manualTestSettingsPageLayout)
        self.manualTestSettingsPageLayout.setAlignment(Qt.AlignTop)
        self.InputOutputLayout = QHBoxLayout()
        self.manualTestSettingsPageLayout.addLayout(self.InputOutputLayout)
    
        self.inputSettings = self.settingsToQLineEdit(self.testSettings)
        self.outputSettings = self.settingsToQLineEdit(self.testSettings)
        
        
        self.inputSettingsHeader = QLabel("Input Settings")
        self.inputSettingsHeader.setAlignment(Qt.AlignCenter)
        self.inputSettingsHeader.setObjectName("header")
        self.settingsInputLayoutWithHeader = QVBoxLayout()
        self.settingsInputLayoutWithHeader.setAlignment(Qt.AlignTop)
        self.settingsInputLayout = QFormLayout()
        self.settingsInputLayoutWithHeader.addWidget(self.inputSettingsHeader)
        self.settingsInputLayoutWithHeader.addLayout(self.settingsInputLayout)
        self.applyCustomSettings = QPushButton("Apply Custom Settings")
        self.applyCustomSettings.clicked.connect(self.applySettings)
        [self.settingsInputLayout.addRow(input, self.inputSettings[input]) for input in self.inputSettings]
        self.InputOutputLayout.addLayout(self.settingsInputLayoutWithHeader)

        arrowLabel = QLabel()
        arrowPixmap = QPixmap('.\\view\\images\\arrow.png')
        arrowLabel.setPixmap(arrowPixmap)
        self.InputOutputLayout.addWidget(arrowLabel)

        self.outputSettingsHeader = QLabel("Current Settings")
        self.outputSettingsHeader.setAlignment(Qt.AlignCenter)
        self.outputSettingsHeader.setObjectName("header")
        self.settingsOutputLayoutWithHeader = QVBoxLayout()
        self.settingsOutputLayoutWithHeader.setAlignment(Qt.AlignTop)
        self.settingsOutputLayout = QFormLayout()
        self.settingsOutputLayoutWithHeader.addWidget(self.outputSettingsHeader)
        self.settingsOutputLayoutWithHeader.addLayout(self.settingsOutputLayout)
        [self.settingsOutputLayout.addRow(output, self.outputSettings[output]) for output in self.outputSettings]
        [self.outputSettings[output].setReadOnly(True) for output in self.outputSettings]
        self.InputOutputLayout.addLayout(self.settingsOutputLayoutWithHeader)
        self.manualTestSettingsPageLayout.addWidget(self.applyCustomSettings)

    def settingsToQLineEdit(self, settings:TestSettings):
        settingsAsDict = self.testSettings.settingsAsDict()
        qlineEdits = {}
        for setting in settingsAsDict:
            if setting == "Pixel List":
                qlineEdits[setting] = QLineEdit(self.testSettings._pixelListAsString())
            else:
                qlineEdits[setting] = QLineEdit(str(settingsAsDict[setting]))
        return qlineEdits

    def QLineEditsToSettingsDict(self, qlineeditsDict):
        testSettingsDict = {} 
        for setting in qlineeditsDict: 
            if setting == "Pixel List":
                testSettingsDict[setting] = [int(pixel) for pixel in qlineeditsDict[setting].text().split(',')]
            else:
                testSettingsDict[setting] = int(qlineeditsDict[setting].text())     
        return testSettingsDict

    def applySettings(self):
        self.testSettings.updateTestSettingsFromDict(self.QLineEditsToSettingsDict(self.inputSettings))
        self.testSettings._CalId = self.model.getCalibrationId()
        self.updateSettingsOutput()

    def updateSettingsOutput(self):
        testSettings = self.testSettings.settingsAsDict()
        print("updating settings")
        for setting in self.outputSettings:
            if setting == "Pixel List":
                self.outputSettings[setting].setText(self.testSettings._pixelListAsString())
            else:
                self.outputSettings[setting].setText(str(testSettings[setting]))
        self.testSettings._CalId = self.model.getCalibrationId()