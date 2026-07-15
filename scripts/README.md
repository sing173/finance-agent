## OHOS 打包准备工作

> 适用于「脱离 DevEco Studio、使用命令行 / CI 构建」的场景。用 DevEco Studio 直接 Build 的同事可跳过第 1、2 步（Studio 已自带 SDK 与 hnp 打包能力）。

### 1. 环境准备

1. 安装 **OHOS Command Line Tools**，并把 `command-line-tools\bin` 加入系统环境变量 `PATH`（使 `hvigorw` / `ohpm` 可用）。
   - Windows 上对应命令为 `hvigorw.bat` / `ohpm.bat`，打包脚本会自动识别。
2. 安装 **OpenJDK 17.0.9**（或更高 17.x）。hvigor 的签名 / 打包守护进程依赖它；若使用 JDK 8 会出现 `parseAlgParameters failed` 报错（详见 `doc/签名问题.md`）。请设置 `JAVA_HOME` 指向 JDK 17 安装目录。
3. 安装 **Node.js 22**。hvigorw 由 Node 启动，`ohpm` 也依赖 Node。

> DevEco Studio 与 Command Line Tools 共用同一套 HarmonyOS SDK。若已安装 DevEco Studio，Command Line Tools 可直接复用其 SDK；但 `bin` 仍需加入 PATH，且机器上仍要装 JDK 17 与 Node 22。

### 2. hnp 打包补丁（必须）

本项目后端以 hnp 形式打入 hap。hvigor 打包工具默认不带 `--hnp-path` 支持，需要给 Command Line Tools 打两处补丁。完整说明见 [hnp-usage.md](doc/hnp-usage.md) 的「DevEco Studio 编译」一节（文档里写的是 DevEco Studio 安装路径下的文件；由于 **IDE 与 Command Line Tools 使用同一套 SDK**，实际修改 Command Line Tools 下对应的两个文件即可）。

> 以下路径以你本机的 command-line-tools 安装目录为准（常见如 `D:\HarmonyDevelopment\command-line-tools` 或 `$HOME/DevEco/command-line-tools`）。

**补丁 1 — `packing-tool-options.js`**

文件：`command-line-tools/hvigor/hvigor-ohos-plugin/src/builder/inner-java-command-builder/packing-tool-options.js`

在 `PackingToolOptions` 类中新增方法（与其它 `addXxxPath` 并列）：

```javascript
addHnpPath(t) {
    return this.addFieldAndPath("--hnp-path", t);
}
```

**补丁 2 — `base-pack-hap-task.js`**

文件：`command-line-tools/hvigor/hvigor-ohos-plugin/src/tasks/base/base-pack-hap-task.js`

找到形如 `const X = new packing_tool_options_js_1.PackingToolOptions;` 的声明，在其后 `...addOutPath(t);` 这一行**之后**追加：

```javascript
let hnpPath = path_1.default.resolve(process.cwd(), 'hnp');
if (fse.existsSync(hnpPath)) {
    X.addHnpPath(hnpPath);
}
```

> ⚠️ **变量名随版本不同**：上面用 `X` 占位，你本机文件里该变量可能是 `a`、`s` 等（例如某版本为 `const s = new ...` 然后 `s.addOutPath(t);`）。以你本机 `new PackingToolOptions` 前面声明的变量名为准，保持一致即可。
> ✅ 若文件里已经存在 `addHnpPath` 的调用（即之前已打过补丁），此两步可跳过。

打包时，脚本会在 OHOS 工程根目录查找 `hnp/arm64-v8a/` 目录，存在则通过 `--hnp-path` 自动打入 hap。

### 3. 打包脚本（finance-agent/scripts/）

打包逻辑集中在 `finance-agent/scripts/` 下的 Bash 脚本，统一使用 Command Line Tools 的 `hvigorw`（Windows / Linux 一致），不再依赖 DevEco Studio 的 `devecocli`。

**脚本一览**

| 脚本 | 用途 |
| --- | --- |
| `common.sh` | 公共配置与辅助函数（探测 hvigorw / ohpm / hnpcli、Windows 适配、目录同步、缺失兄弟工程自动克隆）。被其它脚本 `source`，不直接执行。 |
| `update-backend.sh` | 更新后端：同步 Python 源码到 HNP `site-packages` → `hnpcli pack` 打包 `.hnp` → 复制到 OHOS 工程 `hnp/arm64-v8a/` → 同步 Electron 源码到 `web_engine`。 |
| `update-frontend.sh` | 更新前端：构建 renderer（`npm run build -w apps/renderer`）→ 同步 `dist/` 到 `web_engine` 的 renderer 资源目录。 |
| `update-ohos.sh` | 一键串联：确保兄弟工程存在（缺失则克隆）→ `update-backend.sh` → `update-frontend.sh`。 |
| `pack-ohos.sh` | **核心打包脚本**：按 flavor 执行 hvigorw 构建并收集产物到 `release/`。 |
| `build-ohos.sh` | **常用入口**：先 `update-ohos.sh` 全量更新工程，再调 `pack-ohos.sh` 打包。 |

**pack-ohos.sh 用法（flavor 区分产物与签名）**

```bash
cd finance-agent
./pack-ohos.sh prod    # 正式 app：assembleApp -p product=prod   → 仅 .app（release 签名）
./pack-ohos.sh test    # 测试 app：assembleApp -p product=default → .app + .hap（debug 签名）
./pack-ohos.sh debug   # 调试 hap：assembleHap  -p product=default → 仅 .hap（debug 签名）
# 可选第二参数 buildMode（debug|release），缺省按 flavor 自动取：prod/test=release、debug=debug
./pack-ohos.sh test debug   # 测试 app 但用 debug 构建模式
```

- `assembleApp` 是**项目级**任务（`--mode project`）；`assembleHap` 是**模块级**任务（`--mode module -p module=electron@default`），脚本已自动处理，无需手动指定。
- 产物命名：`finance-assistant-ohos-{prod,test,debug}.{app,hap}`，输出到 `release/`（CI 中覆盖为仓库内 `release/`）。

**build-ohos.sh 用法**

```bash
cd finance-agent
./build-ohos.sh          # 默认 prod（正式 app）
./build-ohos.sh test     # 测试 app（+ hap）
./build-ohos.sh debug    # 调试 hap
```

**真机安装提示**

- `pack-ohos.sh` 复制产物时已自动选取 **`*-signed.app`**（项目级 `assembleApp` 同时产出 signed / unsigned 两个 app；unsigned 外层无签名，直装会报 `9568448`）。
- 工程已设置 `packOptions.appWithSignedPkg=true`，保证 App Pack 内嵌的 HAP/HSP 也带签名，因此 **`test` / `prod` 的 `.app` 可直接 `hdc install` 本地真机**：
  - `test.app`（debug 签名）设备信任，可直接装；
  - `prod.app`（release 签名）需设备已安装对应发布证书，否则仍报 `9568448`（verify app signature failed）。
- `hdc install xxx.app` 报 `9568320 no signature file`：说明 App 内 HAP 未签名，检查 `build-profile.json5` 的 `packOptions.appWithSignedPkg` 是否为 `true`。
- 纯调试也可直接装 `.hap`（`test` / `debug` flavor 产出）：`hdc install release/finance-assistant-ohos-test.hap`。
- 各报错码与排错见 `doc/签名问题.md`。
