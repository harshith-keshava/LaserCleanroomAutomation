$AppRootPath = "$PSScriptRoot\.."
Set-Location $AppRootPath
.\venv\Scripts\activate
pyinstaller.exe .\setup\AutolaserCalibrationApplication.spec -y



