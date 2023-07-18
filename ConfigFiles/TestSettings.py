
#TODO: link plc pulse settings to power limits

import numpy as np

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
        #self.addPixelList(_pixelList)
