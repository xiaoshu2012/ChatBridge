#requires -Version 7.0
param(
    [string]$PythonPath = "python",
    [string]$OutputDir = (Join-Path $env:LOCALAPPDATA "ChatBridge\M1"),
    [switch]$QQLive
)
$ErrorActionPreference = "Stop"
$arguments = @((Join-Path $PSScriptRoot "windows.py"), "--output-dir", $OutputDir)
if ($QQLive) { $arguments += "--qq-live" }
& $PythonPath @arguments
exit $LASTEXITCODE
