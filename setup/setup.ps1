$AppRootPath = "$PSScriptRoot\.."
Set-Location $AppRootPath
py -3.7 -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip==10.0.1
pip install -r .\setup\requirements-pip-10-0-1.txt
python -m pip install --upgrade pip==23.1.2
pip install -r .\setup\requirements-pip-23-1-2.txt
$DeskTopPath=[Environment]::GetFolderPath("Desktop")
$WScriptObj = New-Object -ComObject ("WScript.Shell")
$shortcut = $WScriptObj.CreateShortcut("$DesktopPath\LaserApplication.lnk")
$shortcut.TargetPath = "$AppRootPath\AutolaserCalibrationApplication.bat"
$shortcut.IconLocation = "$AppRootPath\setup\laserbeam_laser_4058.ico"
$shortcut.Save()
#New-Item -ItemType SymbolicLink -Path $DeskTopPath -Name "LaserApplication.lnk" -Value "$AppRootPath\AutolaserCalibrationApplication.bat"
