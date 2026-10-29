$t=$null;$e=$null
$ast=[Management.Automation.Language.Parser]::ParseFile('$PSScriptRoot/../SeedMesh-Agent.ps1',[ref]$t,[ref]$e)
"erreurs: $($e.Count)"; $e | % { $_.ToString() }
$Inv=[Globalization.CultureInfo]::InvariantCulture
$ast.FindAll({$args[0] -is [Management.Automation.Language.FunctionDefinitionAst]},$true) | % { . ([scriptblock]::Create($_.Extent.Text)) }
$pj = CanonParams @{ n_predict = 256; temp = [double]0.2; ctx = 2048; system = "Tu es `"bref`"`nété"; step = 'answer' }
$pj
Get-PromptHash "  Explique   le KV cache ! " 'm.gguf' $pj
