# List Azure Container App Job Executions
#
# Shows the execution history for the depot-butler scheduled job, sorted
# newest-first. Unlike the Azure Portal "Execution history" blade and
# `az containerapp job execution list` (which only read the FIRST page of
# ~20 unordered results), this script follows the API pagination via
# `nextLink` so the most recent runs are always shown.
#
# Why Invoke-RestMethod instead of `az rest`:
#   The Windows `az.cmd` wrapper mangles the `&` characters in the paginated
#   nextLink URL (skipToken/pageSize), so pagination silently loops on page 1.
#   Calling the ARM REST API directly with a bearer token avoids that.
#
# Usage:
#   ./scripts/list-job-executions.ps1            # newest 10 executions
#   ./scripts/list-job-executions.ps1 -Top 25    # newest 25 executions
#   ./scripts/list-job-executions.ps1 -All       # every execution
#   ./scripts/list-job-executions.ps1 -ShowLatestLogs
#   ./scripts/list-job-executions.ps1 -ShowLatestLogs -Tail 100 -Follow
#   ./scripts/list-job-executions.ps1 -ShowLatestLogs -ReplicaSearchDepth 3

[CmdletBinding()]
param(
    [int]$Top = 10,
    [switch]$All,
    [switch]$ShowLatestLogs,
    [switch]$Follow,
    [int]$Tail = 50,
    [int]$ReplicaSearchDepth = 1,
    [string]$ResourceGroup = "rg-FastAPI-AzureContainerApp-dev",
    [string]$JobName = "depot-butler-job"
)

$ErrorActionPreference = "Stop"

Write-Host "Fetching executions for '$JobName' in '$ResourceGroup'..." -ForegroundColor Cyan

# Acquire ARM access token and subscription id via Azure CLI
$token = az account get-access-token --query accessToken -o tsv
if (-not $token) {
    Write-Error "Could not get an access token. Run 'az login' first."
    exit 1
}
$subscriptionId = az account show --query id -o tsv

$headers = @{ Authorization = "Bearer $token" }
$uri = "https://management.azure.com/subscriptions/$subscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.App/jobs/$JobName/executions?api-version=2024-03-01"

# Page through all results using nextLink
$executions = @()
while ($uri) {
    $response = Invoke-RestMethod -Method Get -Uri $uri -Headers $headers
    $executions += $response.value
    $uri = $response.nextLink
}

Write-Host "Total executions found: $($executions.Count)" -ForegroundColor Green

$allSorted = $executions | Sort-Object { $_.properties.startTime } -Descending
$sorted = $allSorted
if (-not $All) {
    $sorted = $sorted | Select-Object -First $Top
}

$sorted |
    Select-Object `
        name,
        @{ n = 'status'; e = { $_.properties.status } },
        @{ n = 'start';  e = { $_.properties.startTime } },
        @{ n = 'end';    e = { $_.properties.endTime } } |
    Format-Table -AutoSize

if ($ShowLatestLogs) {
    $latest = $allSorted | Select-Object -First 1
    if (-not $latest) {
        Write-Warning "No executions found."
        exit 0
    }

    Write-Host "`nFetching logs for latest execution: $($latest.name)" -ForegroundColor Cyan

    $containerName = az containerapp job show `
        --name $JobName `
        --resource-group $ResourceGroup `
        --query "properties.template.containers[0].name" `
        -o tsv

    if (-not $containerName) {
        Write-Error "Could not resolve container name for job '$JobName'."
        exit 1
    }

    if ($ReplicaSearchDepth -lt 1) {
        $ReplicaSearchDepth = 1
    }

    $targetExecution = $latest
    $replicaName = ""
    $executionsToCheck = $allSorted | Select-Object -First $ReplicaSearchDepth

    foreach ($execution in $executionsToCheck) {
        $candidateReplica = az containerapp job replica list `
            --name $JobName `
            --resource-group $ResourceGroup `
            --execution $execution.name `
            --query "[0].name" `
            -o tsv 2>$null

        if ($LASTEXITCODE -ne 0) {
            continue
        }

        if ($candidateReplica) {
            $targetExecution = $execution
            $replicaName = $candidateReplica
            break
        }
    }

    if (-not $replicaName) {
        Write-Warning "No execution with an available replica was found."
        Write-Warning "Replica metadata may have expired for completed executions."
        Write-Warning "Try rerunning with -ShowLatestLogs -Follow immediately after starting a job."
        Write-Warning "You can increase search depth with -ReplicaSearchDepth 3 (or more) if needed."
        exit 0
    }

    if ($targetExecution.name -ne $latest.name) {
        Write-Warning "Latest execution replica not available; using nearest execution with replica: $($targetExecution.name)"
    }

    $logArgs = @("containerapp", "job", "logs", "show", "--name", $JobName, "--resource-group", $ResourceGroup, "--container", $containerName, "--tail", $Tail)

    $logArgs += @("--execution", $targetExecution.name, "--replica", $replicaName)

    if ($Follow) {
        $logArgs += "--follow"
    }

    & az @logArgs
}
