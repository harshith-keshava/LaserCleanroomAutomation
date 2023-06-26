
from Model.FTP_Manager import FTP_Manager
from numpy import genfromtxt
import pandas as pd 

class MachineSettings():

    _simulation = False
    _numberOfRacks = 4
    _numberOfLasersPerRack = 21
    _numberOfPixels = 84 #maximum number of lasers 4*21
    _16BitAnalogMaxPower = 2 ** 16
    _ipAddress = '192.168.200.50'
    _portNumber = '4850'
    _machineID = ""
    _factoryID = ""
    _vflcrIPs = ['192.168.210.51',
    '192.168.210.52', 
    '192.168.210.53', 
    '192.168.210.54']# [The IP addresses to the laser racks [1,2,3,4]]
    _vfpMap = FTP_Manager.readLUTFromPLC(_ipAddress, _simulation) # [[Pixel, Enable, Rack, Laser],........]
    _vfpmapDf = pd.DataFrame(_vfpMap, columns=["Pixel", "Enable", "Rack", "Laser"])
    def __init__(self) -> None:
        pass
    