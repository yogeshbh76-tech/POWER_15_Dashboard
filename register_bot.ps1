$python = "C:\power15_bot\venv\Scripts\python.exe"
$script = "C:\power15_bot\telegram_bot.py"
$dir    = "C:\power15_bot"

Unregister-ScheduledTask -TaskName "Power15_TelegramBot" -Confirm:$false -ErrorAction SilentlyContinue

$action   = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $dir
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Days 365) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Power15_TelegramBot" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force | Out-Null

Write-Host "Bot registered!" -ForegroundColor Green
Start-ScheduledTask -TaskName "Power15_TelegramBot"
Start-Sleep -Seconds 3
Write-Host "Bot state: " -ForegroundColor Cyan
Write-Host "Check Telegram for startup message!" -ForegroundColor Yellow
