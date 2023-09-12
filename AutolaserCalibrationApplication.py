from Model.Model import Model
from Model.Model import LaserSettings
from ConfigFiles.TestSettings import TestSettings
from ConfigFiles.MachineSettings import MachineSettings
from time import sleep

try:
    from ctypes import windll  # Only exists on Windows.
    myappid = 'mycompany.myproduct.subproduct.version'
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

c = TestSettings()
s = MachineSettings()
l = LaserSettings()
m = Model(s,c,l)

if __name__ == '__main__':
    m.connectToPlc()
    
    # Monitor connection by checking heartbeat
    try:
        previousHeartbeat = -1 # initial value that won't match the unsigned heartbeat tag
        while previousHeartbeat != m.heartBeatIntag.value:
            previousHeartbeat = m.heartBeatIntag.value
            sleep(2)
        print("Loss of connection detected; exiting application")

    except Exception as e:
        # If the OPCUA connection is lost, reading from a tag will raise an exception
        # This is actually the typical mode of detecting a lost connection
        print(e)

    finally:
        # Disconnect the client so its threads (and by extension, this script) terminate
        try:
            m.client.disconnect()
        except:
            # If the app isn't connected, including by loss of a prior connection, disconnect will raise an exception
            # This case is nominal and requires no further action
            pass
    