# setup_postgres.ps1
# Script to set up a self-contained local portable PostgreSQL server in user space.

$ErrorActionPreference = "Stop"

$PgsqlDir = Join-Path $PSScriptRoot "pgsql"
$ZipFile = Join-Path $PSScriptRoot "postgresql-16.5-1-windows-x64-binaries.zip"
$DataDir = Join-Path $PgsqlDir "data"
$ServerLog = Join-Path $PgsqlDir "server.log"

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "     Setting up local PostgreSQL Server      " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. Download PostgreSQL zip if not already present
if (-not (Test-Path (Join-Path $PgsqlDir "bin\pg_ctl.exe"))) {
    if (-not (Test-Path $ZipFile)) {
        Write-Host "[1/4] Downloading PostgreSQL 16.5 portable binaries..." -ForegroundColor Yellow
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $webClient = New-Object System.Net.WebClient
        $webClient.Headers.Add("user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        try {
            $webClient.DownloadFile("https://get.enterprisedb.com/postgresql/postgresql-16.5-1-windows-x64-binaries.zip", $ZipFile)
            Write-Host "Download complete!" -ForegroundColor Green
        } catch {
            Write-Error "Failed to download PostgreSQL zip: $_"
            exit 1
        }
    }

    # 2. Extract ZIP
    Write-Host "[2/4] Extracting zip archive (this may take a minute)..." -ForegroundColor Yellow
    try {
        Expand-Archive -Path $ZipFile -DestinationPath $PSScriptRoot -Force
        Write-Host "Extraction complete!" -ForegroundColor Green
    } catch {
        Write-Error "Failed to extract PostgreSQL zip: $_"
        exit 1
    } finally {
        if (Test-Path $ZipFile) {
            Remove-Item $ZipFile -Force
        }
    }
} else {
    Write-Host "PostgreSQL binaries already exist at $PgsqlDir." -ForegroundColor Green
}

# 3. Initialize DB cluster
if (-not (Test-Path $DataDir)) {
    Write-Host "[3/4] Initializing PostgreSQL database cluster..." -ForegroundColor Yellow
    $initdb = Join-Path $PgsqlDir "bin\initdb.exe"
    try {
        # Configure local connections to trust for ease of development
        & $initdb -D $DataDir -U postgres --auth-local=trust --auth-host=trust
        Write-Host "Database cluster initialized successfully!" -ForegroundColor Green
    } catch {
        Write-Error "Failed to initialize DB cluster: $_"
        exit 1
    }
} else {
    Write-Host "Database data directory already exists at $DataDir." -ForegroundColor Green
}

# 4. Start PostgreSQL Server
Write-Host "[4/4] Starting PostgreSQL server..." -ForegroundColor Yellow
$pgctl = Join-Path $PgsqlDir "bin\pg_ctl.exe"
try {
    # Check if pg is already running
    $running = & $pgctl -D $DataDir status
    if ($running -match "server is running") {
        Write-Host "PostgreSQL is already running." -ForegroundColor Green
    } else {
        & $pgctl -D $DataDir -o "-p 5432" -l $ServerLog start
        Write-Host "PostgreSQL started successfully!" -ForegroundColor Green
    }
} catch {
    # If starting fails on port 5432, try 5433
    Write-Host "Port 5432 might be occupied. Trying port 5433..." -ForegroundColor Yellow
    try {
        & $pgctl -D $DataDir -o "-p 5433" -l $ServerLog start
        Write-Host "PostgreSQL started successfully on port 5433!" -ForegroundColor Green
    } catch {
        Write-Error "Failed to start PostgreSQL server: $_"
        exit 1
    }
}

# 5. Create database if it doesn't exist
Start-Sleep -Seconds 3
$createdb = Join-Path $PgsqlDir "bin\createdb.exe"
$port = 5432
$running = & $pgctl -D $DataDir status
if ($running -match "port 5433") {
    $port = 5433
}

Write-Host "Creating 'setu_reconciliation' database on port $port..." -ForegroundColor Yellow
try {
    # Run createdb, ignoring error if database already exists
    & $createdb -h localhost -p $port -U postgres setu_reconciliation 2>$null
    Write-Host "Database 'setu_reconciliation' is ready!" -ForegroundColor Green
} catch {
    Write-Host "Database 'setu_reconciliation' already exists or createdb completed." -ForegroundColor Green
}

Write-Host "=============================================" -ForegroundColor Green
Write-Host "PostgreSQL local server setup complete!" -ForegroundColor Green
Write-Host "Connection string: postgresql://postgres@localhost:$port/setu_reconciliation" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
