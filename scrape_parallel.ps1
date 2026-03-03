# VkusVill Parallel Scraper
# This avoids the WinError 32 chromedriver file lock issue
# Suppress PowerShell NativeCommandError — Python warnings go to stderr
# which PowerShell would otherwise treat as an error and kill the process
$ErrorActionPreference = "Continue"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "VkusVill PARALLEL Scraper with Claude Subagents" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$projectPath = $PSScriptRoot

# Run all 3 scrapers in parallel using subagents
Write-Host "`n🚀 Launching 3 parallel scraper subagents..." -ForegroundColor Yellow

$jobs = @(
    @{Name="Green"; Script="python scrape_green.py"},
    @{Name="Red"; Script="python scrape_red.py"},
    @{Name="Yellow"; Script="python scrape_yellow.py"}
) | ForEach-Object {
    $task = $_
    Start-Job -ScriptBlock {
        param($path, $script, $name)
        Set-Location $path
        Write-Output "[$name] Starting..."
        # Create logs directory if not exists
        New-Item -ItemType Directory -Force -Path "logs" | Out-Null

        # Run python script redirecting all output (stdout+stderr) to log file
        # Using cmd /c avoids PowerShell NativeCommandError on Python warnings
        $logFile = "logs\$($name.ToLower()).log"
        cmd /c "$script > $logFile 2>&1"

        Write-Output "[$name] Completed"
    } -ArgumentList $projectPath, $task.Script, $task.Name

    # Stagger start times to reduce race conditions on driver patching
    Start-Sleep -Seconds 5
}

Write-Host "⏳ Waiting for all scrapers to complete..." -ForegroundColor Yellow

# Wait for all jobs
$jobs | Wait-Job | Out-Null

# Get results
Write-Host "`n📊 Results:" -ForegroundColor Green
foreach ($job in $jobs) {
    $result = Receive-Job -Job $job
    Write-Host $result
}

# Cleanup jobs
$jobs | Remove-Job

# Merge results
Write-Host "`n🔀 Merging all products..." -ForegroundColor Yellow
Set-Location $projectPath
python scrape_merge.py

Write-Host "`n✅ Done!" -ForegroundColor Green
