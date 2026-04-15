param(
    [ValidateSet("normal", "normal-office", "normal-branch", "normal-workday", "suspect", "suspect-dns", "scanning", "c2", "botnet", "exfiltration", "propagation", "ddos", "ddos-distributed", "mixed", "mixed-enterprise", "presentation")]
    [string]$Scenario = "mixed",
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [double]$Delay = 0.8,
    [int]$BatchSize = 1
)

$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "SentinelFlux test env" -ForegroundColor Cyan
Write-Host "Scenario : $Scenario"
Write-Host "Base URL : $BaseUrl"
Write-Host "Delay    : $Delay"
Write-Host "Batch    : $BatchSize"

python "$PSScriptRoot\replay_live.py" `
    --scenario $Scenario `
    --base-url $BaseUrl `
    --delay $Delay `
    --batch-size $BatchSize `
    --reset-live `
    --start-live
