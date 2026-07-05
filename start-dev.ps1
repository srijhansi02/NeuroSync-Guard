$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repo

Write-Host "Starting backend..."
Start-Process powershell -ArgumentList '-NoExit','-Command',"Set-Location '$repo'; python app.py" | Out-Null

Write-Host "Starting frontend..."
Start-Process powershell -ArgumentList '-NoExit','-Command',"Set-Location '$repo'; npm run dev -- --host 0.0.0.0" | Out-Null

Write-Host "Both services started."
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend: http://localhost:5001"
