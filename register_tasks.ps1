$python = "C:\power15_bot\venv\Scripts\python.exe"
$dir    = "C:\power15_bot"

$tasks = @(
    @{ Name = "Power15_Scanner";       Args = "$dir\scanner.py";          Time = "15:30" },
    @{ Name = "Power15_BuyCheck";      Args = "$dir\buy_check.py";         Time = "15:25" },
    @{ Name = "Power15_SL_10AM";       Args = "$dir\buy_check.py --sl";    Time = "10:00" },
    @{ Name = "Power15_SL_1PM";        Args = "$dir\buy_check.py --sl";    Time = "13:00" },
    @{ Name = "Power15_SellAlert";     Args = "$dir\sell_alert.py";        Time = "16:00" }
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Power 15 — Register Scheduled Tasks" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($t in $tasks) {
    Unregister-ScheduledTask -TaskName $t.Name -Confirm:$false -ErrorAction SilentlyContinue

    $action   = New-ScheduledTaskAction -Execute $python -Argument $t.Args -WorkingDirectory $dir
    $trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $t.Time
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable

    Register-ScheduledTask `
        -TaskName $t.Name `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -RunLevel Highest `
        -Force | Out-Null

    Write-Host "  Registered: $($t.Name) at $($t.Time)" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  All 5 tasks registered!" -ForegroundColor Green
Write-Host ""
Write-Host "  Mon-Fri schedule:" -ForegroundColor White
Write-Host "  10:00 AM  SL check (intraday)" -ForegroundColor White
Write-Host "   1:00 PM  SL check (intraday)" -ForegroundColor White
Write-Host "   3:25 PM  Buy check" -ForegroundColor White
Write-Host "   3:30 PM  Scanner" -ForegroundColor White
Write-Host "   4:00 PM  Sell alert / hybrid exits" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
