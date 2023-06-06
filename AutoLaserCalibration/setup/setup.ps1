Set-Location C:\AutoLaserCalibration
python -m venv venv
.\venv\Scripts\activate
pip install -r .\setup\requirements.txt
$DeskTopPath=[Environment]::GetFolderPath("Desktop")
New-Item -ItemType SymbolicLink -Path $DeskTopPath -Name "LaserApplication.lnk" -Value "C:\AutoLaserCalibration\AutolaserCalibrationApplication.bat"
