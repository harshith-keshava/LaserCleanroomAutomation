
class MachineSettings():
    _simulation = False
    _16BitAnalogMaxPower = 2 ** 16
    _ipAddress = '192.168.200.50'
    _portNumber = '4850'
    _machineID = ""
    _factoryID = ""
    _vflcrIPs = ['192.168.210.51',
    '192.168.210.52', 
    '192.168.210.53', 
    '192.168.210.54']# [The IP addresses to the laser racks [1,2,3,4]]
    def __init__(self) -> None:
        pass
    