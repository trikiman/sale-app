# Start Chrome for scrapers — MUST run from top-level PowerShell/bat.
# Python's subprocess chain cannot launch Chrome (CreateProcessW issue).
#
# Called by run_app.bat BEFORE the scheduler service.
# Chrome will listen on port 19222 for CDP connections from scrapers.

$ErrorActionPreference = "SilentlyContinue"

$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$Port = 19222
$ProfileDir = Join-Path $env:TEMP "uc_scraper_$Port"

# Check if already running on this port
try {
    $tc = New-Object Net.Sockets.TcpClient
    $tc.Connect('127.0.0.1', $Port)
    $tc.Close()
    Write-Host "Chrome already running on port $Port"
    exit 0
} catch {
    # Port not open, need to launch
}

# Check if SCRAPER_PROXY env var is set (from proxy_manager.py)
$ProxyArg = $env:SCRAPER_PROXY
if ($ProxyArg) {
    Write-Host "Starting Chrome on port $Port with proxy: $ProxyArg"
} else {
    Write-Host "Starting Chrome on port $Port (direct, no proxy)..."
}

$ChromeArgs = @(
    "--remote-debugging-port=$Port",
    "--user-data-dir=$ProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-features=IsolateOrigins,site-per-process,LocalNetworkAccessChecks",
    "--disable-blink-features=AutomationControlled",
    "--window-size=1280,720"
)

# Add proxy flag if set
if ($ProxyArg) {
    $ChromeArgs += "--proxy-server=$ProxyArg"
}

Start-Process -FilePath $ChromePath -ArgumentList $ChromeArgs

# Wait for CDP endpoint to become available
Write-Host "Waiting for Chrome CDP..."
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep 1
    try {
        $tc = New-Object Net.Sockets.TcpClient
        $tc.Connect('127.0.0.1', $Port)
        $tc.Close()
        Write-Host "Chrome ready on port $Port!"
        exit 0
    } catch {}
}

Write-Host "WARNING: Chrome may not have started properly on port $Port"
