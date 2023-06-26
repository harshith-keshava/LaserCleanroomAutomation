$AppRootPath = "$PSScriptRoot\.."
Set-Location $AppRootPath
py -3.7 -m venv venv
.\venv\Scripts\activate
python -m pip install --upgrade pip==23.1.2
pip install -r .\setup\requirements.txt
$DeskTopPath=[Environment]::GetFolderPath("Desktop")
New-Item -ItemType SymbolicLink -Path $DeskTopPath -Name "LaserApplication.lnk" -Value "$AppRootPath\AutolaserCalibrationApplication.bat"
