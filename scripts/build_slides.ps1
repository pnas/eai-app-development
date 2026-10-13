# Automated Slide Builder for Production GenAI API Integrations Course
# Compiles Marp markdown decks in slides/ to interactive HTML presentation decks in dist/slides/

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " Building Presentation Slides (Marp CLI)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$InputDir = "slides"
$OutputDir = "dist/slides"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
}

Write-Host ">>> Compiling slides from '$InputDir' to '$OutputDir'..." -ForegroundColor Yellow

npx --yes @marp-team/marp-cli --no-stdin --input-dir $InputDir -o $OutputDir

if ($LASTEXITCODE -eq 0) {
    $decks = Get-ChildItem -Path $OutputDir -Filter "*.html"
    Write-Host "`n>>> Successfully built all $($decks.Count) presentation decks in $($OutputDir):" -ForegroundColor Green
    $decks | ForEach-Object {
        Write-Host "  - $($_.Name) ($([math]::Round($_.Length / 1KB, 1)) KB)" -ForegroundColor Gray
    }
    Write-Host "`nOpen any HTML file in your browser to present!" -ForegroundColor Cyan
} else {
    Write-Host "`n[ERROR] Slide compilation failed with code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}
