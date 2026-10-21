param([Parameter(Mandatory=$true)][string]$Database,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$conn=New-Object -ComObject ADODB.Connection
try {
  $conn.Open("Provider=Microsoft.ACE.OLEDB.12.0;Data Source=$Database;Mode=Read;")
  $schema=$conn.OpenSchema(20)
  $names=@()
  while(-not $schema.EOF) {
    if($schema.Fields.Item('TABLE_TYPE').Value -eq 'TABLE') { $names += [string]$schema.Fields.Item('TABLE_NAME').Value }
    $schema.MoveNext()
  }
  $tables=@()
  foreach($name in ($names | Sort-Object)) {
    $rs=New-Object -ComObject ADODB.Recordset
    $rs.Open(('SELECT * FROM ['+$name.Replace(']',']]')+']'),$conn,0,1)
    $columns=@(); $stats=@{}
    for($j=0;$j -lt $rs.Fields.Count;$j++) {
      $f=$rs.Fields.Item($j); $columns += [string]$f.Name
      $stats[$f.Name]=@{type=[int]$f.Type; missing=0; zeros=0; negative=0; minimum=$null; maximum=$null; distinct=@{}}
    }
    $count=0; $samples=@()
    while(-not $rs.EOF) {
      $row=@{}
      foreach($col in $columns) {
        $v=$rs.Fields.Item($col).Value; $s=$stats[$col]
        if($v -is [DBNull] -or $null -eq $v) { $s.missing++; $v=$null }
        else {
          $sv=[string]$v
          if($s.distinct.Count -lt 100) { $s.distinct[$sv]=$true }
          if($v -is [ValueType] -and $v -isnot [bool] -and $v -isnot [datetime]) {
            $nv=[double]$v
            if($nv -eq 0) {$s.zeros++}; if($nv -lt 0) {$s.negative++}
            if($null -eq $s.minimum -or $nv -lt $s.minimum) {$s.minimum=$nv}
            if($null -eq $s.maximum -or $nv -gt $s.maximum) {$s.maximum=$nv}
          }
        }
        $row[$col]=$v
      }
      if($count -lt 2) { $samples += $row }
      $count++; $rs.MoveNext()
    }
    foreach($col in $columns) {
      $s=$stats[$col]; $s.distinct_sample=@($s.distinct.Keys | Sort-Object); $s.Remove('distinct')
    }
    $tables += @{name=$name; rows=$count; columns=$columns; statistics=$stats; samples=$samples}
    $rs.Close()
  }
  @{provider='Microsoft.ACE.OLEDB.12.0'; mode='read only'; database_sha256=(Get-FileHash -LiteralPath $Database -Algorithm SHA256).Hash.ToLower(); tables=$tables} | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Output -Encoding UTF8
} finally { if($conn.State -ne 0) { $conn.Close() } }
