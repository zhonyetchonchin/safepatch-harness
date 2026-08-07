param(
    [string]$Python = ".\.venv\Scripts\python.exe"
)

& $Python -m pytest
exit $LASTEXITCODE
