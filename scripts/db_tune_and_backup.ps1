# Requires: Docker Desktop, running container with psql available
param(
  [string]$PG_CONTAINER = "timescaledb",
  [string]$PGUSER = "postgres",
  [string]$PGPASSWORD = "lc78080808",
  [string]$DB = "aistock",
  [string]$BACKUP_DIR = "D:\\AIstockDB\\backup",
  [switch]$SkipBackup = $true
)

Write-Host "Applying DB tuning parameters inside container: $PG_CONTAINER"

# 1) Persisted tuning parameters (ALTER SYSTEM + reload)
$TuneSql = @"
ALTER SYSTEM SET shared_buffers = '24GB';
ALTER SYSTEM SET effective_cache_size = '72GB';
ALTER SYSTEM SET work_mem = '128MB';
ALTER SYSTEM SET maintenance_work_mem = '4GB';

ALTER SYSTEM SET checkpoint_timeout = '20min';
ALTER SYSTEM SET max_wal_size = '16GB';
ALTER SYSTEM SET min_wal_size = '4GB';
ALTER SYSTEM SET checkpoint_completion_target = '0.9';
ALTER SYSTEM SET wal_compression = 'on';
ALTER SYSTEM SET synchronous_commit = 'on';

ALTER SYSTEM SET random_page_cost = '1.1';
ALTER SYSTEM SET effective_io_concurrency = '256';

SELECT pg_reload_conf();
"@

$TempFile = New-TemporaryFile
Set-Content -Path $TempFile -Value $TuneSql -Encoding UTF8

# Copy and execute inside container
$env:PGPASSWORD = $PGPASSWORD
& docker cp $TempFile "${PG_CONTAINER}:/tmp/tune.sql"
if ($LASTEXITCODE -ne 0) { throw "docker cp tune.sql failed" }
& docker exec -e PGPASSWORD=$PGPASSWORD $PG_CONTAINER bash -lc "psql -v ON_ERROR_STOP=1 -U $PGUSER -d postgres -f /tmp/tune.sql"
if ($LASTEXITCODE -ne 0) { throw "psql exec tune.sql failed" }
Remove-Item $TempFile -Force

# 2) Hot tables autovacuum tuning (apply only if table exists)
$TableSql = @"
ALTER TABLE IF EXISTS market.kline_daily_raw
  SET (autovacuum_vacuum_scale_factor=0.2,
       autovacuum_analyze_scale_factor=0.1,
       autovacuum_vacuum_cost_delay=0);

ALTER TABLE IF EXISTS market.kline_daily_qfq
  SET (autovacuum_vacuum_scale_factor=0.2,
       autovacuum_analyze_scale_factor=0.1,
       autovacuum_vacuum_cost_delay=0);

ALTER TABLE IF EXISTS market.kline_daily_hfq
  SET (autovacuum_vacuum_scale_factor=0.2,
       autovacuum_analyze_scale_factor=0.1,
       autovacuum_vacuum_cost_delay=0);
"@
$TempFile2 = New-TemporaryFile
Set-Content -Path $TempFile2 -Value $TableSql -Encoding UTF8
& docker cp $TempFile2 "${PG_CONTAINER}:/tmp/table_tune.sql"
if ($LASTEXITCODE -ne 0) { throw "docker cp table_tune.sql failed" }
& docker exec -e PGPASSWORD=$PGPASSWORD $PG_CONTAINER bash -lc "psql -v ON_ERROR_STOP=1 -U $PGUSER -d $DB -f /tmp/table_tune.sql"
if ($LASTEXITCODE -ne 0) { throw "psql exec table_tune.sql failed" }
Remove-Item $TempFile2 -Force

# 3) Recommended storage plan: keep volume; optional logical backup to D:\AIstockDB\backup
if (-not $SkipBackup) {
  Write-Host "Creating logical backup to $BACKUP_DIR"
  if (-not (Test-Path $BACKUP_DIR)) { New-Item -ItemType Directory -Path $BACKUP_DIR | Out-Null }
  $BackupFile = Join-Path $BACKUP_DIR ("all_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".sql")
  & docker exec -e PGPASSWORD=$PGPASSWORD $PG_CONTAINER bash -lc "pg_dumpall -U $PGUSER -f /tmp/all.sql"
  if ($LASTEXITCODE -ne 0) { throw "pg_dumpall failed" }
  & docker cp "${PG_CONTAINER}:/tmp/all.sql" "$BackupFile"
  if ($LASTEXITCODE -ne 0) { throw "docker cp backup failed" }
  Write-Host "Backup completed: $BackupFile"
} else {
  Write-Host "Skip backup as requested."
}

# 4) Show key parameters after reload (for verification)
$ShowSql = @"
SELECT name, setting, unit
  FROM pg_settings
 WHERE name IN (
   'shared_buffers','effective_cache_size','work_mem','maintenance_work_mem',
   'checkpoint_timeout','max_wal_size','min_wal_size','checkpoint_completion_target',
   'wal_compression','synchronous_commit','random_page_cost','effective_io_concurrency'
 )
 ORDER BY name;
"@

$TempFile3 = New-TemporaryFile
Set-Content -Path $TempFile3 -Value $ShowSql -Encoding UTF8
& docker cp $TempFile3 "${PG_CONTAINER}:/tmp/show.sql"
if ($LASTEXITCODE -ne 0) { Write-Warning "docker cp show.sql failed" } else {
  & docker exec -e PGPASSWORD=$PGPASSWORD $PG_CONTAINER bash -lc "psql -U $PGUSER -d postgres -f /tmp/show.sql"
  if ($LASTEXITCODE -ne 0) { Write-Warning "verification SHOW failed" }
}
Remove-Item $TempFile3 -Force

Write-Host "Done. Note: changing shared_buffers requires container restart to fully take effect."
