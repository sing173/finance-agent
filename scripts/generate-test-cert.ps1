# Generate test code signing certificate (valid for 1 year)
# Run: powershell -ExecutionPolicy Bypass -File scripts/generate-test-cert.ps1

# Certificates stored at: apps/electron/cert/
$certPath = Join-Path $PSScriptRoot "..\apps\electron\cert"
$certPath = [System.IO.Path]::GetFullPath($certPath)
$pfxFile = Join-Path $certPath "finance-assistant-test.pfx"
$cerFile = Join-Path $certPath "finance-assistant-test.cer"

# Create cert directory
if (!(Test-Path $certPath)) {
    New-Item -ItemType Directory -Path $certPath -Force | Out-Null
    Write-Host "Created directory: $certPath" -ForegroundColor Green
}

# Remove old certs
Remove-Item $pfxFile -ErrorAction SilentlyContinue
Remove-Item $cerFile -ErrorAction SilentlyContinue

# Generate self-signed code signing certificate
# EKU OID 1.3.6.1.5.5.7.3.3 = Code Signing
$cert = New-SelfSignedCertificate `
    -Subject "CN=FinanceAssistant Test,O=FinanceAssistant Dev,C=CN" `
    -KeyUsage DigitalSignature `
    -TextExtension "2.5.29.37={text}1.3.6.1.5.5.7.3.3" `
    -FriendlyName "FinanceAssistant Test Certificate" `
    -NotAfter (Get-Date).AddYears(1) `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeySpec Signature `
    -HashAlgorithm SHA256

Write-Host "Certificate created: $($cert.Subject)" -ForegroundColor Green

# Export to PFX (with private key)
$password = ConvertTo-SecureString -String "FinanceAssistant123!" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $pfxFile -Password $password
Write-Host "PFX exported: $pfxFile" -ForegroundColor Green

# Export to CER (public key, for trust installation)
Export-Certificate -Cert $cert -FilePath $cerFile
Write-Host "CER exported: $cerFile" -ForegroundColor Green

# Optional: install to Trusted Publisher (requires admin)
# Import-Certificate -FilePath $cerFile -CertStoreLocation "Cert:\CurrentUser\TrustedPublisher"

Write-Host "`n=== DONE ===" -ForegroundColor Cyan
Write-Host "PFX: $pfxFile"
Write-Host "Password: FinanceAssistant123!"
Write-Host ""
Write-Host "NOTE: This is a test certificate. Windows will show 'Unknown Publisher'." -ForegroundColor Yellow
Write-Host "To trust it (admin PowerShell required):"
Write-Host "  Import-Certificate -FilePath `"$cerFile`" -CertStoreLocation Cert:\CurrentUser\TrustedPublisher"
