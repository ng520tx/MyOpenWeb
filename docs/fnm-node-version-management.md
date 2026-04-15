# fnm (Fast Node Manager) 使用指南

## 什么是 fnm

fnm 是一个用 Rust 编写的 Node.js 版本管理器，速度比 nvm-windows 快很多。  
核心能力：安装多个 Node 版本，cd 到项目目录时**自动切换**到 `.nvmrc` 指定的版本。

## 当前环境

| 项目 | 值 |
|------|------|
| fnm 版本 | 1.39.0 |
| 安装方式 | winget |
| 已安装 Node | 18.18.0 (default), 22.22.2 |
| Profile 路径 | `C:\Users\ng520\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` |
| fnm 安装目录 | `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Schniz.fnm_Microsoft.Winget.Source_8wekyb3d8bbwe` |

## 自动切换原理

PowerShell Profile 中配置了：

```powershell
# 确保 fnm 在 PATH 中
$fnmDir = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Schniz.fnm_Microsoft.Winget.Source_8wekyb3d8bbwe"
if (Test-Path $fnmDir) {
    $env:Path = "$fnmDir;$env:Path"
}
# --use-on-cd: cd 到有 .nvmrc 的目录时自动切换 Node 版本
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
```

触发时机：
- **打开终端** → Profile 执行 → 检测当前目录的 `.nvmrc` → 自动切换
- **cd 到项目目录** → 检测目标目录的 `.nvmrc` → 自动切换
- **Cursor/VSCode 打开项目** → 终端工作目录就是项目根 → 自动切换

不需要手动操作，全自动。

## 常用命令速查

### 版本管理

```powershell
# 查看已安装的 Node 版本
fnm list
# 输出示例：
# * v18.18.0 default
# * v22.22.2
# * system

# 查看远程可用版本
fnm list-remote

# 安装指定版本
fnm install 20.11.0

# 安装最新 LTS
fnm install --lts

# 安装大版本（自动选最新小版本）
fnm install 22

# 卸载某个版本
fnm uninstall 20.11.0
```

### 切换版本

```powershell
# 手动切换到指定版本（当前 shell 生效）
fnm use 22

# 切换到 .nvmrc 指定的版本
fnm use

# 查看当前使用的版本
fnm current

# 设置默认版本（新终端默认使用）
fnm default 18.18.0
```

### 项目锁定

在项目根目录创建 `.nvmrc` 文件：

```
18.18.0
```

之后任何人 cd 到这个项目（前提是装了 fnm 且配了 `--use-on-cd`），都会自动切换到 18.18.0。

`.nvmrc` 支持的写法：
- `18.18.0` — 精确版本
- `18` — 大版本（匹配已安装的 18.x.x）
- `lts/*` — 最新 LTS
- `system` — 系统自带的 Node

## 与 nvm-windows 的关系

fnm 和 nvm-windows **可以共存**，但建议只用一个，避免 PATH 冲突。

| 对比 | fnm | nvm-windows |
|------|-----|-------------|
| 速度 | 极快（Rust） | 较慢 |
| 自动切换 | 原生支持 `--use-on-cd` | 需要手写脚本 |
| `.nvmrc` | 原生支持 | 需要手动 `nvm use` |
| 安装 | `winget install Schniz.fnm` | 下载安装包 |
| 跨平台 | Windows / Mac / Linux | 仅 Windows |

如果之前用 nvm-windows 安装过 Node，fnm 会独立管理自己的版本，不会冲突。  
但如果 PATH 里同时有两者管理的 node，可能会混乱。建议逐步迁移到 fnm。

## 镜像加速

如果从 nodejs.org 下载慢，可以设置国内镜像：

```powershell
# 临时使用
fnm install 20 --node-dist-mirror https://npmmirror.com/mirrors/node

# 永久设置（环境变量）
[Environment]::SetEnvironmentVariable("FNM_NODE_DIST_MIRROR", "https://npmmirror.com/mirrors/node", "User")
```

设置后重启终端生效，之后所有 `fnm install` 都会走镜像。

## 故障排查

### 问题：终端启动报 "fnm 无法识别"

原因：fnm 不在 PATH 中。  
解决：确认 Profile 里有 PATH 补充逻辑（见上方 Profile 配置）。

### 问题：cd 到项目目录没有自动切换

检查项：
1. 项目根目录有 `.nvmrc` 文件吗？
2. Profile 里有 `--use-on-cd` 参数吗？
3. `.nvmrc` 里写的版本装了吗？（`fnm list` 查看）

如果版本没装，fnm 会提示：

```
Can't find an installed Node version matching v20.11.0.
Do you want to install it? answer [y/N]:
```

### 问题：想看 fnm 到底做了什么

```powershell
# 查看 fnm 设置的环境变量
fnm env --shell powershell

# 输出类似：
# $env:FNM_MULTISHELL_PATH = "C:\Users\xxx\AppData\Local\fnm_multishells\xxxx"
# $env:FNM_VERSION_FILE_STRATEGY = "local"
# $env:FNM_DIR = "C:\Users\xxx\AppData\Roaming\fnm"
# $env:FNM_LOGLEVEL = "info"
# $env:FNM_NODE_DIST_MIRROR = "https://nodejs.org/dist"
# $env:FNM_ARCH = "x64"
```

### 问题：想在某个目录下运行特定 Node 版本的命令，但不想切换

```powershell
fnm exec --using=22 node --version
fnm exec --using=22 npm install
```

## 完整重装步骤（备忘）

如果需要在新机器上重新配置：

```powershell
# 1. 安装 fnm
winget install Schniz.fnm

# 2. 创建 PowerShell Profile（如果不存在）
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Path $PROFILE -Force
}

# 3. 写入 Profile 配置
Add-Content $PROFILE @'

# fnm - Node 版本自动切换
$fnmDir = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Schniz.fnm_Microsoft.Winget.Source_8wekyb3d8bbwe"
if (Test-Path $fnmDir) {
    $env:Path = "$fnmDir;$env:Path"
}
fnm env --use-on-cd --shell powershell | Out-String | Invoke-Expression
'@

# 4. 重启终端，然后安装需要的 Node 版本
fnm install 18.18.0
fnm install 22
fnm default 18.18.0

# 5. 验证
fnm list
node --version
```
