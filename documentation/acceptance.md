# M1 live acceptance procedure

Run this procedure only in a **fresh Codex session** with this repository as the
working directory. It observes host capability; it is not a source-authoring,
profile-changing, or monitored-project-changing task. Keep the generated runtime
directory private and external to every Git worktree. Do not mark M1 or v0
accepted from this document alone.

## 1. Prepare a private, disposable acceptance case

Open PowerShell in this repository. The following block writes every example
request file used below before any skill is invoked. It uses this checkout as
the read-only monitored project and creates only an external private store and
request directory; it does not modify the monitored project.

```powershell
$acceptanceRoot = Join-Path $env:TEMP ("agent-advocate-m1-" + [guid]::NewGuid())
$privateStore = Join-Path $acceptanceRoot "private-store"
$projectPath = (Resolve-Path ".").Path
$requestPath = Join-Path $acceptanceRoot "requests"
New-Item -ItemType Directory -Force $requestPath | Out-Null
$syntheticAdapterPath = Join-Path $acceptanceRoot "deliberately-missing-review-adapter"

function UtcAfter([int] $seconds) {
  return (Get-Date).ToUniversalTime().AddSeconds($seconds).ToString("yyyy-MM-ddTHH:mm:ss.ffffff'Z'")
}

$syntheticProbeAt = UtcAfter 0
if (Test-Path -LiteralPath $syntheticAdapterPath) { throw "Synthetic missing-adapter fixture unexpectedly exists" }

$runRequest = @{
  project_path = $projectPath
  goal = "Read-only assessment of Agent Advocate Step 3 against plan.md"
  acceptance = @(
    "An independent assessment cites Step 3 source and plan evidence",
    "The selected build-step --reviewers deep route has a measured readiness result",
    "A fresh checkpoint and one real watchdog alert are observed"
  )
  non_goals = @("Changing the monitored project", "Publishing private evidence", "Launching a daemon")
  models = @(@{
    role = "advocate"; requested_model = "gpt-6-astra"
    observed_model = $null; effort = $null; host = "codex"
  })
  next_check_at = UtcAfter 3600
  deadline_at = $null
}
$runRequest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "run.json")

$normalCheckpoint = @{
  event_id = [guid]::NewGuid().ToString()
  state = "checking"
  summary = "M1 normal two-interval observation is in progress"
  next_check_at = UtcAfter 190
}
$normalCheckpoint | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "normal-checkpoint.json")

$shortOverdueCheckpoint = @{
  event_id = [guid]::NewGuid().ToString()
  state = "active"
  summary = "M1 short configured overdue demonstration"
  next_check_at = UtcAfter 15
}
$shortOverdueCheckpoint | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "short-overdue-checkpoint.json")

$unsupportedAdapterObservation = @{
  observation_id = [guid]::NewGuid().ToString()
  statement = "Synthetic required-review adapter is unavailable: its deliberately absent executable resource failed Test-Path; owner: adapter maintainer."
  basis = "measured"
  evidence = @(@{
    kind = "host-result"; locator = $syntheticAdapterPath
    captured_at = $syntheticProbeAt; excerpt = "Test-Path -LiteralPath returned False"; sha256 = $null
  })
  pattern_key = "required-review-unavailable"
  recommendation = "Repair or select an explicitly authorized working review route; do not dispatch this synthetic route."
  analysis_kind = "coordinator"; assessor_id = $null; supersedes = $null
}
$unsupportedAdapterObservation | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "unsupported-adapter-observation.json")

$modelCaution = @(@{
  pattern_key = "m1-exact-model-research"
  summary = "GPT-6 Astra: broad legacy skill scaffolding can lead to unnecessary testing"
  trigger = "When writing skills or prompts for requested gpt-6-astra work"
  scope = @{ roles = @(); models = @("gpt-6-astra"); hosts = @("codex"); tags = @() }
  basis = "official-guidance"
  sources = @(@{
    kind = "public-url"; locator = "https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra"
    captured_at = UtcAfter 0; excerpt = $null; sha256 = $null
  })
  owner = "coordinator"
  action = "Use concise task-specific instructions and check the current official guidance before reusing old scaffolding."
  disposition = "candidate"
  review_after = $null
  reason = "Prepared candidate only; import after live research confirms the claim and refreshes captured_at."
})
ConvertTo-Json -InputObject $modelCaution -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "model-caution.json")

uv sync --locked
uv run --locked agent-advocate --data-dir $privateStore init
$started = uv run --locked agent-advocate --data-dir $privateStore start --file (Join-Path $requestPath "run.json") | ConvertFrom-Json
$runId = $started.run_id
$runId
```

The model-caution request is fully authored for the exact model
`gpt-6-astra` and an official direct source. The run requests that model for
the advocate role but leaves observed identity unknown. `brief` can therefore
retrieve a caution scoped to the request without claiming the host used it.
Do not import the prepared candidate if live web capability is unavailable or
the source does not support its specific claim during M1.

## 2. Observe the five packages in the fresh host

First, ask the fresh Codex session to list the project-local packages it
actually discovered. Record whether all five names are visible:
`assign-advocate`, `status-inquisition`, `coordination-cowbell`,
`model-mother`, and `advocate-wrap`. A file on disk alone is not a pass.

Then make these explicit requests, naming `$runId` and the private paths only
inside the session. Preserve detailed receipts in `$privateStore`, not in a
public report.

1. Invoke `$assign-advocate` for the named Step 3 read-only assessment in
   `plan.md`. Supply the run goal/acceptance and require a fresh independent
   assessment of the watchdog source against Step 3. Check the real selected
   `build-step --reviewers deep` route through its loaded `review-deep` adapter,
   required helper resources, and current host capabilities. Report available,
   unavailable, or unknown with reason/evidence/owner. Do not dispatch a build,
   call an API fallback, or claim an independent assessment from coordinator
   narration.
2. In a separate request, invoke `$assign-advocate` with the clearly synthetic
   unsupported adapter at `$syntheticAdapterPath`. Have the fresh session run
   `Test-Path -LiteralPath $syntheticAdapterPath` and cite that observation,
   separate from the real route. Require an **unavailable** result and the
   owning repair, and explicitly forbid attempting that adapter's build. If
   the skill did not persist its observation, use the prepared request only
   after the fresh session repeats the missing-path check:

   ```powershell
   uv run --locked agent-advocate --data-dir $privateStore observe $runId --file (Join-Path $requestPath "unsupported-adapter-observation.json")
   ```

3. Persist a normal checkpoint, then invoke `$status-inquisition` to compare
   the claim with the fresh CLI receipt:

   ```powershell
   $normalCheckpoint.event_id = [guid]::NewGuid().ToString()
   $normalCheckpoint.next_check_at = UtcAfter 180
   $normalCheckpoint | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "normal-checkpoint.json")
   uv run --locked agent-advocate --data-dir $privateStore checkpoint $runId --file (Join-Path $requestPath "normal-checkpoint.json")
   uv run --locked agent-advocate --data-dir $privateStore status $runId
   ```

   Open a new CLI invocation (not cached shell output) and confirm it reads the
   same run ID and latest checkpoint.
4. Invoke `$model-mother` for the exact named model `gpt-6-astra`. Require a
   current direct official public source, its date/scope/uncertainty, and a
   persisted scoped caution. If the skill did not persist an equivalent record
   itself, import the prepared candidate only after the live source supports
   its specific claim. Refresh its capture time to the actual live check:

   ```powershell
   $modelCaution[0].sources[0].captured_at = UtcAfter 0
   $modelCaution[0].reason = "M1 live source checked; preserve exact model identity and source date."
   ConvertTo-Json -InputObject $modelCaution -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "model-caution.json")
   uv run --locked agent-advocate --data-dir $privateStore patterns import --file (Join-Path $requestPath "model-caution.json")
   ```

   Missing web capability is an explicit incomplete M1 result, not permission
   to fabricate current research.

## 3. Observe the real foreground watch terminal

Run this normal watcher in a terminal you can see. Keep it open through two
full default 60-second poll intervals (about 125 seconds total), then press
Ctrl+C. It should not create an alert because the normal checkpoint remains in
the future. Ctrl+C must leave `$runId` and its records intact.

```powershell
$normalCheckpoint.event_id = [guid]::NewGuid().ToString()
$normalCheckpoint.next_check_at = UtcAfter 190
$normalCheckpoint | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "normal-checkpoint.json")
uv run --locked agent-advocate --data-dir $privateStore checkpoint $runId --file (Join-Path $requestPath "normal-checkpoint.json")
uv run --locked agent-advocate --data-dir $privateStore watch $runId --bell
uv run --locked agent-advocate --data-dir $privateStore status $runId
```

For the short configured overdue observation, rewrite the short request just
before use so its short expectation is genuinely future, then run the
watcher in a visible terminal until it prints one `ALERT` line and its
`alert_id`:

```powershell
$shortOverdueCheckpoint.event_id = [guid]::NewGuid().ToString()
$shortOverdueCheckpoint.next_check_at = UtcAfter 15
$shortOverdueCheckpoint | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $requestPath "short-overdue-checkpoint.json")
uv run --locked agent-advocate --data-dir $privateStore checkpoint $runId --file (Join-Path $requestPath "short-overdue-checkpoint.json")
uv run --locked agent-advocate --data-dir $privateStore watch $runId --interval 1 --bell
```

After the alert prints, press Ctrl+C and retrieve it in a fresh process:

```powershell
$current = uv run --locked agent-advocate --data-dir $privateStore status $runId | ConvertFrom-Json
$alertId = $current.alerts[0].alert_id
$alertId
```

Invoke `$coordination-cowbell` with that alert ID. It must investigate the
overdue visibility condition rather than asserting defective work. Persist its
separate evidence/recommendation, then acknowledge, snooze, or dismiss the
alert only with an explicit reason. For example, a deliberately false/superseded
test condition may be dismissed:

```powershell
uv run --locked agent-advocate --data-dir $privateStore alert $alertId --action dismiss --reason "M1 short demonstration completed; the expectation was intentionally superseded."
```

Finally invoke `$advocate-wrap` with the actual outcome of the bounded review.
It should finish the run. Confirm that finish in a new process, then retrieve
the relevant caution through `brief`; an unfinished run is incomplete M1:

```powershell
$wrapped = uv run --locked agent-advocate --data-dir $privateStore status $runId | ConvertFrom-Json
if ($wrapped.run.state -ne "finished") { throw "advocate-wrap did not finish the run" }
uv run --locked agent-advocate --data-dir $privateStore brief $runId
```

## 4. Record the result safely

Record separate sanitized outcomes for package discovery, independent-assessment
provenance, unsupported-route handling, checkpoint persistence, exact-model
research, two normal watch intervals, one short overdue alert, cowbell
disposition, wrap retrieval, and privacy. State missing agent/web capability or
unobserved execution as incomplete. Do not publish local paths, run IDs,
private evidence excerpts, or terminal transcripts. Distinguish demonstrated
mechanisms from any unproven long-term productivity benefit.
