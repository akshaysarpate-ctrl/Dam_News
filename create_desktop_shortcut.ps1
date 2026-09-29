$wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop "Start Dam News Watch.lnk"
$sc = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath = "d:\NDSA\dam_news_R1\dam_news\start.bat"
$sc.WorkingDirectory = "d:\NDSA\dam_news_R1\dam_news"
$sc.Description = "Launch Dam Failure News Watch Application"
$sc.IconLocation = "shell32.dll,14"
$sc.Save()
Write-Host "Created Desktop shortcut: $shortcutPath"
