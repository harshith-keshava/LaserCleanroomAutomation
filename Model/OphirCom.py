# Use of Ophir COM object. 
# Works with python 3.5.1, 2.7.11, & 3.10.6
# Uses pywin32
import win32com.client
import time
import traceback

class OphirJunoCOM:
    
    def __init__(self) -> None:
        try:
            self.OphirCOM = win32com.client.Dispatch("OphirLMMeasurement.CoLMMeasurement")
            self.OphirCOM.StopAllStreams()
            self.OphirCOM.CloseAll()
        except OSError as err:
            self.OphirCOM = None
            print("OS error: {0}".format(err))
        except:
            self.OphirCOM = None
            #traceback.print_exc()

        self.isConnected = False
        self.isStreaming = False
        self.data = tuple()
        self.newestDataPeak = (None, None, None)
    
    def connectToJuno(self):
        if self.isConnected: # disconnect before re-connecting
            self.disconnectJuno()
        if self.OphirCOM == None:
            DeviceList = []
        else:
            DeviceList = self.OphirCOM.ScanUSB()
        if len(DeviceList) == 0:
            self.isConnected = False
            return False
        for Device in DeviceList:   	# if any device is connected
            self.DeviceHandle = self.OphirCOM.OpenUSBDevice(Device)	# open first device
            exists = self.OphirCOM.IsSensorExists(self.DeviceHandle, 0)
            if exists:
                self.JunoSerialNum = self.OphirCOM.GetDeviceInfo(self.DeviceHandle)[2]
                self.JunoSerialCalibrationDate = str(self.OphirCOM.GetDeviceCalibrationDueDate(self.DeviceHandle)).split(' ')[0]
                self.PyrometerSerialNum = self.OphirCOM.GetSensorInfo(self.DeviceHandle, 0)[0]
                self.PyrometerSerialCalibDate = str(self.OphirCOM.GetSensorCalibrationDueDate(self.DeviceHandle, 0)).split(' ')[0]
                self.isConnected = True
                return True
        # Reaching here means no devices with sensors are connected
        return False
    
    def getJunoSerialNum(self):
        if self.isConnected:
            return self.JunoSerialNum
        else:
            return ""
    
    def getPyrometerSerialNum(self):
        if self.isConnected:
            return self.PyrometerSerialNum
        else:
            return ""
    
    def getJunoCalibrationDate(self):
        if self.isConnected:
            return self.JunoSerialCalibrationDate
        else:
            return ""
    
    def getPyrometerCalibrationDate(self):
        if self.isConnected:
            return self.PyrometerSerialCalibDate
        else:
            return "" 
    
    def disconnectJuno(self):
        self.OphirCOM.StopAllStreams()
        self.OphirCOM.CloseAll()
        self.isConnected = False
    
    def startDataCollection(self):
        self.OphirCOM.StartStream(self.DeviceHandle, 0)
    
    def updateData(self):
        # Data should be a sequence of triples for ease of use
        newValues, newTimestamps, newStatuses = self.OphirCOM.GetData(self.DeviceHandle, 0)
        newData = tuple(zip(newValues, newTimestamps, newStatuses))#remove strict as it wasn't introduced yet in 3.7.9#, strict=True)) # set strict mostly as an assertion that all 3 data tuples are the same length
        self.newestDataPeak = max(newData, default=self.newestDataPeak, key=lambda tup:tup[0]) # if new data is empty, keep old peak
        self.data += newData
    
    def getFullData(self, update=True):
        if update:
            self.updateData()
        return self.data
    
    def getLastDataPoint(self, update=True):
        if update:
            self.updateData()
        return self.data[-1]
    
    def getLastDataPeak(self, update=True):
        if update:
            self.updateData()
        return self.newestDataPeak
    
    def getFullDataPeak(self, update=True):
        if update:
            self.updateData()
        return max(self.data, default=(None, None, None), key=lambda tup:tup[0])
    
    def endDataCollection(self):
        self.OphirCOM.StopStream(self.DeviceHandle, 0)
    
    def quickStart(self):
        # Go from object creation straight to streaming data
        if self.connectToJuno():
            self.startDataCollection()
            return True
        return False
    
    def quickEnd(self, update=True):
        # Go from streaming data straight to disconnected
        # At the time of writing, this function isn't strictly necessary, it just pairs nicely with quickStart
        if update:
            self.updateData()
        return self.disconnectJuno()
    
    def clearData(self):
        self.data = tuple()
        self.newestDataPeak = (None, None, None)

