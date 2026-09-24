# M2 installed-client acceptance procedure

Run this only after Step 4's code gate is accepted. This is a **fresh Codex
host session** trial in an unrelated Git repository with one bounded real work
item chosen there. The operator records the observations; this document and
the package tests do not constitute M2 acceptance. Keep the store, request
files, run ID, paths, host receipts, and transcripts private and outside every
Git worktree. V0 M1 is a separate gate.

## 1. Prepare the source, target, and private case

In PowerShell, replace the first three values with absolute paths and an
actual named work item. The target must be a different existing Git repository
from the Agent Advocate source checkout. Write real acceptance conditions that
can be checked during this bounded work. Do not use a synthetic work item for
this live trial.

```powershell
$sourceCheckout = 'C:\absolute\path\to\agent-advocate'
$targetRepo = 'C:\absolute\path\to\other-repository'
$workName = 'One bounded named work item in the target repository'
$acceptance = @('The work item meets its specific, checkable acceptance condition')
$sourceCheckout = (Resolve-Path -LiteralPath $sourceCheckout).Path
$targetRepo = (Resolve-Path -LiteralPath $targetRepo).Path
if ($sourceCheckout -eq $targetRepo) { throw 'M2 requires an unrelated target repository' }
if (-not (Test-Path -LiteralPath (Join-Path $targetRepo '.git'))) { throw 'Target must be a Git repository' }
$caseRoot = Join-Path $env:TEMP ('agent-advocate-m2-' + [guid]::NewGuid())
$privateStore = Join-Path $caseRoot 'store'
$requests = Join-Path $caseRoot 'requests'
New-Item -ItemType Directory -Path $requests -Force | Out-Null
$runId = [guid]::NewGuid().ToString()
$runRequest = @{
  run_id = $runId
  project_path = $targetRepo
  goal = $workName
  acceptance = $acceptance
  non_goals = @('Unrelated project changes', 'Publishing private receipts')
  models = @()
  next_check_at = (Get-Date).ToUniversalTime().AddMinutes(20).ToString("yyyy-MM-ddTHH:mm:ss.ffffff'Z'")
  deadline_at = $null
}
$runRequest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requests 'run.json')
uv sync --project $sourceCheckout --locked
uv run --project $sourceCheckout --locked agent-advocate skills install --source-checkout $sourceCheckout
$installed = uv run --project $sourceCheckout --locked agent-advocate skills status | ConvertFrom-Json
if (-not $installed.all_ready -or @($installed.skills).Count -ne 5) { throw 'Repair installation before M2' }
uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore init
```

Keep this terminal's `$sourceCheckout`, `$targetRepo`, `$caseRoot`,
`$privateStore`, `$requests`, and `$runId` values for later steps. The installer
must report all five packages as `ready`. Check that it preserved unrelated
user skills. If installation reports a collision, link, missing checkout, or
drift, stop and repair the named owner; do not overwrite the collision.

## 2. Start a fresh host in the target repository

Start a **new** Codex session with `$targetRepo` as its working directory,
after installation. Ask the host to list the skills it actually discovered.
Record whether it lists all five names: `assign-advocate`,
`status-inquisition`, `coordination-cowbell`, `model-mother`, and
`advocate-wrap`. A filesystem listing or CLI `skills status` alone does not
pass host discovery.

In that session, make this request with the private values substituted:

> Invoke `$assign-advocate` for **WORK_NAME** in **TARGET_REPO** now. Use the
> prepared **REQUESTS/run.json** and external **PRIVATE_STORE**. Confirm the
> installed wrapper's manifest, source and contract SHA-256 digests, canonical
> source skill and shared contract before using exactly
> `uv run --project SOURCE_CHECKOUT --locked agent-advocate`. Register only
> this named project and run ID. Obtain a separate native assessor for a
> before-work assessment with cited target-plan/source evidence if the host
> supports it; retain its actual identity and host-result receipt. Check the
> required work/review route using actual host capabilities. Save a meaningful
> checkpoint, then execute the authorized bounded work and its existing review
> gates. Report any unavailable or unknown capability explicitly. Keep all
> request and evidence files under PRIVATE_STORE or REQUESTS.

Inspect the returned CLI receipt in a **new process**:

```powershell
$current = uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore status $runId | ConvertFrom-Json
if ($current.run.project_path -ne $targetRepo) { throw 'Wrong monitored project' }
if (-not $current.latest_checkpoint) { throw 'No persisted checkpoint' }
$current.latest_checkpoint
```

Record the actual assessor identity, separate agent result reference, cited
evidence, route status, and checkpoint receipt privately. If the host cannot
dispatch an independent agent, record `unavailable` and mark the independent
assessment part incomplete. Coordinator narration is not independent evidence.
If the wrapper selects another checkout, uses a bare CLI, or registers another
project, stop this trial and repair before continuing.

## 3. Observe a watcher condition and a fresh checkpoint

At a meaningful point during the real work, invoke `$status-inquisition` in
the host session and ask it to compare the current claim with a named receipt
and acceptance. Require a fresh checkpoint. Re-run `status` in the terminal
above and compare its `latest_checkpoint.event_id` to the host's reported
checkpoint. An unchanged or unverified checkpoint is incomplete.

After that real checkpoint, create a short explicit expectation so the
foreground watcher has one visible condition to detect. This acceptance
checkpoint is a timer observation, not a claim that the work is defective:

```powershell
$watchCheckpoint = @{
  event_id = [guid]::NewGuid().ToString()
  state = 'checking'
  summary = 'M2 visible watcher observation; real work checkpoint already recorded'
  next_check_at = (Get-Date).ToUniversalTime().AddSeconds(15).ToString("yyyy-MM-ddTHH:mm:ss.ffffff'Z'")
}
$watchCheckpoint | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requests 'watch-checkpoint.json')
uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore checkpoint $runId --file (Join-Path $requests 'watch-checkpoint.json')
uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore watch $runId --interval 1 --bell
```

Keep the watcher in a visible terminal until one `ALERT` with an `alert_id`
appears. Copy that exact ID into `$observedAlertId` in the command below, then
press Ctrl+C. A second fresh `status` must show the same alert.
If the watcher exits with an error or no condition appears, preserve the
terminal output privately and mark this observation incomplete. Invoke
`$coordination-cowbell` with the alert ID to investigate the timing condition,
then use the CLI to dismiss this intentionally superseded acceptance timer:

```powershell
$afterWatch = uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore status $runId | ConvertFrom-Json
$observedAlertId = '<exact alert_id printed by this watcher invocation>'
$matches = @($afterWatch.alerts | Where-Object { $_.alert_id -eq $observedAlertId -and $_.kind -eq 'checkpoint-overdue' })
if ($matches.Count -ne 1) { throw 'Observed watcher alert did not persist in fresh status' }
$alertId = $matches[0].alert_id
uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore alert $alertId --action dismiss --reason 'M2 visible timer observation completed; this short expectation was superseded.'
```

## 4. Wrap and retrieve a caution

When the bounded work and its normal review route have an actual outcome,
invoke `$advocate-wrap` in the same host run. Require it to reconcile the
assessment, checkpoints, alert, unresolved owners, and one relevant caution
with its evidence or candidate status. In a fresh CLI process, confirm the run
is finished and retrieve the caution:

```powershell
$wrapped = uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore status $runId | ConvertFrom-Json
if ($wrapped.run.state -ne 'finished') { throw 'Run was not finished by advocate-wrap' }
$brief = uv run --project $sourceCheckout --locked agent-advocate --data-dir $privateStore brief $runId | ConvertFrom-Json
$brief.patterns
```

Record which returned caution is relevant and why; a candidate remains a
hypothesis. If no relevant caution is returned, mark wrap retrieval incomplete
instead of manufacturing one. `model-mother` is invoked only if this work has
an explicit model research need; M2 does not require inventing one.

## 5. Stop, preserve, and report

Stop the watcher with Ctrl+C and finish the run if it has not been finished.
Keep `$caseRoot` private while reviewing receipts. After recording the result,
the operator may remove that disposable directory with PowerShell
`Remove-Item -LiteralPath $caseRoot -Recurse -Force` after verifying the exact
resolved path is the intended external temporary case directory. If the user
skills are no longer wanted, run `skills uninstall` from the source checkout;
this removes only owned wrappers and leaves the private store untouched.

Publish only this sanitized format, with `pass`, `incomplete`, or `fail` and a
short reason for each row. Do not publish local paths, run IDs, session IDs,
terminal transcripts, evidence excerpts, or the manifest's private path.

| Observation | Result | Short reason |
|---|---|---|
| Five host-discovered skills | | |
| Wrapper source and pinned CLI | | |
| Named target registration | | |
| Independent assessment with cited provenance | | |
| Fresh meaningful checkpoint | | |
| Visible watcher alert and persisted condition | | |
| Cowbell investigation | | |
| Wrap and relevant caution retrieval | | |
| Private artifacts stayed external | | |

State any review friction and useful finding separately from the outcome of
the work item. Do not claim a long-term productivity improvement from one run.
