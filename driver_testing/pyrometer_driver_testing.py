import time
from Model.OphirCom import OphirJunoCOM

if __name__ == '__main__':
    pyrometer = OphirJunoCOM()
    connectionSucceeded = pyrometer.connectToJuno()
    print('Connected' if connectionSucceeded else 'Failed to connect')
    print('Juno+ Serial Number: ', pyrometer.getJunoSerialNum())
    print('Juno+ Calibration Due Date: ', pyrometer.getJunoCalibrationDate())
    print('Pyrometer Serial Number: ', pyrometer.getPyrometerSerialNum())
    print('Pyrometer Calibration Due Date: ', pyrometer.getPyrometerCalibrationDate())
    if connectionSucceeded:
        print('Starting data collection for 5 seconds...')
        pyrometer.startDataCollection()
        time.sleep(5)
        pyrometer.updateData()
        pyrometer.endDataCollection()
        print('Printing data, up to 100 entries:')
        print(pyrometer.data[:100])
    else:
        print('Terminating without data collection due to failed device connection')
    