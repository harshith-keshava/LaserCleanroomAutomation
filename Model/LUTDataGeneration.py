
from datetime import datetime
from ConfigFiles.TestSettings import TestSettings
import numpy as np
import pandas as pd
from datetime import datetime
import zlib
from io import BytesIO
from ConfigFiles.MachineSettings import MachineSettings
import os
from Model.FTP_Manager import FTP_Manager
from Model.LaserSettings import LaserSettings
from io import BytesIO
import numpy as np
import os
import pandas as pd
from datetime import datetime

class LUTDataManager():
    
    def __init__(self, testSettings:TestSettings) -> None:
        self.testSettings = testSettings
        self.linearLut =np.round(np.linspace(0,1,256) * MachineSettings._16BitAnalogMaxPower,0) #convert to 65535 scale and apply threshold
        self.linearLut[self.linearLut>np.round(MachineSettings._16BitAnalogMaxPower * self.testSettings._powerModifiedLimit)] = np.round(MachineSettings._16BitAnalogMaxPower * self.testSettings._powerModifiedLimit,0)
        self.powerLuts = None
        self.lutStatus = []
        self.binaries = None
        self.rawLaserData = None
        self.results_coeff = None
        self.results_lut = None
        if not os.path.exists('tmp'):
                os.makedirs('tmp', 0o700)

    def changeTestSettings(self, testSettings):
        self.testSettings = testSettings

    def convertLUTDataToBinary(self, lutData):
        bites=lutData.tobytes()
        crccode=zlib.crc32(bites)
        ba=bytearray(crccode.to_bytes(4, 'little'))
        crcbites=np.asarray(ba).tobytes()
        binaryLUT = bites+crcbites
        return binaryLUT

    def scaledLUTfromCoeff(self, coefficients, pixel):
        #inialize an array with values of 0 to 256 (8bits) with increments of 1
        powerperct=np.linspace(0,1,256)
        #convert the power modified limit into a 16 bit number for the output scaling 
        powerModifiedLimit16Bit = int(MachineSettings._16BitAnalogMaxPower  * self.testSettings._powerModifiedLimit) - 1
        #adjust the linear values with the calculated best fit coefficients for that pixel
        adjpower=coefficients[0]*powerperct*powerperct+coefficients[1]*powerperct+coefficients[2]
        scaledpower=np.round_(adjpower*MachineSettings._16BitAnalogMaxPower,0) #scale all values to 0-65535 scale for VFLCR
        scaledpower[scaledpower > powerModifiedLimit16Bit] = powerModifiedLimit16Bit #apply upper threshold
        scaledpower[scaledpower < 0] = 0 # apply lower threshold
        scaledpower = scaledpower.astype(np.uint16)
        if powerModifiedLimit16Bit in scaledpower:
            powerCalledIndex = list(scaledpower).index(powerModifiedLimit16Bit)
        else:
            powerCalledIndex = len(scaledpower)
        powerCalledThresholdIndex = int(np.round(self.testSettings._powerCalledLimit*255,0))
        lutScaledData = scaledpower
        if coefficients[1] != 1:
            self.lutStatus[pixel] = ("Power Scaled")
        if powerCalledIndex < powerCalledThresholdIndex:
            self.lutStatus[pixel] = ("Power Called Failure") 
        return lutScaledData
        
    def convertLaserDataToLUTData(self, laserCalibrationData, commandedPowerData, lasertestStatus, calID, laserSettings: LaserSettings, saveLocation=None,time=None):
        #Get current time for the purpose of file naming and database tags
        time=datetime.now()
        #Convert the test settings into distinct power levels in WATTS to be able to split the raw data up and compare the values 
        commandedPowerLevels = np.array([(self.testSettings._startingPowerLevel + self.testSettings._powerLevelIncrement * powerLevel) * 525/255 for powerLevel in range(self.testSettings._numPowerLevelSteps)])        
        #grab parameters from the PLC
        #get pulse time and max power
        MaxPower = self.testSettings._availableLaserPowerWatts
        # 0, 1, 0 is the default quadratic coefficients i.e. a linear line for the LUT for the lasers
        linearCoefficients = [0, 1, 0]
        #create master coefficient matrix for the lasers; Shape = [Pixels x 3] = [[Coeff1_Pixel1, Coeff2_Pixel1, Coeff3_Pixel1], ..... ,[Coeff1_Pixel147, Coeff2_Pixel147, Coeff3_Pixel147]]
        CFMatrix=np.asarray([linearCoefficients for pixel in range(laserSettings.numberOfPixels)], dtype=float)
        #initialize a default array of statuses with the default as untested and overwrite the index with the test status when the pixel is processed 
        self.lutStatus = ["Untested" for pixel in range(laserSettings.numberOfPixels)]
        #Coefficient calculation for loop
        #Loop through the laser data for each pixel splitting the data by its power levels and average value per power level. 
        #Using the average value for each power level, make a quadratic best fit
        for pixelNum, pixelrawdata in enumerate(laserCalibrationData):
            if(lasertestStatus[pixelNum] == 1):   
                pulseChangeIndexes = [pwrIdx + 1 for pwrIdx, powerDiff in enumerate(np.diff(commandedPowerData[pixelNum])) if powerDiff > 0]
                pulseChangeIndexes.insert(0,0)
                pulseChangeIndexes.append(len(pixelrawdata) + 1)
                pulseSplitData = [pixelrawdata[pulseChangeIndexes[idx]:pulseChangeIndexes[idx+1]] for idx in range(len(pulseChangeIndexes)-1)]
                if [] not in pulseSplitData:
                    pulseAverages = [np.mean(pulses)/MaxPower for pulses in pulseSplitData]
                    #quadratic solve for the needed coefficients
                    ce=np.polyfit(pulseAverages,commandedPowerLevels/MaxPower,2)
                    #store the coefficients in the appropriate matrix and row
                    CFMatrix[pixelNum][0] = float(ce[0])
                    CFMatrix[pixelNum][1] = float(ce[1])
                    CFMatrix[pixelNum][2] = float(ce[2])
            elif(lasertestStatus[pixelNum] == 5):
                self.lutStatus[pixelNum] = "Untested"
            else:
                self.lutStatus[pixelNum] = "Power Tolerance Failure"
        #Generate LUT Power data for each laser for each rack into a single numpy array (Shape = (7,21,256) for rack, laser, power data point)
        luts = np.asarray([self.scaledLUTfromCoeff(CFMatrix[pixel], pixel) for pixel in range(laserSettings.numberOfPixels)], dtype = np.uint16)
        self.powerLuts = luts
        results_coeff = []
        results_lut = []
        for pixelNum in range(laserSettings.numberOfPixels):
            pixel, enable, rack, laser = laserSettings.vfpMap[pixelNum]
            results_coeff.append([pixel, rack, laser, CFMatrix[pixelNum][0], CFMatrix[pixelNum][1], CFMatrix[pixelNum][2]])
            for dataPoint in range(0,256):
                results_lut.append([time.strftime("%Y-%m-%d,%H:%M:%S"), MachineSettings._machineID, MachineSettings._factoryID, pixel, rack, laser, self.lutStatus[pixelNum], CFMatrix[pixelNum][0], CFMatrix[pixelNum][1], CFMatrix[pixelNum][2], dataPoint, np.int32(luts[pixelNum][dataPoint])])
                #make this a single dataframe
        self.results_coeff = pd.DataFrame(results_coeff, columns=["Pixel", "Rack", "Laser", "a", "b", "c"]) # add printer name, calibration, timestamp only this, power modified limit (round to 2), max power for each laser, bitpower and bitnumber
        self.results_lut = pd.DataFrame(results_lut, columns=["DateTime", "Machine ID", "Factory ID", "Pixel", "Rack", "Laser", "Status", "a", "b", "c", "BitNumber", "BitPower"]) 
        self.results_coeff.to_csv("tmp\\LUT_Coeff.csv", index=False)
        self.results_lut.to_csv("tmp\\LUT_Raw.csv", index=False)  
        if saveLocation is not None:
            self.results_coeff.to_csv(saveLocation + "\\LUT_Coeff.csv")
            self.results_lut.to_csv(saveLocation + "\\LUT_Raw.csv")  
        return luts

    def writeLUTDataToFolder(self, calID, csvPath=None, luts=None):
        #Save LUT Data into a single file for documentation/data purposes
        if luts is None:
            luts = self.powerLuts
        now=datetime.now()
        if csvPath is None:
            if MachineSettings._simulation:
                csvPath = '.\\tmp\\LUTDataGeneration\\CSV'
            else:
                csvPath = '.\\tmp\\CSV'
            if not os.path.isdir(csvPath):
                os.mkdir(csvPath)
        if luts is None:
            luts = self.powerLuts

    def convertLUTDataToBinaries(self, luts=None):
        #Generate binary arrays for each laser in each rack into a list (Shape = (7,21,1), for rack, laser, bytes
        if luts is None:
            luts = self.powerLuts
        binaries = [self.convertLUTDataToBinary(lut) for lut in luts]
        np.save('tmp\\bin', binaries)
        self.binaries = binaries
        return binaries

    def writeBinariesToFolder(self, calID, laserSettings: LaserSettings, binaries=None, binPath = None):
        if binaries is None:
            binaries = self.binaries
        if not os.path.isdir('tmp\\bin\\'):
            os.mkdir('tmp\\bin\\')
        [os.remove('tmp\\bin\\' + file) for file in os.listdir('tmp\\bin\\')]
        for pixelNum, binary in enumerate(binaries):
            pixel, enable, rack, laser = laserSettings.vfpMap[pixelNum]
            self.writeBinaryArrayToFile(int(rack), int(laser), binary, calID, 'tmp\\bin\\')
        #Write binaries for each laser to their own file with the name format being VF-LaserPowerLUT_R{rackNum}_P{laserNum}_ID{id}.vflpc
        if binPath is not None:
            if not os.path.isdir(binPath):
                os.mkdir(binPath)
            for pixelNum, binary in enumerate(binaries):
                pixel, enable, rack, laser = laserSettings.vfpMap[pixelNum]
                self.writeBinaryArrayToFile(rack, laser, binary, calID, binPath)
        

    def writeBinaryArrayToFile(self, rackNumber, laserNumber, bits, CalID, path):
        binaryFile = BytesIO(bits)
        with open(path + "\\VF-LaserPowerLUT_R{rackNum}_L{laserNum}_ID{id}.vflpc".format(rackNum=str(int(rackNumber)).zfill(2), laserNum=str(int(laserNumber)).zfill(2), id=str(CalID).zfill(5)), 'wb') as outfile:
            outfile.write(binaryFile.getbuffer())
        binaryFile.seek(0)

    def uploadLinearLuts(self, laserSettings: LaserSettings):
        powerModifiedLimit16Bit = MachineSettings._16BitAnalogMaxPower  * self.testSettings._powerModifiedLimit
        powerperct=np.linspace(0,1,256)
        lineardata=np.round(powerperct * MachineSettings._16BitAnalogMaxPower,0) #convert to 65535 scale and apply threshold
        lineardata[lineardata>np.round(powerModifiedLimit16Bit)] = np.round(powerModifiedLimit16Bit,0)
        luts = np.asarray([lineardata for pixel in range(laserSettings.numberOfPixels)], dtype = np.uint16)
        bins = self.convertLUTDataToBinaries(luts)
        self.writeBinaryArraysToVFPLCs(99999, bins)

    def writeBinaryArraysToVFPLCs(self, lutNumber, laserSettings: LaserSettings, binaries=None):
        if binaries is None:
            binaries = self.binaries
        vflcrs = MachineSettings._vflcrIPs
        for rack in range(4):
            for laser in range(21):
               FTP_Manager.writeBinaryArrayToVfplc(vflcrs[rack],rack+1,laser+1,binaries[-1], lutNumber) 
        for pixelNum, binary in enumerate(binaries):
            pixel, enable, rack, laser = laserSettings.vfpMap[pixelNum]
            print("Sending data to VFLCR")
            FTP_Manager.writeBinaryArrayToVfplc(vflcrs[rack-1],rack,laser,binary, lutNumber)
            

    def _generateSaveDir(self, calID):
        now = datetime.now()
        date = now.strftime("%Y%m%d")
        drivePath = os.path.join(".", "tmp", "printerinfo", MachineSettings._factoryID, MachineSettings._machineID,"Laser Data", "30_Calibrations", MachineSettings._machineID + "_LUT_" + str(calID).zfill(5)+"_"+date)
        return drivePath
        
    def getResultsLUT(self):
        return self.results_lut
    
    def getResultsCoeffLUT(self):
        return self.results_coeff
    
    @staticmethod
    def percentDiff(numA, numB):
        if numA == numB:
            return 0
        try:
            return (abs(numA - numB) / numB) * 100.0
        except ZeroDivisionError:
            return float('inf')

