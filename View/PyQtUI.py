
from datetime import datetime
from time import sleep
from apscheduler.schedulers.background import BackgroundScheduler
from PySide2.QtCore import Slot
from PySide2.QtCore import Signal as pyqtSignal
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import QPushButton, QTabWidget,QFormLayout,QVBoxLayout,QHBoxLayout,QLineEdit,QRadioButton,QComboBox,QTextEdit,QProgressBar,QLabel,QFrame,QSizePolicy, QWidget,QFileDialog,QGridLayout,QButtonGroup
from PySide2.QtCore import QThread
from PySide2 import QtWebEngineWidgets
from matplotlib.pyplot import plot, scatter
from Model.Model import TestType
from View.QLed import QLed as ledIndicator
from PySide2 import QtWidgets
from PySide2.QtGui import *
from ConfigFiles.TestSettings import TestSettings
from View.LiveFigureCanvas import LiveFigureCanvas
import PySide2
from ConfigFiles.MachineSettings import MachineSettings
from Model.Model import Model
from threading import Thread
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import math
from View.ResultsWidget import ResultsWidget
from View.TracedVariables import ThreadTracedVariable
from View.TracedVariables import TracedVariable
from View.CriticalFailurePopUpWidget import CriticalFailurePopUpWidget
from View.LUTResultsPopUpWidget import LUTResultsPopUpWidget
from View.SettingsWidget import SettingsWidget
from Model.OphirCom import OphirJunoCOM

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, model:Model):
        QtWidgets.QMainWindow.__init__(self)
        self.testSettings = TestSettings()
        self.model = model
        self.junoPlusCom = OphirJunoCOM()
        self.model.connectToPlc()
        self.junoPlusCom.connectToJuno()
        self.testSettings.addPixelList(self.model.getViablePixelList())
        sleep(0.25)
        self.model.updateTestSettings(self.testSettings)
        self.resize(1920, 1080)
        self.centralwidget = QWidget(self)
        self.testPercentComplete = ThreadTracedVariable()
        self.lutDataReady = ThreadTracedVariable()
        
        self.tooltips = {"StartTestButtonLowPower" : "<b>Requires</b>:\nA valid pixel list\nGantry at Laser Calibrate in X,Y \nChiller enabled\nLaser DC Power Enabled\nLaser Emission Enabled\nSafety Reset\nNo Laser System Errors\nNo Laser Hardware Errors\nRecoater Powered On, at park, and No Errors",
                         "StartTestButtonVerification" : "<b>Requires</b>:\nA valid pixel list\nGantry at Laser Calibrate in X,Y \nChiller enabled\nLaser DC Power Enabled\nLaser Emission Enabled\nSafety Reset\nNo Laser System Errors\nNo Laser Hardware Errors\nRecoater Powered On, at park, and No Errors",
                         "StartTestButtonCalibration" : "<b>Requires</b>:\nA valid pixel list\nLinear LUTS Uploaded\nGantry at Laser Calibrate in X,Y \nChiller enabled\nLaser DC Power Enabled\nLaser Emission Enabled\nSafety Reset\nNo Laser System Errors\nNo Laser Hardware Errors\nRecoater Powered On, at park, and No Errors",
                         "SendConfigurationButton" : "<b>Requires</b>:\nChiller enabled\nLaser DC Power Enabled\nLaser Emission Enabled\nSafety Reset\nNo Laser System Errors\nNo Laser Hardware Errors\nRecoater Powered On, at park, and No Errors",
                         "UploadLinearLUTButton" : "Pushes Linear LUTs to VFLRs (this is required for Calibration Test)",
                         "UploadCalibratedLUTButton" : "<b>Requires:</b>\nCalibration test run successfully (check result plots)",
                         "ProceedToNextPixelButton" : "<b>Requires:</b>\nTest mode to be semi-automatic <b>OR</b> test mode to be continuous and a pixel to fail\nA test to be currently running",
                         "AbortTestButton" : "Aborts Test\nTurns of Laser Power and Disables Emission"}
        
        self.modelTestStatus = ThreadTracedVariable()
        self.setCentralWidget(self.centralwidget)
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName("main")
        self.CalibrationTab = QWidget()
        self.SettingsTab = SettingsWidget(self.model, self.testSettings)
        self.ResultsTab = ResultsWidget(self.testSettings, self.model)
        self.LoggerTab = QWidget()
        self.tabWidget.insertTab(0, self.CalibrationTab, "Test")
        self.tabWidget.insertTab(1, self.SettingsTab, "Settings")
        self.tabWidget.insertTab(2, self.ResultsTab, "Results")
        self.tabWidget.insertTab(3, self.LoggerTab, "Logger")
        

        self.verificationInputframe = QFrame()
        self.verificationInputLayout = QFormLayout(self.verificationInputframe)
        self.verificationStartingPowerInput = QLineEdit("199.7")
        self.verificationStartingPowerInput.textChanged.connect(self.updateStartingPower)
        self.verificationPowerIncrementInput = QLineEdit("49.4")
        self.verificationPowerIncrementInput.textChanged.connect(self.updatePowerIncrement)
        self.verificationPowerLevelsInput = QLineEdit("3")
        self.verificationPowerLevelsInput.textChanged.connect(self.updatePowerLevels)
        self.verificationToleranceBandInput = QLineEdit("5")
        self.verificationToleranceBandInput.textChanged.connect(self.updateToleranceBand)
        self.verificationInputLayout.addRow("Starting Power(W):", self.verificationStartingPowerInput)
        self.verificationInputLayout.addRow("Power Increment(W):", self.verificationPowerIncrementInput)
        self.verificationInputLayout.addRow("Power Levels:", self.verificationPowerLevelsInput)
        self.verificationInputLayout.addRow("Process Tolerance:", self.verificationToleranceBandInput)
        self.verificationInputframe.hide()

        self.calibrationInputFrame = QFrame()
        self.calibrationInputForm = QFormLayout(self.calibrationInputFrame)
        self.calibrationIDInput = QLineEdit()
        self.calibrationIDInput.textChanged.connect(self.updateCalibrationID)
        self.calibrationInputForm.addRow("Calibration ID:", self.calibrationIDInput)
        self.calibrationPowerCalledLimitInput = QLineEdit(str(self.testSettings._powerCalledLimit))
        self.calibrationPowerCalledLimitInput.textChanged.connect(self.updatePowerCalledLimitInput)
        self.calibrationInputForm.addRow("Called Limit (W):", self.calibrationPowerCalledLimitInput)
        self.calibrationPowerModifiedLimitInput = QLineEdit(str(self.testSettings._powerModifiedLimit))
        self.calibrationPowerModifiedLimitInput.textChanged.connect(self.updatePowerModifiedLimitInput)
        self.calibrationInputForm.addRow("Modified Limit (W):", self.calibrationPowerModifiedLimitInput)
        
        self.testHeader = QLabel("Test Commands")
        self.testHeader.setObjectName("header")
        self.testInfoInputsFrame = QFrame()
        self.testInfoInputs = QFormLayout(self.testInfoInputsFrame)
        self.operatorInfo = QLineEdit()
        self.operatorInfo.textChanged.connect(self.updateOperatorName)
        self.testInfoInputs.addRow("Operator:", self.operatorInfo)
        self.sensorInfo = QLineEdit() 
        self.ophirdeviceInfoLayout = QHBoxLayout()
        if self.junoPlusCom.isConnected:
            self.sensorInfo.setReadOnly(True)
            self.sensorInfo.setText("S\\N: " + str(self.junoPlusCom.getPyrometerSerialNum()) + ",  Calibrate: " + str(self.junoPlusCom.getPyrometerCalibrationDate()))
            self.testSettings._sensorNumber = self.junoPlusCom.getPyrometerSerialNum()
        else:
             self.sensorInfo.textChanged.connect(self.updateSensorID)
        self.testInfoInputs.addRow("Pyrometer", self.sensorInfo)
        self.junoPlusSerial = QLineEdit()
        if self.junoPlusCom.isConnected:
            self.junoPlusSerial.setReadOnly(True)
            self.junoPlusSerial.setText("S\\N: " + str(self.junoPlusCom.getJunoSerialNum()) + ",  Calibrate: " + str(self.junoPlusCom.getJunoCalibrationDate()))
            self.testSettings._junoPlusSerial = self.junoPlusCom.getJunoSerialNum()
        else:
            self.junoPlusSerial.textChanged.connect(self.updateJunoSerial)

        self.testInfoInputs.addRow("Juno+", self.junoPlusSerial)
        self.settingsDropDown = QComboBox()
        self.settingsDropDown.addItem('Low Power Check')
        self.settingsDropDown.addItem('Calibration')
        self.settingsDropDown.addItem('Clean Verification')
        self.settingsDropDown.addItem('Dirty Verification')
        self.settingsDropDown.currentIndexChanged.connect(self.updateConfigSettings)
        
        self.sendConfigSettingsButton = QPushButton("Send Configuration Values")
        self.sendConfigSettingsButton.clicked.connect(self.sendConfiguration)
        self.sendConfigSettingsButton.setToolTip(self.tooltips["SendConfigurationButton"])
    
        self.configirationRecievedIndicator = ledIndicator(self, onColour=ledIndicator.Green, shape=ledIndicator.Circle)
        
        self.testmodeComboBox = QComboBox()
        self.testmodeComboBox.addItem('Semi Auto - user interaction for all pixels')
        self.testmodeComboBox.addItem('Continuous - user interaction for bad pixels')
        self.testmodeComboBox.currentIndexChanged.connect(self.updateTestMode)
    

        self.startButton = QPushButton("Start Test")
        self.startButton.clicked.connect(self.startTest)
        self.startButton.setEnabled(self.model.isReadyToTest())
        self.startButton.setToolTip(self.tooltips["StartTestButtonLowPower"])

        self.calibratedLutUploadButton = QPushButton("Upload Calibrated LUTs")
        self.calibratedLutUploadButton.setEnabled(self.model.isTestComplete())
        self.calibratedLutUploadButton.clicked.connect(self.uploadCalibratedLuts)
        self.calibratedLutUploadButton.setToolTip(self.tooltips["UploadCalibratedLUTButton"])
        
        self.proceedToNextPixelButton = QPushButton('Proceed To Next Pixel')
        self.proceedToNextPixelButton.clicked.connect(self.goToNextPixel)
        self.proceedToNextPixelButton.setEnabled(False)
        self.proceedToNextPixelButton.setToolTip(self.tooltips["ProceedToNextPixelButton"])

        self.abortTestButton = QPushButton("Abort Test")
        self.abortTestButton.setObjectName("abort")
        self.abortTestButton.clicked.connect(self.abortTest)
        self.abortTestButton.setToolTip(self.tooltips["AbortTestButton"])
    
        self.uploadLinearLUTButton = QPushButton("Upload Linear LUTs")
        self.uploadLinearLUTButton.clicked.connect(self.model.uploadLinearLuts)
        self.uploadLinearLUTButton.setToolTip(self.tooltips["UploadLinearLUTButton"])

        self.uploadLutFromFolderButton = QPushButton("Upload LUTs from Folder")

        self.applicationLayout = QHBoxLayout(self.CalibrationTab)

        self.buttonLayout = QVBoxLayout()
        self.buttonLayout.setAlignment(Qt.AlignTop)
        self.buttonLayout.addWidget(self.testHeader)
        self.buttonLayout.addWidget(self.testInfoInputsFrame)
        self.buttonLayout.addWidget(self.settingsDropDown)
        self.buttonLayout.addWidget(self.testmodeComboBox)
        self.buttonLayout.addWidget(self.verificationInputframe)
        
        self.testingButtonFrame = QFrame()
        self.testingButtonFrame.setObjectName("boundingBox")
        self.testingButtonLayout = QGridLayout(self.testingButtonFrame)
        self.testingButtonLayout.addWidget(self.sendConfigSettingsButton,0,0,1,1)
        self.testingButtonLayout.addWidget(self.configirationRecievedIndicator,0,1,1,1)
        self.testingButtonLayout.addWidget(self.startButton,1,0,1,2)
        self.testingButtonLayout.addWidget(self.proceedToNextPixelButton,2,0,1,2)
        self.testingButtonLayout.addWidget(self.abortTestButton,3,0,1,2)

        self.LutButtonFrame = QFrame()
        self.LutButtonFrame.setObjectName("boundingBox")
        self.LutFrameLayout = QVBoxLayout(self.LutButtonFrame)
        self.LutButtonLayout = QGridLayout()
        self.uploadLinearLutLED = ledIndicator(self, onColour=ledIndicator.Green, shape=ledIndicator.Circle)
        self.uploadCalibratedLutLED = ledIndicator(self, onColour=ledIndicator.Green, shape=ledIndicator.Circle)
        self.LutButtonLayout.addWidget(self.uploadLinearLUTButton, 0,0)
        self.LutButtonLayout.addWidget(self.uploadLinearLutLED, 0,1)
        self.LutButtonLayout.addWidget(self.calibratedLutUploadButton, 1,0)
        self.LutButtonLayout.addWidget(self.uploadCalibratedLutLED, 1,1)
        self.LutFrameLayout.addLayout(self.LutButtonLayout)
        
        self.buttonLayout.addWidget(self.calibrationInputFrame)
        self.buttonLayout.addWidget(self.testingButtonFrame)
        self.buttonLayout.addWidget(self.LutButtonFrame)

        self.liveGraphing = LiveFigureCanvas(x_len=201, y_range=[0, 100], interval=1, model=self.model)

        self.graphAndBar = QVBoxLayout()
        self.lutAndDataButtonsLayout = QHBoxLayout()
        self.progressBar = QProgressBar()
        self.progressBar.setProperty("status", "testing")
        self.model.OnPixelChange(self.updateProgressBar)
        #self.model.addTagReaction('TestComplete', self.updateProgressBarComplete)
        self.testPercentComplete.valueChanged.connect(self.progressBar.setValue)
        self.graphAndBar.addWidget(self.liveGraphing)
        self.graphAndBar.addWidget(self.progressBar)
        self.testPercentComplete.val = 0
    
        self.testStatusAndProgressLayout = QVBoxLayout()
        self.numericalTestStatLabel = QLabel("Test Variables")
        self.numericalTestStatLabel.setObjectName("header")
        self.numericalTestStats = QFormLayout()
        self.currentCommandedPowerStatus = QLineEdit("0")
        self.currentCommandedPowerStatus.setReadOnly(True)
        self.currentTestPixelStatus = QLineEdit("0")
        self.currentTestPixelStatus.setReadOnly(True)
        self.opticsBoxTemperatureStatus = QLineEdit("0")
        self.opticsBoxTemperatureStatus.setReadOnly(True)
        self.pixelIndexStatus = QLineEdit("0")
        self.pixelIndexStatus.setReadOnly(True)
        self.energyStatus = QLineEdit("0")
        self.energyStatus.setReadOnly(True)
        self.powerStatus = QLineEdit("0")
        self.powerStatus.setReadOnly(True)
        self.percentErrorStatus = QLineEdit("0")
        self.percentErrorStatus.setReadOnly(True)
        self.testStatus = QLineEdit("Testing Inactive")
        self.testStatus.setReadOnly(True)
        self.errorCodeStatus = QLineEdit("")
        self.errorCodeStatus.setReadOnly(True)
        
        self.numericalTestStats.addRow("Text Pixel:", self.currentTestPixelStatus)
        self.numericalTestStats.addRow("Pixel Test Status:", self.pixelIndexStatus)
        self.numericalTestStats.addRow("Commanded Power (W):", self.currentCommandedPowerStatus)
        self.numericalTestStats.addRow("Energy (J):", self.energyStatus)
        self.numericalTestStats.addRow("Power (W):", self.powerStatus)
        self.numericalTestStats.addRow("Percent Error (%):", self.percentErrorStatus)
        self.numericalTestStats.addRow("Test Status:", self.testStatus)
        self.numericalTestStats.addRow("Error: ", self.errorCodeStatus)
        self.testIndicatorLayout = QFormLayout()
        self.testIndicatorLabel = QLabel("Test Indicators")
        self.testIndicatorLabel.setObjectName("header")
        self.testIndicatorLabel.adjustSize()
        self.testStatusLed = ledIndicator(self, onColour=ledIndicator.Green, shape=ledIndicator.Circle)
        self.userInputRequiredLed = ledIndicator(self, onColour=ledIndicator.Yellow, shape=ledIndicator.Round)
        self.fatalErrorLed = ledIndicator(self, onColour=ledIndicator.Red, shape=ledIndicator.Round)
        self.testCompleteLed = ledIndicator(self, onColour=ledIndicator.Green, shape=ledIndicator.Round)
        
        self.testIndicatorLayout.addRow("Test Status:", self.testStatusLed)
        self.testIndicatorLayout.addRow("User Input Needed:", self.userInputRequiredLed)
        self.testIndicatorLayout.addRow("Fatal Error - Test Aborted:", self.fatalErrorLed)
        self.testIndicatorLayout.addRow("Test Complete:", self.testCompleteLed)
        self.testStatusAndProgressLayout.addWidget(self.numericalTestStatLabel)
        self.testStatusAndProgressLayout.addLayout(self.numericalTestStats)
        self.testStatusAndProgressLayout.addWidget(self.testIndicatorLabel)
        self.testStatusAndProgressLayout.addLayout(self.testIndicatorLayout)

    
        self.sched = BackgroundScheduler()
        self.sched.add_job(lambda : self.energyStatus.setText(str(round(self.model.ScaledEnergyLiveTag.value, 3))), 'interval', seconds=0.5)
        self.sched.add_job(lambda : self.powerStatus.setText(str(round(self.model.ScaledEnergyLiveTag.value / (self.testSettings._pulseOnMsec / 1000), 2))), 'interval', seconds=0.5)
        self.sched.add_job(lambda : self.percentErrorStatus.setText(str(round(self.model.PercentErrorLiveTag.value, 3))), 'interval', seconds=0.5)
        self.sched.add_job(lambda : self.currentTestPixelStatus.setText(str(self.model.activePixelTag.value)), 'interval', seconds=0.5)
        self.sched.add_job(lambda : self.pixelIndexStatus.setText(str(self.model.getCurrentPixelIndex()) + " of " + str(len(self.testSettings._pixelList))), 'interval', seconds=0.5)
        # self.sched.add_job(lambda : self.currentCommandedPowerStatus.setText(str(round(max(self.model.currentPowerWattsTag.value), 3))), 'interval', seconds=0.5)
        

        sleep(0.25)
        self.sched.start()
        
        self.connectTagReactions()

        self.applicationLayout.addLayout(self.buttonLayout)
        self.applicationLayout.addLayout(self.graphAndBar)
        self.applicationLayout.addLayout(self.testStatusAndProgressLayout)
        self.updateConfigSettings()
    
        self.loggerFrame = QFrame(self.LoggerTab)
        self.loggerFrame.setObjectName("logger")
        self.logOutput = QTextEdit(self.loggerFrame)
        self.logOutput.setReadOnly(True)
        self.logOutput.setLineWrapMode(QTextEdit.NoWrap)       
        font = self.logOutput.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        self.logOutput.moveCursor(QTextCursor.End)
        self.model.addLogReactions(lambda : [self.logOutput.append(log) for log in self.model.logger.getNewLogs()])

        self.logOutput.setCurrentFont(font)
        sb = self.logOutput.verticalScrollBar()
        sb.setValue(sb.maximum())

    ## ----------------------------------------------------------
    ## ---------- INITIALIZATION FUNCTIONS ----------------------
    ## ----------------------------------------------------------

    def connectTagReactions(self):
        self.model.addTagReaction('UserAccessLevel', self.changeUserAccess)
        self.model.addTagReaction('TestComplete', lambda : self.settingsDropDown.setEnabled(self.model.isTestComplete()))
        self.model.addTagReaction('ReadyToTest', lambda : self.startButton.setEnabled(self.model.isReadyToTest()))
        self.model.addTagReaction('TestComplete', lambda : self.calibratedLutUploadButton.setEnabled(self.model.isTestComplete()))
        self.model.addTagReaction('CurrentLUTID', lambda : self.uploadLinearLutLED.setValue(int(self.model.getCalibrationId()) == 99999))
        self.model.addTagReaction('ConfigValid', lambda : self.configirationRecievedIndicator.setValue(self.model.isConfigValid()))
        self.model.addTagReaction('CurrentLUTID', lambda : self.uploadCalibratedLutLED.setValue(int(self.model.getCalibrationId()) == int(self.calibrationIDInput.text())))
        self.model.addTagReaction('TestComplete', lambda : self.testStatus.setText("Test Complete"))
        self.model.addTagReaction('TestComplete', lambda : self.testCompleteLed.setValue(self.model.isTestComplete()))
        self.model.addTagReaction('TestStatus', self.updateTestStatus)
        self.model.addTagReaction('TestStatus', lambda : self.proceedToNextPixelButton.setEnabled((self.model.TestMode == self.model.TestMode.SEMI_AUTO and self.model.getTestStatus() > 0) or (self.model.TestMode == self.model.TestMode.CONTINUOUS and self.model.getTestStatus() > 1)))
        self.model.addTagReaction('ErrorNum', lambda : self.errorCodeStatus.setText(self.model.getError()))
        self.tabWidget.setTabVisible(1, self.model.userAccessLevelTag.value==10)
        self.model.lutDataReady.addReaction(self.updateLUTDataReady)
        self.lutDataReady.valueChanged.connect(self.generateLUTPopUp)
        self.modelTestStatus.valueChanged.connect(self.showCriticalFailurePopUp)

    
    ## -------------------------------------------------------------
    ## ---------------- FUNCTION CONNECTED TO BUTTONS --------------
    ## -------------------------------------------------------------

    def startTest(self):
        self.abortTestButton.setEnabled(True)
        self.settingsDropDown.setDisabled(True)
        self.testCompleteLed.value = False
        self.testStatus.setText("Test In Progress")
        self.model.startTest()

    def sendConfiguration(self):
        if(self.testSettings._testType != 2):
            self.testSettings._CalId = self.model.getCalibrationId()
        else:
            self.updateCalibrationID()
        self.testSettings.addPixelList(self.model.getViablePixelList())
        self.model.updateTestSettings(self.testSettings)
        print(self.testSettings.settingsAsDict())
        self.liveGraphing.updateScale(x_len=math.ceil(1.6*self.testSettings._numPulsesPerLevel*self.testSettings._numPowerLevelSteps) - 1, y_range=[0, math.ceil((self.testSettings._numPowerLevelSteps * self.testSettings._powerLevelIncrement +  self.testSettings._startingPowerLevel) * (525/255))])
        self.model.sendConfigSettings()
    
    def abortTest(self):
        self.testStatus.setText("Test Aborted")
        self.settingsDropDown.setEnabled(True)
        self.model.abortTest()
        self.abortTestButton.setEnabled(False)
    
    def uploadCalibratedLuts(self):
        self.model.uploadCalibratedLuts(int(self.calibrationIDInput.text()))
    
    def closeEvent(self, event: PySide2.QtGui.QCloseEvent) -> None:
        self.model.abortTest()
        self.sched.remove_all_jobs()
        sleep(0.25)
        self.sched.shutdown(wait=False)
        sleep(0.5)
        self.liveGraphing._disconnect()
        sleep(0.25)
        self.model.disconnect()
        sleep(0.25)
        return super().closeEvent(event)

    def updateConfigSettings(self):
        testType = self.settingsDropDown.currentIndex()
        self.testSettings.addPixelList(self.model.getViablePixelList())
        if(testType == 0):
            self.testSettings.setDefaultLowPowerSettings()
            self.verificationInputframe.hide()
            self.calibrationInputFrame.hide()
            self.LutButtonFrame.hide()
            self.startButton.setToolTip(self.tooltips["StartTestButtonLowPower"])
        elif(testType==1):
            self.testSettings.setDefaultCalibrationSettings()
            self.verificationInputframe.hide()
            self.calibrationInputFrame.show()
            self.LutButtonFrame.show()
            self.startButton.setToolTip(self.tooltips["StartTestButtonCalibration"])
        elif(testType == 2 or testType == 3):
            if(testType == 2):
                self.testSettings.setDefaultCleanVerificationSettings()
            elif(testType == 3):
                self.testSettings.setDefaultDirtyVerificationSettings()
            self.startButton.setToolTip(self.tooltips["StartTestButtonVerification"])
            self.verificationInputframe.show()
            self.LutButtonFrame.hide()
            self.calibrationInputFrame.hide()
            if self.verificationStartingPowerInput.text() != "":
                self.testSettings._startingPowerLevel = round(float(self.verificationStartingPowerInput.text()) * (255/525))
            if self.verificationPowerIncrementInput.text() != "":
                self.testSettings._powerLevelIncrement = round(float(self.verificationPowerIncrementInput.text()) * (255/525))
            if self.verificationPowerLevelsInput.text() != "":
                self.testSettings._numPowerLevelSteps = round(float(self.verificationPowerLevelsInput.text()))
            if self.verificationToleranceBandInput.text() != "":
                self.testSettings._processTolerance = round(float(self.verificationToleranceBandInput.text()))
        else:
            self.verificationInputframe.hide()
            self.LutButtonFrame.hide()
        self.liveGraphing.updateScale(x_len=math.ceil(1.6*self.testSettings._numPulsesPerLevel*self.testSettings._numPowerLevelSteps) - 1, y_range=[0, math.ceil((self.testSettings._numPowerLevelSteps * self.testSettings._powerLevelIncrement +  self.testSettings._startingPowerLevel) * (525/255))])
        self.SettingsTab.updateSettingsOutput()

        

    def changeUserAccess(self):
        if self.model.userAccessLevelTag.value == 10:
            self.tabWidget.setTabVisible(1, True)
        else:
            self.tabWidget.setTabVisible(1, False)

    def moveTestToNextPixel(self):
         t = Thread(target = self.model.goToNextPixel())
         t.start()

    def updateTestMode(self):
        self.model.changeTestMode(self.testmodeComboBox.currentIndex())

    def updateProgressBar(self):
        self.testPercentComplete.val = (self.model.getCurrentPixelIndex()) / len(self.testSettings._pixelList) * 100

    def goToNextPixel(self):
        self.model.goToNextPixel()
        self.proceedToNextPixelButton.setDisabled(True)  
        self.userInputRequiredLed.setValue(False)
    
    def updateTestStatus(self):
        testStatusAsInt = self.model.getTestStatus()
        if testStatusAsInt == 0 and self.model.getCurrentPixelIndex() > 0 and self.model.testInProgress:
            self.testStatus.setText("Test In Progress")
            self.testStatusLed.onColour = ledIndicator.Blue
            self.testStatusLed.setValue(True)
        elif testStatusAsInt == 0 and self.model.getCurrentPixelIndex() == 0:
            self.testStatus.setText("Testing Inactive")
            self.testStatusLed.onColour = ledIndicator.Green
            self.testStatusLed.setValue(False)
        elif self.model.isTestComplete():
            self.testStatus.setText("Testing Complete")
            self.testStatusLed.onColour = ledIndicator.Green
            self.testStatusLed.setValue(True)
        elif testStatusAsInt == 1:
            self.testStatus.setText("Pixel Passed")
            self.testStatusLed.onColour = ledIndicator.Green
            self.testStatusLed.setValue(True)
        elif testStatusAsInt == 2:
            self.testStatus.setText("Power Output Too High")
            self.testStatusLed.onColour = ledIndicator.Yellow
            self.testStatusLed.setValue(True)
            self.userInputRequiredLed.setValue(True)
        elif testStatusAsInt == 3:
            self.testStatus.setText("Power Output Too Low")
            self.testStatusLed.onColour = ledIndicator.Yellow
            self.testStatusLed.setValue(True)
            self.userInputRequiredLed.setValue(True)
        elif testStatusAsInt == 4:
            self.modelTestStatus.val = testStatusAsInt
            self.testStatus.setText("Power output zero")
            self.testStatusLed.onColour = ledIndicator.Red
            self.testStatusLed.setValue(True)
        elif testStatusAsInt == 10:
            self.testStatus.setText("Laser Error")
            self.fatalErrorLed.setValue(True)


    ### ---------------------------------------------------------------
    ### ----------ALL UPDATE FUNCTIONS FOR TEXT BINDINGS  -------------
    ### ---------------------------------------------------------------

    def updateStartingPower(self):
        if self.verificationStartingPowerInput.text() != "":
            try:
                self.testSettings._startingPowerLevel = int(float(self.verificationStartingPowerInput.text()) * (255/525))
                self.SettingsTab.updateSettingsOutput()
            except:
                self.verificationStartingPowerInput.clear()

    def updatePowerIncrement(self):
        if self.verificationPowerIncrementInput.text() != "":
            try:
                self.testSettings._powerLevelIncrement = int(float(self.verificationPowerIncrementInput.text()) * (255/525))
                self.SettingsTab.updateSettingsOutput()
            except:
                self.verificationPowerIncrementInput.clear()
            
    def updatePowerLevels(self):
        if self.verificationPowerLevelsInput.text() != "":
            try:
                self.testSettings._numPowerLevelSteps = int(self.verificationPowerLevelsInput.text())
                self.SettingsTab.updateSettingsOutput()
                self.liveGraphing.updateScale(x_len=math.ceil(1.6*self.testSettings._numPulsesPerLevel*self.testSettings._numPowerLevelSteps) - 1, y_range=[0, math.ceil((self.testSettings._numPowerLevelSteps * self.testSettings._powerLevelIncrement +  self.testSettings._startingPowerLevel) * (525/255))])
            except:
                self.verificationPowerLevelsInput.clear()

    def updateToleranceBand(self):
        if self.verificationToleranceBandInput.text() != "":
            try:
                self.testSettings._processTolerance = int(self.verificationToleranceBandInput.text())
                self.SettingsTab.updateSettingsOutput()
            except:
                self.verificationToleranceBandInput.clear()
    
    def updateCalibrationID(self):
        if self.calibrationIDInput.text() != "" and self.testSettings._testType == 2:
            try:   
                self.testSettings._CalId = int(self.calibrationIDInput.text())
            except:
                self.calibrationIDInput.clear()


    def updatePowerModifiedLimitInput(self):
        try:
            self.testSettings._powerModifiedLimit = float(self.calibrationPowerModifiedLimitInput.text())
        except:
            self.calibrationIDInput.clear()

    def updatePowerCalledLimitInput(self):
        try:
            self.testSettings._powerCalledLimit = float(self.calibrationPowerCalledLimitInput.text())
        except:
            self.calibrationIDInput.clear()

    def updateOperatorName(self):
        self.testSettings._operatorName = str(self.operatorInfo.text())
    
    def updateSensorID(self):
        self.testSettings._sensorNumber = str(self.sensorInfo.text())
    
    def updateJunoSerial(self):
        self.testSettings._junoPlusSerial = str(self.junoPlusSerial.text())

    
    ### -------------------------------------------------------------------------
    ### --------------------------- POP UPS -------------------------------------
    ### -------------------------------------------------------------------------

    def generateLUTPopUp(self):
        self.lutpopup = LUTResultsPopUpWidget(self.model.getLUTResults())

    def showCriticalFailurePopUp(self):
        self.popUp = CriticalFailurePopUpWidget(self.model, self.testSettings)
    
    def updateLUTDataReady(self):
        if(self.model.lutDataReady.value == True):
            self.lutDataReady.val = self.model.lutDataReady.value

    ############################ OTHER ##############################################################
   

    def uploadLUTsFromFolder(self):
        folder , check = QFileDialog.getOpenFileName(None, "QFileDialog.getOpenFileName()",
                                                "", "CSV Files (*.csv)")
        if check:
            self.model.uploadLUTsFromFolder(folder)
    
    def updateProgressBarTesting(self):
        self.updateProgressBarStyle("testing")

    def updateProgressBarComplete(self):
        self.updateProgressBarStyle("complete")
    
    def updateProgressBarAbort(self):
        self.updateProgressBarStyle("abort")

    def updateProgressBarStyle(self, status):
        self.progressBar.setProperty("status", status)
        self.progressBar.style().unpolish(self.progressBar)
        self.progressBar.style().polish(self.progressBar)
    
    
    
   
    
    