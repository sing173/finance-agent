# HNP 打包流程（Python 后端 for HarmonyOS）

本文档描述如何将 Python 后端（含依赖包）交叉编译并打包成 HNP，供 HarmonyOS Electron 应用调用。

---

## 一、环境准备

### 1.1 WSL 环境（推荐）

在 Windows 上安装 WSL2（Ubuntu），后续操作均在 WSL 中进行。

```bash
# 检查 WSL 架构
uname -m
# 输出 x86_64 为正常，ARM 设备需另外处理
```

### 1.2 安装 WSL 依赖

```bash
sudo apt update -y
sudo apt install -y unzip autoconf automake libtool build-essential
```

### 1.3 下载 Linux 版 OHOS SDK

从华为开发者网站下载 **Command Line Tools for HarmonyOS (Linux)**：

- 地址：https://developer.harmonyos.com/cn/develop/deveco-studio#download
- 文件名示例：`command-line-tools-linux-6.1.1.280.zip`

下载后在 WSL 中解压：

```bash
mkdir -p ~/ohos-sdk-linux
unzip /mnt/d/Downloads/command-line-tools-linux.zip -d ~/ohos-sdk-linux/

# 验证 clang 可用
~/ohos-sdk-linux/command-line-tools/sdk/default/openharmony/native/llvm/bin/clang --version
# 预期输出：OHOS (dev) clang version 15.0.4 ...
```

### 1.4 设置 OHOS_SDK 环境变量

```bash
# 删除旧软链接（如有）
rm ~/ohos-sdk 2>/dev/null

# 指向 OpenHarmony SDK（不是 hms）
ln -s ~/ohos-sdk-linux/command-line-tools/sdk/default/openharmony ~/ohos-sdk

# 写入 ~/.bashrc 使其持久化
echo 'export OHOS_SDK=~/ohos-sdk' >> ~/.bashrc
source ~/.bashrc

# 验证
echo $OHOS_SDK
ls $OHOS_SDK/native/llvm/bin/clang
```

---

## 二、交叉编译 CPython（生成 python3 可执行文件）

### 2.1 克隆 python_oh 仓库

```bash
cd ~
git clone https://gitee.com/OpenHarmony_Python/python_oh.git
```

### 2.2 安装 Host Python 3.13（用于交叉编译）

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update -y
sudo apt install python3.13 python3.13-dev python3.13-venv -y
python3.13 --version
```

### 2.3 执行编译

```bash
cd ~/python_oh
bash build_python_oh.sh
```

编译完成后，产物在：
```
~/python_oh/cpython_install/
├── arm64-v8a/       ← ARM64 版本（HarmonyOS PC 用这个）
│   ├── bin/python3
│   └── lib/python3.13/
└── armeabi-v7a/     ← ARM32 版本
```

### 2.4 复制编译产物到工作目录

```bash
mkdir -p ~/finance_agent_hnp/bin
mkdir -p ~/finance_agent_hnp/lib/python3.13

# 复制 Python 解释器
cp ~/python_oh/cpython_install/arm64-v8a/bin/python3 ~/finance_agent_hnp/bin/

# 复制标准库（含 lib-dynload C 扩展）
cp -r ~/python_oh/cpython_install/arm64-v8a/lib/python3.13/lib-dynload \
   ~/finance_agent_hnp/lib/python3.13/
```

---

## 三、下载 Python 依赖包（OHOS ARM64 wheel）

### 3.1 配置 PyPI 凭证

```bash
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://cnb:<TOKEN>@cnb.cool/OpenHarmonyPCDeveloper/pypi/-/registries/simple
trusted-host = cnb.cool
EOF
```

> **注意**：`<TOKEN>` 替换为你从 `cnb.cool` 获取的有效访问令牌。

### 3.2 手动下载 wheel 文件

由于 PyPI 兼容接口路径问题，推荐直接在浏览器下载：

1. 访问 `https://cnb.cool/OpenHarmonyPCDeveloper/pypi/`
2. 搜索需要的包（如 `PyMuPDF`、`onnxruntime`）
3. 下载对应的 `cp312-cp312-ohos_aarch64.whl` 文件
4. 将文件放到 WSL 的 `~/ohos_wheels/` 目录

```bash
mkdir -p ~/ohos_wheels
cp /mnt/d/Downloads/*.whl ~/ohos_wheels/
```

### 3.3 解压 wheel 到 site-packages

```bash
mkdir -p ~/finance_agent_hnp/lib/python3.13/site-packages/

cd ~/finance_agent_hnp/lib/python3.13/site-packages/

# 解压每个 wheel
unzip -o ~/ohos_wheels/PyMuPDF-1.25.1-cp312-cp312-ohos_aarch64.whl
unzip -o ~/ohos_wheels/onnxruntime-1.26.0-cp312-cp312-ohos_aarch64.whl
unzip -o ~/ohos_wheels/opencv_python_headless-4.10.0.84-cp312-cp312-ohos_aarch64.whl
```

### 3.4 安装纯 Python 依赖

```bash
# openpyxl、nanobot 等纯 Python 包可以直接用 pip 下载源码
pip3 download openpyxl nanobot --no-binary :all: --dest ~/ohos_wheels/

# 解压
cd ~/finance_agent_hnp/lib/python3.13/site-packages/
unzip -o ~/ohos_wheels/openpyxl-*.tar.gz
# 或如果是 .whl（纯 Python 的 whl 是平台无关的）
unzip -o ~/ohos_wheels/openpyxl-*.whl
```

---

## 四、复制后端代码

```bash
cp -r /mnt/d/WorkSpace/zungen/finance-agent/apps/python/src/finance_agent_backend \
   ~/finance_agent_hnp/lib/python3.13/site-packages/
```

验证：

```bash
ls ~/finance_agent_hnp/lib/python3.13/site-packages/finance_agent_backend/
# 应看到 __init__.py, bridge.py, tools/, 等文件
```

---

## 五、创建 HNP 包

### 5.1 编写 hnp.json

```bash
cat > ~/finance_agent_hnp/hnp.json << 'EOF'
{
  "type": "hnp-config",
  "name": "finance-agent-backend",
  "version": "1.0",
  "install": {
    "links": [
      {
        "source": "bin/python3",
        "target": "python3"
      }
    ]
  }
}
EOF
```

### 5.2 确认 HNP 目录结构

```
finance_agent_hnp/
├── hnp.json
├── bin/
│   └── python3          ← ARM64 ELF 可执行文件
└── lib/
    └── python3.13/
        ├── lib-dynload/  ← 标准库 C 扩展
        └── site-packages/ ← 第三方包 + 后端代码
            ├── PyMuPDF/
            ├── onnxruntime/
            ├── openpyxl/
            ├── nanobot/
            └── finance_agent_backend/
```

### 5.3 在 Windows 上执行打包

HNP 打包工具 `hnpcli.exe` 只在 Windows 上可用，需在 Windows PowerShell 执行：

```powershell
# 先把 WSL 里的 HNP 目录复制到 Windows 文件系统
Copy-Item "\\wsl$\Ubuntu\home\zungen\finance_agent_hnp" `
  "D:\HarmonyDevelopment\finance_agent_hnp" -Recurse -Force

# 执行打包（确保输出目录存在）
New-Item -ItemType Directory -Path "D:\HarmonyDevelopment\output" -Force

& "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe" `
  pack -i "D:\HarmonyDevelopment\finance_agent_hnp" `
  -o "D:\HarmonyDevelopment\output"
```

成功后生成：`D:\HarmonyDevelopment\output\finance-agent-backend.hnp`

---

## 六、集成到 Electron 应用

### 6.1 复制 HNP 到项目

```powershell
New-Item -ItemType Directory -Path "D:\WorkSpace\zungen\finance-assistant-ohos\hnp" -Force
Copy-Item "D:\HarmonyDevelopment\output\finance-agent-backend.hnp" `
  "D:\WorkSpace\zungen\finance-assistant-ohos\hnp\"
```

### 6.2 修改 electron-builder.hmos.yml

```yaml
hmos:
  extraResources:
    - from: "hnp/"
      to: "hnp/"
```

### 6.3 修改 pythonProcessManager.js

在 `getPythonSpawnConfig()` 函数开头添加 HarmonyOS HNP 模式：

```javascript
function getPythonSpawnConfig() {
    // HarmonyOS HNP 模式
    if (process.platform === 'ohos' || process.env.OHOS_HNP_MODE === '1') {
        const hnpBasePath = process.env.OHOS_HNP_PATH || 
            '/data/app/com.zungen.financeassistant.hmos/com.zungen.financeassistant_1.0';
        const pythonPath = path.join(hnpBasePath, 'bin', 'python3');
        const scriptPath = path.join(hnpBasePath, 'lib', 'python3.13',
            'site-packages', 'finance_agent_backend', 'bridge.py');
        // ... 验证并 return
    }
    // 原有逻辑...
}
```

---

## 七、流水线化建议

### 7.1 可脚本化的步骤

| 步骤 | 是否可自动化 | 说明 |
|------|--------------|------|
| 环境准备 | ✅ | WSL + SDK 只需配置一次 |
| 编译 CPython | ✅ | `bash build_python_oh.sh` 可直接跑 |
| 下载 wheel | ⚠️ | 需要有效的 cnb.cool token |
| 复制后端代码 | ✅ | `cp` 命令 |
| 打包 HNP | ✅ | `hnpcli.exe` 命令 |
| 复制到项目 | ✅ | `Copy-Item` 命令 |

### 7.2 CI/CD 流水线建议

```yaml
# 伪代码：GitHub Actions / CNB Pipeline
steps:
  - name: 编译 CPython
    run: |
      cd ~/python_oh
      bash build_python_oh.sh

  - name: 下载依赖 wheel
    run: |
      pip download PyMuPDF onnxruntime ... --dest ~/ohos_wheels/

  - name: 打包 HNP
    # 需在 Windows agent 上执行
    run: |
      hnpcli.exe pack -i ... -o ...

  - name: 上传 HNP 到制品库
    run: |
      # 上传到 cnb.cool 制品库或内网文件服务器
```

---

## 八、常见问题

### Q: `file python3` 显示 `cannot execute binary file`
A: 正常现象。python3 是 ARM64 二进制，WSL（x86）无法运行，只能在 HarmonyOS 设备上执行。

### Q: `hnpcli pack` 报 `open zip unsuccess`
A: 输出目录不存在，`hnpcli` 不会自动创建，需手动 `mkdir -p`。

### Q: 依赖包版本冲突
A: `cnb.cool` 上的 OHOS wheel 版本较少，建议固定版本号，或在 `requirements.txt` 中注明 OHOS 兼容版本。

### Q: 后端代码更新后如何快速重新打包？
A: 只需重新执行 **步骤四**（复制后端代码）和 **步骤五**（打包 HNP），不需要重新编译 CPython。
