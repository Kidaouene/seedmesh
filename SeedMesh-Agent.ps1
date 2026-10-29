<#
.SYNOPSIS
  Agent SeedMesh pour Windows/PowerShell : cache SQLite (même schéma que seedmesh_cache.py)
  + appel llama.cpp. Match exact uniquement (pas d'embeddings), KV via --prompt-cache.
.EXAMPLE
  .\SeedMesh-Agent.ps1 -Prompt "Explique le KV cache" -Model C:\models\qwen.gguf -Kv -Refine 2
.NOTES
  Depuis llama.cpp b7348 l'ancien llama-cli s'appelle llama-completion (seul à garder --prompt-cache).
  Le hash doit rester identique à Python : sha256(NFC(prompt) espaces compactés + 0x1F + model + 0x1F + JSON canonique).
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)][string]$Prompt,
  [switch]$Gc,
  [double]$MaxMB = $(if ($env:SEEDMESH_MAX_MB) { [double]::Parse($env:SEEDMESH_MAX_MB, [Globalization.CultureInfo]::InvariantCulture) } else { 0 }),
  [string]$Model = $env:SEEDMESH_MODEL,
  [string]$Bin = $(if ($env:SEEDMESH_LLAMA_BIN) { $env:SEEDMESH_LLAMA_BIN } else { 'llama-completion.exe' }),
  [string]$Sqlite = $(if ($env:SEEDMESH_SQLITE) { $env:SEEDMESH_SQLITE } else { 'sqlite3.exe' }),
  [string]$SeedMeshHome = $(if ($env:SEEDMESH_HOME) { $env:SEEDMESH_HOME } else { Join-Path $HOME '.seedmesh' }),
  [string]$System = $env:SEEDMESH_SYSTEM,
  [int]$NPredict = 256,
  [double]$Temp = 0.2,
  [int]$Ctx = 2048,
  [int]$TimeoutSec = 300,
  [int]$Refine = 0,
  [switch]$Kv,
  [int]$Seed = 42,
  [double]$TopP = 0.9,
  [int]$TopK = 40,
  [double]$RepeatPenalty = 1.1,
  [int]$Threads = 4,
  [switch]$Raw,
  [switch]$NoCache,
  [string]$Config = $env:SEEDMESH_CONFIG
)
$ErrorActionPreference = 'Stop'
# --- config globale (même fichier/format que agent.py) : CLI > env > config.json > défauts
$cfgPaths = @($Config, $(if ($env:ProgramData) { Join-Path $env:ProgramData 'SeedMesh\config.json' }), '/opt/seedmesh/config.json',
  (Join-Path $HOME '.seedmesh/config.json')) | Where-Object { $_ }
$Cfg = $null
foreach ($cp in $cfgPaths) { if (Test-Path -LiteralPath $cp) { $Cfg = Get-Content -LiteralPath $cp -Raw -Encoding utf8 | ConvertFrom-Json; break } }
$Chat = -not $Raw
if ($Cfg) {
  $map = @{ NPredict = 'n_predict'; Temp = 'temp'; Ctx = 'ctx'; Seed = 'seed'; TopP = 'top_p'; TopK = 'top_k'; RepeatPenalty = 'repeat_penalty'; Threads = 'threads' }
  foreach ($k in $map.Keys) {
    $v = $Cfg.sampling.($map[$k])
    if (-not $PSBoundParameters.ContainsKey($k) -and $null -ne $v) { Set-Variable -Name $k -Value $v }
  }
  $prov = @($Cfg.providers | Sort-Object { if ($null -ne $_.priority) { $_.priority } else { 99 } })[0]
  if (-not $PSBoundParameters.ContainsKey('Model') -and -not $env:SEEDMESH_MODEL -and $prov.model) { $Model = $prov.model }
  if (-not $PSBoundParameters.ContainsKey('Bin') -and -not $env:SEEDMESH_LLAMA_BIN -and $prov.llama_completion_bin) { $Bin = $prov.llama_completion_bin }
  if (-not $PSBoundParameters.ContainsKey('SeedMeshHome') -and -not $env:SEEDMESH_HOME -and $Cfg.seedmesh_home) { $SeedMeshHome = $Cfg.seedmesh_home }
  if ($null -ne $Cfg.chat_template -and -not $Raw) { $Chat = [bool]$Cfg.chat_template }
}
[int]$NPredict = $NPredict; [double]$Temp = $Temp; [int]$Ctx = $Ctx; [int]$Seed = $Seed
[double]$TopP = $TopP; [int]$TopK = $TopK; [double]$RepeatPenalty = $RepeatPenalty; [int]$Threads = $Threads
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.UTF8Encoding]::new($false)
if (-not $System) { $System = '' }
$SeedMeshHome = [IO.Path]::GetFullPath($SeedMeshHome)
$Db = Join-Path $SeedMeshHome 'cache.db'
$KvDir = Join-Path $SeedMeshHome 'kv'
New-Item -ItemType Directory -Force -Path $SeedMeshHome, $KvDir | Out-Null
$ModelPath = if ($Model) { [IO.Path]::GetFullPath($Model) } else { '' }
$ModelId = if ($ModelPath) { [IO.Path]::GetFileName($ModelPath) } else { 'unknown' }
$Inv = [Globalization.CultureInfo]::InvariantCulture

function Invoke-Sql([string]$Sql, [switch]$Json) {
  $args_ = @($Db); if ($Json) { $args_ = @('-json', $Db) }
  $out = $Sql | & $Sqlite @args_
  if ($LASTEXITCODE -ne 0) { throw "sqlite3 a échoué : $out" }
  if ($Json) { if ($out) { return (($out -join "`n") | ConvertFrom-Json) } else { return @() } }
  return $out
}
function Q([string]$s) { "'" + $s.Replace("'", "''") + "'" }

# --- schéma identique à seedmesh_cache.py (PRAGMA user_version = 3)
$schema = @"
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS entries(
  id INTEGER PRIMARY KEY AUTOINCREMENT, prompt_hash TEXT NOT NULL UNIQUE, prompt TEXT NOT NULL,
  response TEXT NOT NULL, model TEXT NOT NULL DEFAULT '', params_json TEXT NOT NULL DEFAULT '{}',
  embedding BLOB, emb_model TEXT, created_at REAL NOT NULL, hits INTEGER NOT NULL DEFAULT 0, last_hit REAL);
CREATE INDEX IF NOT EXISTS idx_entries_model ON entries(model);
CREATE TABLE IF NOT EXISTS kv_snapshots(prefix_hash TEXT NOT NULL, path TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, PRIMARY KEY(prefix_hash, model));
CREATE INDEX IF NOT EXISTS idx_entries_last_hit ON entries(last_hit);
CREATE TABLE IF NOT EXISTS kv_prefixes(prefix_hash TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
  slot_file TEXT NOT NULL, n_turns INTEGER NOT NULL, created_at REAL NOT NULL, last_used REAL,
  PRIMARY KEY(prefix_hash, model));
"@
$ver = [int](Invoke-Sql 'PRAGMA user_version;' | Select-Object -Last 1)
if ($ver -lt 3) {
  Invoke-Sql $schema | Out-Null
  $cols = Invoke-Sql 'PRAGMA table_info(entries);' -Json | ForEach-Object { $_.name }
  if ($cols -notcontains 'emb_scale') { Invoke-Sql 'ALTER TABLE entries ADD COLUMN emb_scale REAL;' | Out-Null }
  # les embeddings float32 éventuels sont convertis en int8 par Python à la prochaine ouverture
  Invoke-Sql 'PRAGMA user_version=3;' | Out-Null
}

# --- LRU par taille (même formule que SeedMeshCache.size_bytes, ROW_OVERHEAD = 200)
$RowSize = "LENGTH(CAST(prompt AS BLOB))+LENGTH(CAST(response AS BLOB))+LENGTH(params_json)+COALESCE(LENGTH(embedding),0)+200"
function Invoke-Evict([double]$Mb) {
  if ($Mb -le 0) { return 0 }
  $limit = [long]($Mb * 1024 * 1024)
  $r = Invoke-Sql ("DELETE FROM entries WHERE id IN (SELECT id FROM (SELECT id, SUM($RowSize) OVER " +
    "(ORDER BY COALESCE(last_hit, created_at) DESC, id DESC) AS cum FROM entries) WHERE cum > $limit); SELECT changes();")
  [int]($r | Select-Object -Last 1)
}
function Invoke-Gc {
  $ev = Invoke-Evict $MaxMB; $dead = 0; $orph = 0
  foreach ($k in @(Invoke-Sql 'SELECT prefix_hash, model, path FROM kv_snapshots;' -Json)) {
    if (-not (Test-Path -LiteralPath $k.path)) {
      Invoke-Sql "DELETE FROM kv_snapshots WHERE prefix_hash=$(Q $k.prefix_hash) AND model=$(Q $k.model);" | Out-Null; $dead++ }
  }
  $refs = @{}
  foreach ($k in @(Invoke-Sql 'SELECT path FROM kv_snapshots;' -Json)) { $refs[[IO.Path]::GetFullPath($k.path)] = 1 }
  foreach ($k in @(Invoke-Sql 'SELECT slot_file FROM kv_prefixes;' -Json)) { $refs[[IO.Path]::GetFullPath((Join-Path $KvDir $k.slot_file))] = 1 }
  foreach ($f in Get-ChildItem -LiteralPath $KvDir -Filter *.bin -File) {
    if (-not $refs.ContainsKey($f.FullName)) { Remove-Item -LiteralPath $f.FullName; $orph++ }
  }
  [pscustomobject]@{ evicted = $ev; dead_kv_rows = $dead; orphan_files = $orph }
}

function Get-Sha256([string]$s) {
  $b = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($s))
  -join ($b | ForEach-Object { $_.ToString('x2') })
}
function Normalize([string]$p) { ($p.Normalize([Text.NormalizationForm]::FormC).Trim() -split '\s+' | Where-Object { $_ -ne '' }) -join ' ' }
function JsonStr([string]$s) {
  $sb = [Text.StringBuilder]::new('"')
  foreach ($ch in $s.ToCharArray()) {
    switch ($ch) {
      '"' { [void]$sb.Append('\"') } '\' { [void]$sb.Append('\\') }
      "`n" { [void]$sb.Append('\n') } "`r" { [void]$sb.Append('\r') } "`t" { [void]$sb.Append('\t') }
      "`b" { [void]$sb.Append('\b') } "`f" { [void]$sb.Append('\f') }
      default { if ([int]$ch -lt 0x20) { [void]$sb.Append(('\u{0:x4}' -f [int]$ch)) } else { [void]$sb.Append($ch) } }
    }
  }
  [void]$sb.Append('"'); $sb.ToString()
}
# JSON canonique = json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)
function CanonParams([hashtable]$h) {
  $parts = foreach ($k in ($h.Keys | Sort-Object -CaseSensitive { $_ } )) {
    $v = $h[$k]
    $js = if ($v -is [string]) { JsonStr $v }
          elseif ($v -is [bool]) { if ($v) { 'true' } else { 'false' } }
          elseif ($v -is [double]) { $r = $v.ToString('R', $Inv); if ($r -notmatch '[.eE]') { $r += '.0' }; $r }
          else { ([string]$v) }
    (JsonStr $k) + ':' + $js
  }
  '{' + ($parts -join ',') + '}'
}
function Get-PromptHash([string]$p, [string]$m, [string]$pj) { Get-Sha256 ((Normalize $p) + [char]0x1F + $m + [char]0x1F + $pj) }
function Now { ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0).ToString('R', $Inv) }

function Get-KvFile {
  $ph = (Get-Sha256 ($ModelId + [char]0x1F + $System)).Substring(0, 32)
  $row = Invoke-Sql "SELECT path FROM kv_snapshots WHERE prefix_hash=$(Q $ph) AND model=$(Q $ModelId);" -Json
  $p = if ($row -and (Test-Path $row[0].path)) { $row[0].path } else { Join-Path $KvDir "$ph.bin" }
  return @($ph, $p)
}

function Invoke-Llama([string]$p) {
  if (-not $ModelPath -or -not (Test-Path $ModelPath)) { throw "Modèle introuvable : '$ModelPath'" }
  $full = if ($System) { "$System`n`n$p" } else { $p }
  $a = @('-m', $ModelPath, '-n', $NPredict, '--temp', $Temp.ToString($Inv), '-c', $Ctx, '--no-display-prompt')
  if ($Chat) { $a += @('-st', '-p', $p); if ($System) { $a += @('-sys', $System) } } else { $a += @('-no-cnv', '-p', $full) }
  $a += @('--seed', $Seed, '--top-p', $TopP.ToString($Inv), '--top-k', $TopK, '--repeat-penalty', $RepeatPenalty.ToString($Inv), '-t', $Threads)
  if ($Kv) { $ph, $kvPath = Get-KvFile; $a += @('--prompt-cache', $kvPath, '--prompt-cache-all') }
  $psi = [Diagnostics.ProcessStartInfo]::new($Bin)
  foreach ($x in $a) { [void]$psi.ArgumentList.Add([string]$x) }   # PowerShell 7+ (gère le quoting)
  $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.UseShellExecute = $false
  $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
  $proc = [Diagnostics.Process]::Start($psi); $proc.StandardInput.Close()
  $outTask = $proc.StandardOutput.ReadToEndAsync(); $errTask = $proc.StandardError.ReadToEndAsync()
  if (-not $proc.WaitForExit($TimeoutSec * 1000)) { $proc.Kill($true); throw "llama.cpp timeout ($TimeoutSec s)" }
  if ($proc.ExitCode -ne 0) { throw "llama.cpp code $($proc.ExitCode) : $($errTask.Result)" }
  if ($Kv -and (Test-Path $kvPath)) {
    Invoke-Sql "INSERT OR REPLACE INTO kv_snapshots(prefix_hash,path,model,created_at) VALUES($(Q $ph),$(Q ([IO.Path]::GetFullPath($kvPath))),$(Q $ModelId),$(Now));" | Out-Null
  }
  $txt = (($outTask.Result -split "`r?`n") | Where-Object { $_ -notmatch '^\s*(llama_completion|main):\s' }) -join "`n"
  ($txt -replace '\s*\[end of text\]\s*$', '').Trim()
}

function Ask([string]$p, [string]$Step = 'answer') {
  $hp = @{ n_predict = $NPredict; temp = [double]$Temp; ctx = $Ctx; system = $System; step = $Step
    seed = $Seed; top_p = [double]$TopP; top_k = $TopK; repeat_penalty = [double]$RepeatPenalty }
  if ($Chat) { $hp.chat = $true }
  $pj = CanonParams $hp
  $h = Get-PromptHash $p $ModelId $pj
  $row = if ($NoCache) { $null } else { Invoke-Sql "SELECT id, response FROM entries WHERE prompt_hash=$(Q $h);" -Json }
  if ($row) {
    Invoke-Sql "UPDATE entries SET hits=hits+1, last_hit=$(Now) WHERE id=$($row[0].id);" | Out-Null
    Write-Verbose "cache exact [$Step]"; return $row[0].response
  }
  $resp = Invoke-Llama $p
  Invoke-Sql ("INSERT INTO entries(prompt_hash,prompt,response,model,params_json,created_at,hits) VALUES(" +
    "$(Q $h),$(Q $p),$(Q $resp),$(Q $ModelId),$(Q $pj),$(Now),0) ON CONFLICT(prompt_hash) DO UPDATE SET response=excluded.response;") | Out-Null
  if ($MaxMB -gt 0) { Invoke-Evict $MaxMB | Out-Null }   # LRU automatique après put
  $resp
}

if ($Gc) { Invoke-Gc; return }
if (-not $Prompt) { throw 'Paramètre -Prompt requis (ou -Gc)' }
$answer = Ask $Prompt 'answer'
for ($i = 1; $i -le $Refine; $i++) {
  $crit = Ask ("Question :`n$Prompt`n`nRéponse proposée :`n$answer`n`nCritique brièvement cette réponse (exactitude, clarté, complétude). Si elle est satisfaisante, réponds uniquement : OK") 'critique'
  Write-Verbose "itération $i critique : $crit"
  if ($crit.Trim().Trim('.', '!').ToUpper().StartsWith('OK')) { break }
  $answer = Ask ("Question :`n$Prompt`n`nRéponse précédente :`n$answer`n`nCritique :`n$crit`n`nRéécris une réponse améliorée en tenant compte de la critique. Donne seulement la réponse.") 'revise'
}
$answer
