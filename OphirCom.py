# Use of Ophir COM object. 
# Works with python 3.5.1 & 2.7.11
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
         print("OS error: {0}".format(err))
      except:
         traceback.print_exc()
   
   def connectToJuno(self):
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
            self.PyrometerSerialNum = self.OphirCOM.GetSensorInfo(self.DeviceHandle,0)[0]
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

