<#
.SYNOPSIS
  Sync SeedMesh (PowerShell 7) : push/pull HTTP vers un `seedmesh_cache.py serve` distant. KV exclus.
.EXAMPLE
  .\Sync-SeedMesh.ps1 -Url http://192.168.1.20:8765 -Mode both
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$Url,
  [ValidateSet('push', 'pull', 'both')][string]$Mode = 'both',
  [string]$Sqlite = $(if ($env:SEEDMESH_SQLITE) { $env:SEEDMESH_SQLITE } else { 'sqlite3.exe' }),
  [string]$SeedMeshHome = $(if ($env:SEEDMESH_HOME) { $env:SEEDMESH_HOME } else { Join-Path $HOME '.seedmesh' }),
  [int]$Batch = 500
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.UTF8Encoding]::new($false)
$SeedMeshHome = [IO.Path]::GetFullPath($SeedMeshHome)
$Db = Join-Path $SeedMeshHome 'cache.db'
$StatePath = Join-Path $SeedMeshHome 'sync_state.json'
$Url = $Url.TrimEnd('/')
$Inv = [Globalization.CultureInfo]::InvariantCulture
if (-not (Test-Path $Db)) { throw "DB absente : $Db (lancer d'abord SeedMesh-Agent.ps1 ou seedmesh_cache.py)" }

function Invoke-Sql([string]$Sql, [switch]$Json) {
  $a = @($Db); if ($Json) { $a = @('-json', $Db) }
  $out = $Sql | & $Sqlite @a
  if ($LASTEXITCODE -ne 0) { throw "sqlite3 a échoué : $out" }
  if ($Json) { if ($out) { return (($out -join "`n") | ConvertFrom-Json) } else { return @() } }
  $out
}
function Q($s) { if ($null -eq $s) { 'NULL' } else { "'" + ([string]$s).Replace("'", "''") + "'" } }
function N($x) { if ($null -eq $x) { 'NULL' } else { ([double]$x).ToString('R', $Inv) } }

$state = if (Test-Path $StatePath) { Get-Content $StatePath -Raw | ConvertFrom-Json -AsHashtable } else { @{} }
if (-not $state.ContainsKey($Url)) { $state[$Url] = @{} }
$s = $state[$Url]; $result = [ordered]@{}

if ($Mode -in 'push', 'both') {
  $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0
  $where = if ($s.push_since) { "WHERE MAX(created_at, COALESCE(last_hit,0)) >= $(N $s.push_since)" } else { '' }
  $rows = @(Invoke-Sql ("SELECT prompt_hash,prompt,response,model,params_json,hex(embedding) AS emb_hex,emb_scale,emb_model," +
      "created_at,hits,last_hit FROM entries $where ORDER BY id;") -Json)
  $recs = foreach ($r in $rows) {
    $b64 = $null
    if ($r.emb_hex -and $null -ne $r.emb_scale) { $b64 = [Convert]::ToBase64String([Convert]::FromHexString($r.emb_hex)) }
    [ordered]@{ prompt_hash = $r.prompt_hash; prompt = $r.prompt; response = $r.response; model = $r.model
      params = ($r.params_json | ConvertFrom-Json -AsHashtable); embedding_b64 = $b64
      emb_scale = $(if ($b64) { $r.emb_scale }); emb_model = $(if ($b64) { $r.emb_model })
      created_at = $r.created_at; hits = $r.hits; last_hit = $r.last_hit }
  }
  $recs = @($recs); $tot = @{ inserted = 0; updated = 0; skipped = 0 }
  for ($i = 0; $i -lt $recs.Count; $i += $Batch) {
    $chunk = $recs[$i..([Math]::Min($i + $Batch, $recs.Count) - 1)]
    $body = @{ records = @($chunk) } | ConvertTo-Json -Depth 8 -Compress
    $r = Invoke-RestMethod -Method Post -Uri "$Url/put_batch" -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
    foreach ($k in 'inserted', 'updated', 'skipped') { $tot[$k] += [int]$r.$k }
  }
  $s.push_since = $now; $result.push = @{ sent = $recs.Count } + $tot
}

if ($Mode -in 'pull', 'both') {
  $q = if ($s.pull_since) { "?since=$(N $s.pull_since)" } else { '' }
  $r = Invoke-RestMethod -Uri "$Url/export$q"
  $sql = [Text.StringBuilder]::new("BEGIN;`n")
  foreach ($d in @($r.records)) {
    # params_json canonique fourni par le serveur (identique au calcul du hash)
    $pj = $d.params_json
    $emb = if ($d.embedding_b64) { "X'" + [Convert]::ToHexString([Convert]::FromBase64String($d.embedding_b64)) + "'" } else { 'NULL' }
    [void]$sql.AppendLine(("INSERT INTO entries(prompt_hash,prompt,response,model,params_json,embedding,emb_scale,emb_model,created_at,hits,last_hit) " +
      "VALUES($(Q $d.prompt_hash),$(Q $d.prompt),$(Q $d.response),$(Q $d.model),$(Q $pj),$emb,$(N $d.emb_scale),$(Q $d.emb_model)," +
      "$(N $d.created_at),$([int]$d.hits),$(N $d.last_hit)) ON CONFLICT(prompt_hash) DO UPDATE SET hits=MAX(entries.hits,excluded.hits), " +
      "last_hit=CASE WHEN entries.last_hit IS NULL THEN excluded.last_hit WHEN excluded.last_hit IS NULL THEN entries.last_hit " +
      "ELSE MAX(entries.last_hit,excluded.last_hit) END, " +
      "emb_scale=CASE WHEN entries.embedding IS NULL THEN excluded.emb_scale ELSE entries.emb_scale END, " +
      "emb_model=CASE WHEN entries.embedding IS NULL THEN excluded.emb_model ELSE entries.emb_model END, " +
      "embedding=COALESCE(entries.embedding, excluded.embedding);"))
  }
  [void]$sql.AppendLine('COMMIT;')
  Invoke-Sql $sql.ToString() | Out-Null
  $s.pull_since = $r.now; $result.pull = @{ received = @($r.records).Count }
}
$state | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 $StatePath
[pscustomobject]$result
