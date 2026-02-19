# Quick start script for Windows
# Run: .\start.ps1

Write-Host "🚀 Starting AIRMAN Dispatch System..." -ForegroundColor Green

# Build and start
docker-compose up -d --build

# Wait for services
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 20

# Check health
$apiStatus = try { 
    $response = Invoke-WebRequest -Uri "http://localhost:8000" -UseBasicParsing
    "✅ API is running"
} catch { 
    "❌ API failed to start"
}

Write-Host $apiStatus -ForegroundColor $(if ($apiStatus -like "*✅*") { "Green" } else { "Red" })

Write-Host "`n📊 Services:" -ForegroundColor Cyan
Write-Host "  API:      http://localhost:8000"
Write-Host "  API Docs: http://localhost:8000/docs"
Write-Host "  Postgres: localhost:5432"
Write-Host "  Redis:    localhost:6379"

Write-Host "`n🔧 Quick commands:" -ForegroundColor Cyan
Write-Host "  View logs:  docker-compose logs -f"
Write-Host "  Stop:       docker-compose down"
Write-Host "  Rebuild:    docker-compose up -d --build"