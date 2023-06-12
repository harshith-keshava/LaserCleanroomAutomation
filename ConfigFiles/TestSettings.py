import string
import numpy as np

from ConfigFiles.MachineSettings import MachineSettings
class TestSettings():

    def __init__(self) -> None:
        self._testType = 1
        self._CalId = 99999
        self._operatorName = ""
        self._sensorNumber = ""
        self._pulseDelayMsec = 0
        self._pulseOnMsec = 5
        self._pulseOffMsec = 58
        self._availableLaserPowerWatts = 525
        self._safePowerLimitWatts = 300
        self._numPulsesPerLevel = 1
        self._startingPowerLevel = 24  #bnr.startingPowerLevelTag.getValue()
        self._numPowerLevelSteps = 2 #bnr.numPowerLevelStepsTag.getValue()
        self._powerLevelIncrement = 5 #bnr.powerLevelIncrementTag.getValue()
        self._powerModifiedLimit = 1.0
        self._powerCalledLimit = 0.6
        self._pixelList = [0]
        self._tolerancePercent = 50
        self._coefficients = np.full((1,84), 1, dtype=float)[0]
        self._processTolerance = 5
        self._junoPlusSerial = ""
    

    def setDefaultLowPowerSettings(self):
        self._testType = 1
        self._pulseDelayMsec = 0
        self._pulseOnMsec = 5
        self._pulseOffMsec = 58
        self._availableLaserPowerWatts = 525
        self._safePowerLimitWatts = 300
        self._numPulsesPerLevel = 1
        self._startingPowerLevel = 24  #bnr.startingPowerLevelTag.getValue()
        self._numPowerLevelSteps = 2 #bnr.numPowerLevelStepsTag.getValue()
        self._powerLevelIncrement = 5 #bnr.powerLevelIncrementTag.getValue()
        self._tolerancePercent = 50
        self._processTolerance = 5
        
    def setDefaultCalibrationSettings(self):
        print("Changing to Calibration Test Settings")
        self._testType = 2
        self._pulseDelayMsec = 0
        self._pulseOnMsec = 5
        self._pulseOffMsec = 58
        self._availableLaserPowerWatts = 525
        self._safePowerLimitWatts = 525
        self._numPulsesPerLevel = 10
        self._startingPowerLevel = 49  #bnr.startingPowerLevelTag.getValue()
        self._numPowerLevelSteps = 6 #bnr.numPowerLevelStepsTag.getValue()
        self._powerLevelIncrement = 24  #bnr.powerLevelIncrementTag.getValue()
        self._tolerancePercent = 30
        self._processTolerance = 5


    def setDefaultVerificationSettings(self):
        print("Changing to Verification Test Settings")
        self._pulseDelayMsec = 0
        self._pulseOnMsec = 5
        self._pulseOffMsec = 58
        self._availableLaserPowerWatts = 525
        self._safePowerLimitWatts = 525
        self._numPulsesPerLevel = 10
        self._startingPowerLevel = 97  #bnr.startingPowerLevelTag.getValue()
        self._numPowerLevelSteps = 3 #bnr.numPowerLevelStepsTag.getValue()
        self._powerLevelIncrement = 24 #bnr.powerLevelIncrementTag.getValue()
        self._tolerancePercent = 10
        self._processTolerance = 5

    def setDefaultCleanVerificationSettings(self):
        self._testType = 3
        self.setDefaultVerificationSettings()

    def setDefaultDirtyVerificationSettings(self):
        self._testType = 4
        self.setDefaultVerificationSettings()

    def addPixelList(self, pixelList):
        self._pixelList = [int(pixel) for pixel in list(pixelList)]

    def addCoefficients(self, expectedValueCFs):
        self._coefficients = np.array(expectedValueCFs)

    def _pixelListAsString(self):
        pixelList = [str(pixel) for pixel in self._pixelList]
        return ",".join(pixelList)

    def settingsAsDict(self):
        return {'Pulse Delay (ms)': self._pulseDelayMsec,
        'Pulse On (ms)': self._pulseOnMsec,
        'Pulse Off (ms)': self._pulseOffMsec,
        'Number of Pulses Per Level': self._numPulsesPerLevel,
        'Available Laser Power (W)': self._availableLaserPowerWatts,
        'Safe Power Limit (W)': self._safePowerLimitWatts,
        'Starting Power (8 Bit)': self._startingPowerLevel,
        'Number of Power Level Steps': self._numPowerLevelSteps,
        'Power Level Increment (8 Bit)': self._powerLevelIncrement,
        'Tolerance Band (%)': self._tolerancePercent,
        'Process Tolerance (%)': self._processTolerance,
        'Test Type': self._testType,
        'Pixel List': self._pixelList}

    def updateTestSettings(self,_pulseDelayMsec,_pulseOnMsec,_pulseOffMsec,_availableLaserPowerWatts,_safePowerLimitWatts,_numPulsesPerLevel,_startingPowerLevel,_numPowerLevelSteps,_powerLevelIncrement,_tolerancePercent,_testType,_pixelList, _processTolerance):
        self._pulseDelayMsec = _pulseDelayMsec
        self._pulseOnMsec = _pulseOnMsec
        self._pulseOffMsec = _pulseOffMsec
        self._availableLaserPowerWatts = _availableLaserPowerWatts
        self._safePowerLimitWatts = _safePowerLimitWatts
        self._numPulsesPerLevel = _numPulsesPerLevel
        self._startingPowerLevel = _startingPowerLevel
        self._numPowerLevelSteps = _numPowerLevelSteps
        self._powerLevelIncrement = _powerLevelIncrement
        self._tolerancePercent = _tolerancePercent
        self._testType = _testType
        self._processTolerance = _processTolerance
        self.addPixelList(_pixelList)
    
    def updateTestSettingsFromDict(self, testSettings):
        print(testSettings)
        self._pulseDelayMsec = testSettings['Pulse Delay (ms)'] 
        self._pulseOnMsec = testSettings['Pulse On (ms)']
        self._pulseOffMsec = testSettings['Pulse Off (ms)']
        self._numPulsesPerLevel = testSettings['Number of Pulses Per Level']
        self._availableLaserPowerWatts = testSettings['Available Laser Power (W)']
        self._safePowerLimitWatts = testSettings['Safe Power Limit (W)']
        self._startingPowerLevel = testSettings['Starting Power (8 Bit)']
        self._numPowerLevelSteps = testSettings['Number of Power Level Steps']
        self._powerLevelIncrement = testSettings['Power Level Increment (8 Bit)']
        self._tolerancePercent = testSettings['Tolerance Band (%)']
        self._processTolerance = testSettings['Process Tolerance (%)']
        self._testType = testSettings['Test Type']
        self._pixelList = testSettings['Pixel List']
            

