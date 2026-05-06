# 代码签名配置（测试环境）

## 概述

本项目使用 **electron-builder** 进行代码签名，当前配置为**测试证书**。

## 快速开始

### 1. 生成测试证书

```powershell
# 从项目根目录运行
powershell -ExecutionPolicy Bypass -File scripts/generate-test-cert.ps1
```

这会生成：

- `apps/electron/cert/finance-assistant-test.pfx` — 签名证书（含私钥）
- `apps/electron/cert/finance-assistant-test.cer` — 公钥证书

### 2. 打包（自动签名）

```bash
cd apps/electron
npm run package
```

electron-builder 会使用 `cert/finance-assistant-test.pfx` 自动签名所有可执行文件。

---

## 当前配置（package.json）

```json
"win": {
  "certificateFile": "cert/finance-assistant-test.pfx",
  "certificatePassword": "FinanceAssistant123!",
  "signDlls": true
}
```

### 配置说明

| 字段 | 说明 |
|:----:|:-----|
| `certificateFile` | PFX 证书路径（相对 `apps/electron/` 目录） |
| `certificatePassword` | 证书密码（测试用固定密码） |
| `signDlls` | 是否签名所有 DLL 插件 |

---

## 生产环境配置

### 使用正式代码签名证书

1. **购买证书**：从 DigiCert、Sectigo 等 CA 购买
2. **转换为 PFX**：
   ```powershell
   # 使用 Windows SDK 的 signtool 或 OpenSSL
   openssl pkcs12 -export -out release-cert.pfx -inkey private.key -in certificate.crt -certfile intermediate.crt
   ```
3. **修改配置**：
   ```json
   "win": {
     "certificateFile": "C:/path/to/your-release-cert.pfx"
     // 不提交密码，使用环境变量 CSC_KEY_PASSWORD
   }
   ```
4. **通过环境变量传递密码**（推荐）：
   ```bash
   # Bash / Git Bash
   export CSC_KEY_PASSWORD=your_password

   # Windows CMD
   set CSC_KEY_PASSWORD=your_password

   # PowerShell
   $env:CSC_KEY_PASSWORD = "your_password"
   ```

### 使用 Azure Key Vault / AWS KMS

electron-builder 支持云端密钥管理，需安装对应插件：
```bash
npm install -D @electron-builder/azure-key-vault
```

---

## 验证签名

打包完成后，检查签名：

```powershell
# 查看 Setup.exe 签名信息
Get-AuthenticodeSignature "release/FinanceAssistant Setup 1.0.0.exe"

# 或使用 signtool（Windows SDK）
signtool verify /pa "release/FinanceAssistant Setup 1.0.0.exe"
```

---

## 常见问题

### Q: Windows 显示"未知发布者"警告？
A: 测试证书未受 Windows 信任。可以：
1. 安装公钥证书到"受信任的发布者"：
   ```powershell
   Import-Certificate -FilePath apps\electron\cert\finance-assistant-test.cer -CertStoreLocation "Cert:\CurrentUser\TrustedPublisher"
   ```
2. 或购买正式证书

### Q: 签名失败 "The specified network password is not correct"？
A: 检查 `certificatePassword` 是否与生成 PFX 时的密码一致。

### Q: 想跳过签名（快速测试）？
A: 临时删除 `win.sign` 配置段，或设置 `asar: true` 时 electron-builder 会跳过某些签名步骤。

---

## 相关资源

- [electron-builder 签名文档](https://www.electron.build/code-signing)
- [Windows 代码签名指南](https://learn.microsoft.com/en-us/windows/win32/seccrypto/creating-a-self-signed-certificate)
- [timestamp.digicert.com](http://timestamp.digicert.com) — 免费时间戳服务
