$AppRootPath = "$PSScriptRoot\.."
Set-Location $AppRootPath
python -m venv venv
.\venv\Scripts\activate
pip install -r .\setup\requirements.txt
$DeskTopPath=[Environment]::GetFolderPath("Desktop")
New-Item -ItemType SymbolicLink -Path $DeskTopPath -Name "LaserApplication.lnk" -Value "$AppRootPath\AutolaserCalibrationApplication.bat"
