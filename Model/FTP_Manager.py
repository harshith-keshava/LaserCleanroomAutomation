


from fileinput import filename
from ftplib import FTP
from io import BytesIO
import csv
import string
import numpy as np
import os
import re


class FTP_Manager():

    def __init__(self, ipAddress, username, passwd) -> None:
        self.ftpClient = FTP(ipAddress)
        self.ftpClient.login(user=username, passwd=passwd)
        
    def sendBinaryFile(self, ftpPath, localPath):
        print(ftpPath)
        self.ftpClient.storbinary('STOR '+ ftpPath, localPath)

    def listDirectory(self):
        return self.ftpClient.nlst("/MachineParameters")

    @staticmethod
    def lutsEmpty(ip_address):
        ftp = FTP_Manager(ip_address, 'admin', 'VFftp')
        return len(ftp.listDirectory()) == 0

    def readFile(self, path):
        r = BytesIO()
        self.ftpClient.retrbinary('RETR ' + path, r.write)
        return r.getvalue().decode('utf-8')
    
    @staticmethod
    def readLUTFromPLC(ip_address):
        if ip_address == "127.0.0.1":
            pixelMappingArray = np.genfromtxt("C:\\SIM\\PixelMapping\\PrinterPixelMap_DP1_1.vfpmap", delimiter=',', skip_header=1)
        else:
            ftp = FTP_Manager(ip_address, 'admin', 'VFftp')
            pmapfiles = [file for file in ftp.ftpClient.nlst('F:\\PixelMapping') if '.vfpmap' in file]
            currentPMAP = pmapfiles[0]
            pMapString = ftp.readFile('F:\\PixelMapping\\' + currentPMAP)
            pixelMappingReader = csv.reader(pMapString.split('\n'), delimiter=',')
            pixelMappingArray = np.array(list(pixelMappingReader)[1:-1], dtype=int)
        return pixelMappingArray

    @staticmethod
    def writeBinaryFileToVfplc(ip_address, binaryFilePath:string):
        ftp = FTP_Manager(ip_address, 'admin', 'VFftp')
        file = open(binaryFilePath,'rb') 
        filename = binaryFilePath.split('\\')[-1]
        ftp.sendBinaryFile("/MachineParameters/" + filename, file)


    @staticmethod
    def writeBinaryArrayToVfplc(ip_address, rackNumber, laserNumber, bits, CalID):
        ftp = FTP_Manager(ip_address, 'admin', 'VFftp')
        binaryFileStructure = "/MachineParameters/VF-LaserPowerLUT_R{rackNum}_P{laserNum}_ID{id}.vflpc"
        print(binaryFileStructure)
        binaryFileStructure = binaryFileStructure.format(rackNum=str(rackNumber).zfill(2), laserNum=str(laserNumber).zfill(2), id=str(CalID).zfill(5))
        binaryFile = BytesIO(bits)
        binaryFile.seek(0)
        ftp.sendBinaryFile(binaryFileStructure, binaryFile)
