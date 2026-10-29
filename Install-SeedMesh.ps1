<#
.SYNOPSIS
  Installe SeedMesh sous Windows (x64, CPU) avec la MÊME config que la box (seed 42, local priorité 1).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\Install-SeedMesh.ps1            # machine (admin) -> C:\ProgramData\SeedMesh
  pwsh -File .\Install-SeedMesh.ps1 -Root "$HOME\SeedMesh" -Scope User      # sans admin
#>
[CmdletBinding()]
param(
  [string]$Root = (Join-Path $env:ProgramData 'SeedMesh'),
  [ValidateSet('Machine', 'User')][string]$Scope = 'Machine',
  [string]$LlamaTag = 'b11921',
  [int]$Threads = [Math]::Max(1, [Environment]::ProcessorCount / 2)
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Src = $PSScriptRoot
# PowerShell 7 (pwsh.exe) est requis par SeedMesh-Agent.ps1, même si cet installeur tourne sous Windows PowerShell 5.1
$Pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $Pwsh) {
  $Pwsh = @("$env:ProgramFiles\PowerShell\7\pwsh.exe", "$env:LOCALAPPDATA\Microsoft\WindowsApps\pwsh.exe") |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
if ($Pwsh) { Write-Host "PowerShell 7 détecté : $Pwsh" }
else { Write-Warning 'pwsh.exe (PowerShell 7) introuvable : winget install Microsoft.PowerShell, puis relancer cet installeur.' }
foreach ($id in 'SQLite.SQLite', 'Python.Python.3.12') {
  if (Get-Command winget -ErrorAction SilentlyContinue) { winget install -e --id $id --accept-source-agreements --accept-package-agreements | Out-Null }
}
$dirs = 'llama.cpp', 'models', 'app', 'data\kv', 'data\logs' | ForEach-Object { Join-Path $Root $_ }
New-Item -ItemType Directory -Force -Path $dirs | Out-Null
$llamaDir = Join-Path $Root "llama.cpp\$LlamaTag"
if (-not (Test-Path (Join-Path $llamaDir 'llama-completion.exe'))) {
  $zip = Join-Path $env:TEMP "llama-$LlamaTag.zip"
  Invoke-WebRequest "https://github.com/ggml-org/llama.cpp/releases/download/$LlamaTag/llama-$LlamaTag-bin-win-cpu-x64.zip" -OutFile $zip
  Expand-Archive $zip -DestinationPath $llamaDir -Force; Remove-Item $zip
}
$exe = Get-ChildItem $llamaDir -Recurse -Filter llama-completion.exe | Select-Object -First 1
$bin = $exe.DirectoryName
$model = Join-Path $Root 'models\qwen2.5-1.5b-instruct-q4_k_m.gguf'
if (-not (Test-Path $model)) {
  Invoke-WebRequest 'https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf' -OutFile $model
}
Copy-Item (Join-Path $Src '*.py'), (Join-Path $Src '*.ps1'), (Join-Path $Src 'README.md') (Join-Path $Root 'app') -Force
$cfg = [ordered]@{
  version   = 1
  providers = @(
    [ordered]@{ name = 'local'; priority = 1; type = 'llama.cpp'; model = $model
      llama_completion_bin = (Join-Path $bin 'llama-completion.exe'); llama_server_bin = (Join-Path $bin 'llama-server.exe')
      server_url = 'http://127.0.0.1:8080' },
    [ordered]@{ name = 'cloud'; priority = 2; type = 'remote'; note = 'seulement si le local échoue ou est insuffisant' })
  sampling  = [ordered]@{ seed = 42; temp = 0.0; top_p = 0.9; top_k = 40; repeat_penalty = 1.1; ctx = 4096; n_predict = 512; threads = $Threads }
  chat_template = $true
  seedmesh_home = (Join-Path $Root 'data')
  cache_server  = 'http://127.0.0.1:8765'
  max_mb        = 512
}
$cfgPath = Join-Path $Root 'config.json'
$cfg | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $cfgPath
$vars = @{ SEEDMESH_ROOT = $Root; SEEDMESH_HOME = (Join-Path $Root 'data'); SEEDMESH_CONFIG = $cfgPath; SEEDMESH_MAX_MB = '512'
  SEEDMESH_MODEL = $model; SEEDMESH_LLAMA_BIN = (Join-Path $bin 'llama-completion.exe'); SEEDMESH_PROVIDER_PRIORITY = 'local' }
foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $vars[$k], $Scope); Set-Item "env:$k" $vars[$k] }
if ($Scope -eq 'Machine') {  # DB partagée : écriture pour tous les utilisateurs
  icacls (Join-Path $Root 'data') /grant '*S-1-5-32-545:(OI)(CI)M' /T | Out-Null
}
# commande 'seedmesh' : seedmesh.cmd dans le dossier app, ajouté au PATH
$pwshFallback = if ($Pwsh) { $Pwsh } else { "$env:ProgramFiles\PowerShell\7\pwsh.exe" }
$cmd = @"
@echo off
setlocal
rem --- localise pwsh.exe (PowerShell 7) : PATH, puis chemin complet
set "PWSH="
for %%P in (pwsh.exe) do set "PWSH=%%~`$PATH:P"
if not defined PWSH if exist "$pwshFallback" set "PWSH=$pwshFallback"
if not defined PWSH if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if /I "%~1"=="ask" goto :ask
if /I "%~1"=="status" ( python "$Root\app\seedmesh_cache.py" --no-emb stats & goto :eof )
if /I "%~1"=="start" ( start "" /B "$bin\llama-server.exe" -m "$model" --host 127.0.0.1 --port 8080 -c 4096 -t $Threads -np 1 --slot-save-path "$Root\data\kv" & start "" /B python "$Root\app\seedmesh_cache.py" --no-emb serve & goto :eof )
python "$Root\app\agent.py" %*
goto :eof
:ask
if not defined PWSH (
  echo [SeedMesh] ERREUR : pwsh.exe ^(PowerShell 7^) introuvable. 1>&2
  echo [SeedMesh] Installez-le : winget install Microsoft.PowerShell  -- ou utilisez : python "$Root\app\agent.py" "question" 1>&2
  exit /b 9009
)
shift
set "ARGS="
:loop
if "%~1"=="" goto :run
set ARGS=%ARGS% %1
shift
goto :loop
:run
"%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "$Root\app\SeedMesh-Agent.ps1" %ARGS%
exit /b %ERRORLEVEL%
"@
Set-Content -Encoding Default (Join-Path $Root 'app\seedmesh.cmd') $cmd
$path = [Environment]::GetEnvironmentVariable('Path', $Scope)
if ($path -notlike "*$Root\app*") { [Environment]::SetEnvironmentVariable('Path', "$path;$Root\app", $Scope) }
Write-Host "OK. Nouveau terminal puis : seedmesh status ; seedmesh start ; seedmesh ask `"Bonjour`""
