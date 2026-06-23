# 鸿蒙 PC 适配调研与开发指南

> 日期: 2026-06-22 | 基于 OpenHarmony SIG Electron 官方文档及社区实践

---

## 1. 背景

Finance Assistant 采用 Electron + Python 三进程架构（Renderer → Electron Main → Python Backend via stdio JSON-RPC）。本文评估该项目迁移到鸿蒙 PC 平台的可行性，并详细描述基于交叉编译的开发环境搭建与完整开发流程。

**开发模式（三机协作）**：

| 机器 | 角色 | 职责 |
|------|------|------|
| **Windows** | 主开发机 | DevEco Studio、日常编码、前端调试、HAP 打包签名、hdc 连接鸿蒙 PC |
| **Linux** | 交叉编译机 | OHOS NDK 工具链、编译 C/C++ 依赖和 Python wheel |
| **鸿蒙 PC** | 目标设备 | 安装 HAP 即可运行（Python + 依赖已内置），真机测试 |

---

## 2. 核心结论

| 维度 | 结论 | 风险等级 |
|------|------|---------|
| Node.js 运行时 | 鸿蒙 Electron 包含定制 Node.js 运行时，核心模块可用 | 低 |
| child_process.spawn() | 官方文档明确支持 spawn/exec/execfile/fork | 低 |
| Python 解释器 | Linux 交叉编译 ohos_aarch64 版本，打包进 HAP | 低 |
| PyMuPDF | 社区已编译 ohos_aarch64 wheel (v1.25.1) | 低 |
| opencv-python | 社区已编译 ohos_aarch64 wheel (v4.12.0.88) | 低 |
| onnxruntime | 社区已编译 ohos_aarch64 wheel (v1.26.0) | 低 |
| HAP 打包分发 | 可行，Python 解释器和所有依赖打包进 HAP，客户装完即用 | 中 |

**总体评估：项目迁移到鸿蒙 PC 技术上可行，核心依赖已有社区预编译包，主要工作在开发环境搭建和打包分发层面。**

---

## 3. 开发环境搭建

### 3.1 整体架构

```
┌───────────────────────────┐    ┌───────────────────────────┐    ┌──────────────────────────┐
│  Windows 主开发机           │    │  Linux 交叉编译机           │    │  鸿蒙 PC (ARM64)          │
│                             │    │                             │    │                            │
│  - VS Code / IDE 编码       │    │  - OHOS NDK 工具链         │    │  - Python 3.12 运行时     │
│  - npm run dev 前端调试     │    │  - C/C++ 交叉编译          │    │  - ohos_aarch64 wheel     │
│  - DevEco Studio 打包签名   │ scp│  - Python wheel 交叉编译   │ hdc│  - 运行 Electron 应用     │
│  - hdc 连接鸿蒙 PC          │───▶│  - 产物传回 Windows        │───▶│  - 真机调试               │
│                             │    │                             │    │                            │
└───────────────────────────┘    └───────────────────────────┘    └──────────────────────────┘
```

### 3.2 Windows 主开发机环境

Windows 是日常开发的主机器，与现有开发流程一致：

**基础环境**（与当前相同）：
- Node.js + npm（Electron 前端开发）
- Python 3.12 + venv（Python 后端开发）
- VS Code 或其他 IDE

**鸿蒙适配新增**：
- **DevEco Studio**：华为官方 IDE，用于 HAP 打包、签名、设备管理
  - 下载地址：华为开发者联盟官网（支持 Windows）
  - 安装后内置 **hdc** 工具（鸿蒙设备通信，类似 adb）
  - 安装后内置 **hnpcli**（HNP 包打包工具）
  - 安装后内置 **binary-sign-tool**（二进制签名工具）

**日常工作流**：
```
1. 在 Windows 上 npm run dev 正常开发调试 Electron + Python 代码
2. 如需编译鸿蒙版 wheel → 在 Linux 上交叉编译 → scp 传回 Windows
3. 通过 DevEco Studio 打包 HAP
4. 通过 hdc 将 HAP 安装到鸿蒙 PC 真机测试
```

### 3.3 Linux 交叉编译机：安装 OHOS SDK

OHOS SDK 是鸿蒙 PC 交叉编译的核心工具链，包含 LLVM/Clang 编译器、sysroot 头文件和系统库。

```bash
# 创建工作目录
mkdir -p ~/ohos-dev && cd ~/ohos-dev

# 下载 OHOS SDK（以 Linux 为例，Mac 替换为 mac 路径）
# SDK 通常随 DevEco Studio 安装，也可从 OpenHarmony 源码仓获取
# 路径示例：从 DevEco Studio 安装后提取
# Linux: /opt/deveco-studio/sdk/HarmonyOS-NEXT/openharmony/native
# Mac:   ~/Library/Huawei/Sdk/openharmony/native

# 如果从源码仓获取 prebuilts：
# git clone https://gitee.com/openharmony/prebuilts_ohos_sdk.git
```

SDK 关键目录结构：

```
ohos-sdk/
└── linux/                      # 或 mac/
    └── native/
        ├── llvm/               # LLVM/Clang 工具链
        │   └── bin/
        │       ├── clang
        │       ├── clang++
        │       ├── lld
        │       ├── llvm-ar
        │       ├── llvm-strip
        │       └── ...
        ├── sysroot/            # 鸿蒙系统头文件和库
        │   └── usr/
        │       ├── include/    # musl libc 头文件
        │       └── lib/aarch64-linux-ohos/
        └── build-tools/       # 构建工具
```

### 3.4 Linux 交叉编译机：配置环境变量

创建环境配置文件 `~/ohos-dev/ohos-env.sh`：

```bash
#!/bin/bash
# OHOS SDK 交叉编译环境

export OHOS_SDK_HOME="$HOME/ohos-sdk/linux"    # Mac 用户改为 mac
export OHOS_NDK="$OHOS_SDK_HOME/native"
export OHOS_SYSROOT="$OHOS_NDK/sysroot"

# C/C++ 编译器
export CC="$OHOS_NDK/llvm/bin/clang --target=aarch64-linux-ohos"
export CXX="$OHOS_NDK/llvm/bin/clang++ --target=aarch64-linux-ohos"

# 链接器和工具
export LD="$OHOS_NDK/llvm/bin/lld"
export AR="$OHOS_NDK/llvm/bin/llvm-ar"
export RANLIB="$OHOS_NDK/llvm/bin/llvm-ranlib"
export STRIP="$OHOS_NDK/llvm/bin/llvm-strip"

# 编译标志
export CFLAGS="--sysroot=$OHOS_SYSROOT -fPIC"
export CXXFLAGS="--sysroot=$OHOS_SYSROOT -fPIC"
export LDFLAGS="--sysroot=$OHOS_SYSROOT"

# 将工具链加入 PATH
export PATH="$OHOS_NDK/llvm/bin:$PATH"

echo "OHOS NDK 环境已加载: $OHOS_NDK"
```

使用时：

```bash
source ~/ohos-dev/ohos-env.sh
```

### 3.5 Linux 交叉编译机：验证工具链

```bash
# 验证 clang 可用
$CC --version
# 应输出: clang version ... Target: aarch64-linux-ohos

# 编译一个简单的 C 测试程序
echo 'int main() { return 0; }' > /tmp/test.c
$CC /tmp/test.c -o /tmp/test_ohos
file /tmp/test_ohos
# 应输出: ELF 64-bit LSB executable, ARM aarch64
```

### 3.6 Windows：连接鸿蒙 PC 真机

DevEco Studio 安装后，在 Windows 上使用内置的 hdc 工具连接鸿蒙 PC：

```bash
# 确认设备连接
hdc list targets

# 文件传输
hdc file send ./local-file /data/local/tmp/
hdc file recv /data/local/tmp/remote-file ./

# 远程 shell
hdc shell

# 安装 HAP
hdc install your-app.hap
```

### 3.7 DevEco Studio 工程目录结构

DevEco Studio 工程的职责是：**Electron 源码编译 + 集成前端构建产物和 Python 可执行文件 → 打包 HAP**。前端和 Python 的源码不在 DevEco Studio 工程中编译，只接收构建产物。

| 模块 | DevEco Studio 中的形式 | 来源 |
|------|----------------------|------|
| **Electron 主进程** | TypeScript 源码（需适配鸿蒙 API） | 保留在工程中，工程内编译 |
| **Renderer 前端** | Vite 构建产物（.js/.css/.html） | Windows 编译后同步进工程 |
| **Python 后端** | PyInstaller 打包的独立可执行文件（含解释器 + 业务代码 + 所有依赖） | Linux 交叉编译后同步进工程 |

#### 当前项目结构（Windows 开发态）

```
finance-agent/
├── apps/
│   ├── electron/                         ← Electron 主进程（源码）
│   │   ├── src/
│   │   │   ├── main.ts
│   │   │   ├── preload.ts
│   │   │   ├── ipc.ts
│   │   │   └── pythonProcessManager.ts
│   │   ├── dist/                         ← tsc 编译产物
│   │   └── package.json
│   ├── renderer/                         ← React 前端（源码）
│   │   ├── src/
│   │   └── dist/                         ← Vite 构建产物 ★ 同步到 DevEco
│   └── python/                           ← Python 后端（源码）
│       └── src/finance_agent_backend/
│           ├── bridge.py
│           ├── parser_router.py
│           ├── subject_matcher.py
│           ├── voucher_composer.py
│           ├── services/
│           └── config/
├── shared/                               ← 共享类型定义
├── docs/
└── release/                              ← electron-builder 输出 (Windows)
```

#### 鸿蒙 Electron DevEco Studio 工程结构

> **关键设计**：编译与分发职责分离。
> - **PyInstaller**（Linux 交叉编译机上）：将 Python 解释器 + 业务代码 + 所有三方依赖打包为一个 ohos_aarch64 独立可执行文件 `bridge`（项目已有 `bridge.spec`）
> - **HNP**（hnpcli 工具）：仅是分发容器，将已编译好的 `bridge` 可执行文件 + 元数据打包为 `.hnp` 文件，嵌入 HAP 分发
> - HNP **不负责编译**，它等价于一个带元数据的归档格式
>
> DevEco Studio 工程中不出现任何 .py 源码。

```
chromium-electron-release/                ← Electron 鸿蒙版源码根目录
└── src/
    └── ohos/
        └── ohos_hap/                     ← DevEco Studio 打开此目录
            ├── electron/                 ← Electron native 层
            │   └── libs/
            │       └── arm64-v8a/
            │           ├── libelectron.so
            │           └── *.so
            │
            ├── hnp/
            │   └── arm64-v8a/
            │       └── python-runtime.hnp    ← Python 后端（Linux PyInstaller + hnpcli 打包）
            │
            └── web_engine/               ← 应用层
                └── src/
                    └── main/
                        ├── module.json5          ← HAP 配置（声明 hnpPackages）
                        │
                        ├── ets/                  ← Electron TS 源码 ★ 工程内编译
                        │   ├── main.ts
                        │   ├── preload.ts
                        │   ├── ipc.ts
                        │   ├── pythonProcessManager.ts
                        │   └── tsconfig.json
                        │
                        └── resources/
                            └── resfile/
                                └── resources/
                                    └── app/              ← 运行时资源目录
                                        │
                                        ├── package.json
                                        ├── node_modules/
                                        │
                                        │  ← Windows 构建产物（同步）：
                                        └── renderer/             ← apps/renderer/dist/
                                            ├── index.html
                                            ├── assets/
                                            │   ├── *.js
                                            │   └── *.css
                                            └── ...
```

#### 构建同步脚本（Windows + Linux → DevEco Studio 工程）

```powershell
# build-ohos.ps1 — 在 Windows 上构建前端，同步所有产物到 DevEco Studio 工程
# python-runtime.hnp 需要先在 Linux 上编译好，再 scp 到 Windows

$OHOS_PROJECT = "C:\chromium-electron-release\src\ohos\ohos_hap"
$OHOS_APP = "$OHOS_PROJECT\web_engine\src\main\resources\resfile\resources\app"

# 1. 编译前端（Windows）
cd apps\renderer
npm run build

# 2. 同步前端构建产物
Copy-Item -Recurse dist\* "$OHOS_APP\renderer\" -Force

# 3. 同步 python-runtime.hnp（Linux 打包后 scp 到 Windows）
Copy-Item C:\ohos-build\python-runtime.hnp "$OHOS_PROJECT\hnp\arm64-v8a\" -Force

# 4. 同步 package.json
Copy-Item ..\electron\package.json "$OHOS_APP\" -Force

Write-Host "同步完成。在 DevEco Studio 中编译 Electron TS + 打包 HAP"
```

```bash
# build-hnp.sh — 在 Linux 交叉编译机上执行（完整流程）
source ~/ohos-dev/ohos-env.sh

# 1. PyInstaller 打包 bridge 可执行文件
cd /path/to/finance-agent/apps/python
pyinstaller bridge.spec --onefile --clean

# 2. 组装 HNP 源目录
mkdir -p python-runtime/bin
cp dist/bridge python-runtime/bin/

# 3. 创建 hnp.json
cat > python-runtime/hnp.json << 'EOF'
{
  "type": "hnp-config",
  "name": "python-runtime",
  "version": "0.3.1",
  "description": "Finance Assistant Python backend",
  "install": {
    "links": [{ "source": "bin/bridge", "target": "bin/bridge" }]
  }
}
EOF

# 4. 打包为 .hnp
hnpcli pack -i python-runtime/ -o python-runtime.hnp

# 5. scp 传回 Windows
scp python-runtime.hnp user@windows-machine:C:/ohos-build/
```

---

## 4. 各层可行性分析

### 4.1 Node.js 运行时

鸿蒙 Electron（OpenHarmony SIG 适配版）包含完整的 Node.js 运行时，支持：

- 核心模块：`path`、`fs`、`events`、`stream`、`crypto`、`net`、`url`、`buffer`、`child_process` 等
- Electron API：`BrowserWindow`、`ipcMain`/`ipcRenderer`、`contextBridge`、`Tray` 等
- Native Addon：需使用 OHOS NDK 交叉编译（N-API 接口可用）

**对本项目的影响**：Electron 主进程代码（`main.ts`、`pythonProcessManager.ts`、`preload.ts`）无需修改即可运行。

> 参考：[OpenHarmony SIG Electron](https://gitcode.com/openharmony-sig/electron)

### 4.2 child_process.spawn()

官方仓库 `docs/child-process/` 提供了 `spawn`、`exec`、`execfile`、`fork` 四个 API 的完整文档和端到端示例，文档中明确标注支持 OHOS 系统：

```javascript
// Unix-like、OHOS系统
const ls = spawn('ls', ['-lh', '/usr']);
```

**对本项目的影响**：`pythonProcessManager.ts` 中的 `spawn(pythonCmd, [scriptPath], { stdio: ['pipe', 'pipe', 'pipe'] })` 方案在鸿蒙 Electron 上直接可用。

> 参考：[child-process 文档](https://gitcode.com/openharmony-sig/electron/tree/master/docs/child-process)

### 4.3 Python 解释器

> **注意**：生产分发时，Python 解释器由 Linux 交叉编译后打包进 HAP，客户无需手动安装。以下内容仅用于开发阶段在鸿蒙 PC 上快速验证。

社区提供两种方式在鸿蒙 PC 上安装 Python 3.12（仅开发调试用）：

**方式一：命令行安装脚本（推荐）**

```bash
curl -fsSL https://gitcode.com/OpenHarmonyPCDeveloper/cmd-pkgs/releases/download/pkgs/install.sh \
  | sh -s -- python 3.12.9
```

**方式二：Harmonybrew 包管理器**

```bash
zsh -c "$(curl -fsSL https://harmonybrew.atomgit.com/install.sh)"
brew install python
```

安装后通过 `python3 -m ensurepip` 启用 pip。

### 4.4 Python 依赖库

#### 社区预编译 wheel

社区项目 [Python_Package_For_HarmonyOS](https://gitcode.com/OpenHarmonyPCDeveloper/Python_Package_For_HarmonyOS) 已编译并上传了大量 Python 包到社区 PyPI 镜像。本项目所需的三个 C 扩展库均已就绪：

| 库 | 版本 | Wheel 平台标签 |
|---|------|---------------|
| PyMuPDF | 1.25.1 | `cp312-cp312-ohos_aarch64` |
| opencv-python | 4.12.0.88 | `cp312-cp312-ohos_aarch64` |
| onnxruntime | 1.26.0 | `cp312-cp312-ohos_aarch64` |

#### 在鸿蒙 PC 上直接安装（仅开发验证用）

> **生产分发**：wheel 在 Linux 上通过 `pip download --platform ohos_aarch64` 下载，解压后打包进 HAP，客户无需安装。

```bash
# 配置社区 PyPI 源
pip3 config set global.index-url https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/simple
pip3 config set global.trusted-host pypi.cnb.cool

# 安装（自动拉取 ohos_aarch64 预编译 wheel）
pip3 install PyMuPDF opencv-python onnxruntime
```

#### 纯 Python 库 vs C 扩展库

| 类别 | 说明 | 安装方式 |
|------|------|---------|
| 纯 Python 库（`py3-none-any`） | 无需移植，直接安装 | `pip install` 从官方 PyPI 或社区源 |
| C/C++ 扩展库 | 必须为 ohos_aarch64 重新编译 | 社区预编译 wheel 或自行交叉编译 |
| Rust 扩展库 | 需 Rust 交叉编译工具链 | `maturin build --target aarch64-unknown-linux-ohos` |

### 4.5 在 Linux 上自行交叉编译 Python Wheel（备选方案）

当社区镜像没有所需版本或需要定制时，在 Linux 交叉编译机上编译：

```bash
# 确保已加载 OHOS NDK 环境
source ~/ohos-dev/ohos-env.sh

# 克隆目标包源码
git clone https://github.com/pymupdf/PyMuPDF.git
cd PyMuPDF

# 交叉编译 wheel（--no-build-isolation 保留环境变量）
pip wheel . --no-build-isolation -w dist/

# 验证产物
ls dist/*.whl
# 应输出: PyMuPDF-x.x.x-cp312-cp312-linux_aarch64.whl

# 如需修改 wheel 平台标签为 ohos_aarch64
# wheel tags --platform-tag ohos_aarch64 dist/*.whl
```

#### 常见问题处理

| 问题 | 原因 | 解法 |
|------|------|------|
| `Undefined symbol: OPENSSL_sk_set_thunks` | 系统 OpenSSL 版本差异 | 在源码中注入兼容定义或静态链接 OpenSSL |
| `dlopen` 签名校验失败 | 鸿蒙要求 .so 签名 | 使用 `binary-sign-tool` 签名 |
| Wheel 平台标签不匹配 | 编译器输出 linux_aarch64 | 使用 `wheel tags` 修改为 `ohos_aarch64` |
| 运行时找不到 .so | rpath 未设置 | 编译时加 `-Wl,-rpath,$ORIGIN` 或设置 `LD_LIBRARY_PATH` |

#### Rust 扩展交叉编译

```bash
# 添加鸿蒙 Rust target
rustup target add aarch64-unknown-linux-ohos

# 配置 ~/.cargo/config.toml
cat >> ~/.cargo/config.toml << 'EOF'
[target.aarch64-unknown-linux-ohos]
linker = "/home/user/ohos-sdk/linux/native/llvm/bin/clang"
rustflags = [
  "-C", "link-arg=--target=aarch64-linux-ohos",
  "-C", "link-arg=--sysroot=/home/user/ohos-sdk/linux/native/sysroot"
]
EOF

# 使用 maturin 编译 PyO3 扩展
maturin build --target aarch64-unknown-linux-ohos --release -o dist/
```

### 4.6 Node.js Native Addon

如需在 Electron 中使用 Node.js native addon（如 `node-sqlite3`），同样使用 OHOS NDK 交叉编译：

```bash
source ~/ohos-dev/ohos-env.sh

cd node-sqlite3
npm install --verbose --build-from-source \
  --runtime=electron --target=18.18.2 \
  --dist-url=https://electronjs.org/headers

# 产物在 build/Release/node_sqlite3.node
# 拷贝到 HAP 的 libs/arm64-v8a/ 目录
```

> 参考：[Native Addon 加载指南](https://gitcode.com/openharmony-sig/electron/tree/master/docs/electron-loading-addon-guide)

---

## 5. C/C++ 三方库迁移方案

当 Python 包依赖的底层 C/C++ 库需要移植时，社区提供四种方案：

| 方案 | 工具 | 已适配库数 | 适用场景 |
|------|------|-----------|---------|
| **手动交叉编译** | OHOS NDK + CMake/Make | - | 简单项目，完全控制 |
| **Lycium++** | lycium_plusplus 框架 | 200+ | 标准 C/C++ 库，鸿蒙原生构建流 |
| **ohos_vcpkg** | vcpkg fork | 1000+ | 大型 C/C++ 生态，自动依赖解析 |
| **build_in_harmonyos** | AI 辅助迁移 | - | 自动化编译，需鸿蒙设备联网 |

### 本项目相关 C/C++ 底层库状态

| 底层库 | 被谁依赖 | ohos_vcpkg 状态 |
|--------|---------|----------------|
| freetype | PyMuPDF (MuPDF) | 已适配 |
| harfbuzz | PyMuPDF (MuPDF) | 已适配 |
| zlib | PyMuPDF, OpenCV | 系统内置（sysroot） |
| flatbuffers | onnxruntime | 已适配 |
| protobuf | onnxruntime | 未找到（可能需要额外适配） |
| OpenCV core | opencv-python | 未找到（社区已有 Python wheel，底层已内含） |

> 由于 PyMuPDF / opencv-python / onnxruntime 的 Python wheel 已由社区预编译完成，通常不需要单独处理底层 C/C++ 库。仅当需要自定义编译选项或社区版本不满足需求时才走交叉编译。

> 参考：[三方库鸿蒙化迁移工具汇总](https://atomgit.com/OpenHarmonyPCDeveloper/docs/blob/main/aggregate/%E3%80%90%E4%B8%89%E6%96%B9%E5%BA%93%E9%B8%BF%E8%92%99%E5%8C%96%E8%BF%81%E7%A7%BB%E5%B7%A5%E5%85%B7%E3%80%91%E6%B1%87%E6%80%BB.md)

---

## 6. 完整开发流程

### 6.1 日常开发阶段（Windows）

```
1. 在 Windows 上正常开发 Electron + Python 代码
2. npm run dev 本地调试（使用本地 Python venv）
3. 代码逻辑与现有 Windows/Mac 版本一致，无需修改
```

### 6.2 鸿蒙适配阶段（Windows + Linux + 鸿蒙 PC）

**核心原则：鸿蒙 PC 是客户机器，不能有任何手动安装步骤。Python 后端通过 PyInstaller 编译为独立可执行文件，再通过 HNP 嵌入 HAP，客户装完即用。**

```
【Linux 交叉编译机】
1. 搭建 OHOS NDK 交叉编译环境（见第 3.3 ~ 3.5 节）
2. PyInstaller 交叉编译 bridge 可执行文件（ohos_aarch64）
   pyinstaller bridge.spec --onefile --clean
   （产物含 Python 解释器 + 业务代码 + 所有三方依赖，一个文件搞定）
3. hnpcli 打包为 python-runtime.hnp
4. 将 python-runtime.hnp 通过 scp 传回 Windows

【Windows 主开发机】
5. 接收 python-runtime.hnp，放入 DevEco Studio 工程的 hnp/arm64-v8a/ 目录
6. 在 module.json5 中声明 hnpPackages
7. 通过 DevEco Studio 打包 HAP（HNP 自动嵌入）
8. 通过 hdc 将 HAP 安装到鸿蒙 PC 测试

【鸿蒙 PC 目标设备（客户机器）】
9. 安装 HAP，无需任何额外操作
10. 验证 Electron 前端启动正常
11. 验证 Electron spawn HNP 中的 bridge 可执行文件 + JSON-RPC 通信正常
12. 验证核心业务功能（PDF 解析、OCR、凭证生成等）
```

### 6.3 打包分发阶段

详见第 7 章。

---

## 7. HAP 打包方案

采用 **HNP 嵌入**方式：Linux 上用 PyInstaller 编译 Python 后端为独立可执行文件 → `hnpcli` 打包为 HNP → 嵌入 HAP 分发。客户安装 HAP 即用，无需任何额外操作。

### 7.1 HNP 概述

HNP（HarmonyOS Native Package）是鸿蒙 PC 的原生二进制分发格式。它**不是编译工具**，而是一个带元数据的归档容器——将已编译好的可执行文件打包为 `.hnp`，嵌入 HAP 进行分发。

| HNP 类型 | 安装路径 | 共享范围 |
|---------|---------|---------|
| **Public** | `/data/service/hnp/` | 所有应用共享（`HNP_PUBLIC_HOME` 环境变量） |
| **Private** | `/data/app/<app>/` | 仅宿主 HAP 可访问 |

本项目使用 **Private HNP**：Python 后端仅供本应用使用，嵌入 HAP 内，安装时自动部署。

### 7.2 HAP 包结构

```
your-app.hap
├── libs/arm64-v8a/
│   └── libelectron.so
├── hnp/arm64-v8a/
│   └── python-runtime.hnp          ← 内含 bridge 可执行文件
├── rawfile/
│   └── app/
│       ├── package.json, node_modules/
│       └── renderer/                 ← 前端构建产物（无 Python 任何文件）
└── module.json5                    ← 声明 hnpPackages
```

### 7.3 HNP 包内部结构

```
python-runtime/                     ← HNP 源目录（在 Linux 上组装）
├── bin/
│   └── bridge                      ← PyInstaller 独立可执行文件
│                                     （含 Python 解释器 + 业务代码 + 所有依赖）
└── hnp.json
```

`hnp.json`：

```json
{
  "type": "hnp-config",
  "name": "python-runtime",
  "version": "0.3.1",
  "description": "Finance Assistant Python backend",
  "install": {
    "links": [{ "source": "bin/bridge", "target": "bin/bridge" }]
  }
}
```

### 7.4 完整打包流程

```bash
# 【Linux 交叉编译机】

# 1. PyInstaller 打包 bridge 可执行文件
source ~/ohos-dev/ohos-env.sh
cd /path/to/finance-agent/apps/python
pyinstaller bridge.spec --onefile --clean

# 2. 组装 HNP 源目录
mkdir -p python-runtime/bin
cp dist/bridge python-runtime/bin/

# 3. 创建 hnp.json（见 7.3 格式）

# 4. 打包为 .hnp
hnpcli pack -i python-runtime/ -o python-runtime.hnp

# 5. scp 传回 Windows
scp python-runtime.hnp user@windows-machine:C:/ohos-build/
```

```powershell
# 【Windows 主开发机】

# 6. 拷贝 .hnp 到 DevEco Studio 工程
Copy-Item C:\ohos-build\python-runtime.hnp "$OHOS_PROJECT\hnp\arm64-v8a\" -Force

# 7. 在 module.json5 中声明 hnpPackages（见 7.5）

# 8. 在 DevEco Studio 中打包 HAP（.hnp 自动嵌入）

# 9. 签名 HAP

# 10. 通过 hdc install 安装到鸿蒙 PC 测试
```

### 7.5 module.json5 配置

```json5
{
  "module": {
    // ...
    "hnpPackages": [
      {
        "package": "hnp/arm64-v8a/python-runtime.hnp",
        "type": "private"
      }
    ]
  }
}
```

### 7.6 pythonProcessManager.ts 适配

Private HNP 安装后，bridge 可执行文件位于应用沙箱的标准路径：

```typescript
function getPythonSpawnConfig(): { cmd: string; args: string[]; cwd: string } {
  if (isElectronPackaged()) {
    // Private HNP 安装路径
    const hnpHome = process.env.HNP_PRIVATE_HOME
      || `/data/app/${app.getName()}`;

    const bridgeExe = path.join(hnpHome, 'bin', 'bridge');

    return {
      cmd: bridgeExe,
      args: [],
      cwd: path.join(hnpHome, 'bin'),
    };
  }

  // 开发模式：保持不变（使用本地 venv + python bridge.py）
  // ...existing code...
}
```

---

## 8. 待验证事项

| 序号 | 事项 | 在哪台机器 | 优先级 | 预估工作量 |
|------|------|-----------|--------|-----------|
| 1 | Windows 安装 DevEco Studio，配置 hdc 连接鸿蒙 PC | Windows | P0 | 0.5 天 |
| 2 | Linux 搭建 OHOS NDK 交叉编译环境并验证工具链 | Linux | P0 | 1 天 |
| 3 | Linux PyInstaller 交叉编译 bridge 可执行文件（ohos_aarch64） | Linux | P0 | 1 天 |
| 4 | Linux hnpcli 打包 python-runtime.hnp | Linux | P0 | 0.5 天 |
| 5 | Windows 打包 HAP（含 HNP）并安装到鸿蒙 PC | Windows → 鸿蒙 PC | P0 | 2 天 |
| 6 | 验证 spawn bridge + stdio JSON-RPC 通信正常 | 鸿蒙 PC | P0 | 0.5 天 |
| 7 | 验证 bridge 内 import 正常（PyMuPDF / cv2 / onnxruntime） | 鸿蒙 PC | P0 | 0.5 天 |
| 8 | 端到端业务验证（PDF 解析、OCR、凭证生成） | 鸿蒙 PC | P1 | 1 天 |
| 9 | PyMuPDF `fitz.open("pdf", bytes)` 处理中文路径 | 鸿蒙 PC | P1 | 0.5 天 |
| 10 | bridge 可执行文件签名 | Linux / Windows | P2 | 0.5 天 |
| 11 | 应用市场提审流程 | Windows | P2 | 视情况 |

---

## 9. 参考资料

| 资源 | 链接 |
|------|------|
| OpenHarmony SIG Electron | https://gitcode.com/openharmony-sig/electron |
| child_process 文档 | https://gitcode.com/openharmony-sig/electron/tree/master/docs/child-process |
| Native Addon 加载指南 | https://gitcode.com/openharmony-sig/electron/tree/master/docs/electron-loading-addon-guide |
| Python_Package_For_HarmonyOS | https://gitcode.com/OpenHarmonyPCDeveloper/Python_Package_For_HarmonyOS |
| 社区 PyPI 镜像 | https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/simple |
| ohos_vcpkg (C/C++ 库) | https://gitcode.com/OpenHarmonyPCDeveloper/ohos_vcpkg |
| lycium_plusplus (C/C++ 库) | https://gitcode.com/OpenHarmonyPCDeveloper/ohos_vcpkg/tree/feature/mac |
| Harmonybrew | https://harmonybrew.atomgit.com/ |
| 三方库迁移工具汇总 | https://atomgit.com/OpenHarmonyPCDeveloper/docs/blob/main/aggregate/ |
| Python 三方库移植全景指南 | https://blog.csdn.net/qq8864/article/details/161572678 |
| OHOS Rust 交叉编译指南 | https://blog.csdn.net/qq8864/article/details/161624297 |
| 鸿蒙 Electron 打包部署指南 | https://blog.csdn.net/TrisighT0/article/details/161001996 |
| HNP 开发指南 | https://openharmonycrossplatform.csdn.net/691696d882fbe0098cab6ff0.html |
| HNP 公有包与私有包设计 | https://blog.csdn.net/weixin_29197835/article/details/157748461 |
| Lycium + FFmpeg HNP 打包实战 | https://blog.csdn.net/weixin_47308626/article/details/156418112 |
| Lycium 框架环境配置 | https://blog.csdn.net/zl392321162/article/details/160993980 |
| 四种移植方案对比 | https://blog.csdn.net/chenlycly/article/details/161392511 |
