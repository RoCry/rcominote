# 固定 SDK 的主机构建可行性

2026-10-12。源码固定于 `lvgl/lv_port_actions_technology` 的
`26f51e584940d5b141cd1d09d2629d69b595f579`。本轮只读源码、枚举主机工具与文件格式；
未安装依赖、未编译、未运行 vendor 二进制、未接触硬件。所有构建命令均为**未执行候选配方**。
设备/启动链边界见 [Actions SDK 研究](actions-sdk.md)。

**可以准备 Linux 上的应用编译实验；完整打包另受 Python 2.7 与 x86 工具约束。**
公开树包含运行库、参考板启动镜像和打包程序，但不包含 C/C++ 编译器本体。
构建 EVK 示例只能验证 SDK，不能证明 CoMi 可启动此镜像。

## 本轮新增的确定信息

| 项目 | 固定树事实 | 实际影响 |
|---|---|---|
| CMake | `hello_world/CMakeLists.txt` 写 3.13.1，但内层 `cmake/app/boilerplate.cmake:29` 实际要求 **3.20.0** | 以 3.20 为下限；不能仅照应用首行装旧版本 [入口][app] [内层][boilerplate] |
| Python 3 | `cmake/python.cmake` 最低 3.6；requirements 无上界 | 新 Python/依赖是否兼容尚未验证；成功后必须锁版本 [Python][python] [依赖][requirements] |
| Python 2 | Linux `.fw` 生成硬编码 `python2 -O .../maker/PyMaker.pyo`；本机 `file` 判为 Python 2.7 bytecode | Python 3 环境无法替代；应用编译可先绕开这一层 [maker 调用][maker] |
| 平台分派 | 非 Windows 打包器按 Python 32/64 位选 `linux-x86`/`linux-x86_64`，没有 Darwin/ARM 分支 | macOS arm64 或 Linux arm64 均不会自动获得适配工具 [SDFS][sdfs] [maker][maker] |
| 模块来源 | `west.yml` 指向 `192.168.4.4` 的 Gerrit，目录内容已随公开仓库提交 | 不运行 `west update`；使用本地现有模块显式列表 [manifest][manifest] [模块装配][modules] |
| CLI 参数陷阱 | `build.py` 声明 `-a/-b`，但后续没有读取 `args.application/args.boards`；首次仍读菜单/写 `.build_config` | 不能用这两个参数实现无人值守选目标 [CLI][cli] |
| 编译/打包分界 | `build.py` 先 `west build`，后无条件 `build_firmware`；`-p` 是只打包 | 先直调应用 CMake，获得 ELF/BIN，排除老打包器干扰 [构建调度][dispatch] |

## 主机与工具盘点

本机实测：`Darwin arm64`；`uv 0.12.4`、CMake `4.4.4`、Ninja `1.13.2`、west `1.5.0`；
`dtc`、Docker CLI、7z 存在。仅检查 CLI 路径，未确认 Docker daemon/可用 Linux 环境。
本次 PATH 未找到 `arm-none-eabi-gcc`、`arm-zephyr-eabi-gcc`、`python2`、`JLinkExe`。
PATH 结果不能排除其他目录已有安装。

固定仓库的 `git ls-files` 未发现 GCC/Clang/Arm Compiler 可执行文件；
有 `cmake/toolchain/{zephyr,gnuarmemb,armclang}` 集成、`tools/ar.exe`、`tools/ninja2mdk.exe`，
它们不构成完整编译器。GCC 仍需外装：

- 推荐开发入口要求 Zephyr SDK；本树检测下限 0.11.1，不给唯一已验证版本。
  0.11.1/0.11.2 走树内兼容脚本，较新版本加载 SDK 自己的 CMake 文件。[SDK 检测][sdk]
- 可选 `gnuarmemb`：提供 `GNUARMEMB_TOOLCHAIN_PATH`，其中需有 `bin/arm-none-eabi-*`
  与 Newlib sysroot；树内不是一个无需外部 GCC 的实现。[GNU Arm][gnuarm]
- `build.py -k` 仅在 Windows 生成/打开 Keil 项目，非 Windows 明确报错；不等于附送 Keil。[Keil][gcc]

本机 `file` 实测：

| 固定树相对路径，均在 `action_technology_sdk/zephyr/tools/utils/` | 格式 |
|---|---|
| `linux-x86_64/make_sdfs` | x86-64 Linux ELF，静态链接 |
| `linux-x86_64/maker/CompoundFW` | x86-64 Linux ELF，动态链接；解释器 `/lib64/ld-linux-x86-64.so.2` |
| `linux-x86_64/fw2x/fw2x` | 同上，x86-64 glibc loader |
| `linux-x86/make_sdfs` | i386 Linux ELF，静态链接 |
| `linux-x86_64/maker/PyMaker.pyo` | Python 2.7 bytecode |

因此完整打包实验优先 Linux x86_64 + glibc；Apple Silicon 上需 x86_64 Linux 虚拟机或仿真容器。
这只是格式推导，未验证仿真兼容性、共享库依赖、Python 2 模块依赖。
单独安装 macOS Arm GCC 仍不能执行这些 Linux ELF。
Python 2 仅作为旧 vendor 打包工具的隔离运行时，应用编译保持独立 Python 3 环境。

## 最小现实构建路线：先编译公开 hello_world

`hello_world` 是带 LVGL、显示/输入/存储、字体和 Actions framework 的应用模板，
不是仅输出串口的最小 Zephyr 程序。它启用 VG Lite、Newlib、资源管理和大显示内存池；
作为公开 README 实际描述的基线，比凭空删配置更可复现。[应用配置][prj] [板覆盖][board-conf] [源码][main]

第一阶段只需 Linux x86_64、Git、Bash、uv、外装的 Zephyr SDK ARM 工具链。
以下命令**未执行**；版本窗口 `cmake>=3.20,<4` 是减少旧策略兼容变量的实验选择，
Python 3.13 也尚未验证；它们均不是已经确认的 vendor 最佳版本。
先在全新 checkout 操作，并把工具链安装路径设置为实际值。

```bash
set -euo pipefail
task_src="$HOME/w/_tmp/lv_port_actions_technology"
task_sdk="$task_src/action_technology_sdk"
test "$(git -C "$task_src" rev-parse HEAD)" = \
  26f51e584940d5b141cd1d09d2629d69b595f579

# 先通过 SDK 安装程序取得 ARM toolchain；这里不假设任何已安装目录。
: "${ZEPHYR_SDK_INSTALL_DIR:?set to installed Zephyr SDK directory}"
export ZEPHYR_SDK_INSTALL_DIR
export ZEPHYR_TOOLCHAIN_VARIANT=zephyr

uv venv --python 3.13 "$task_sdk/.venv"
uv pip install --python "$task_sdk/.venv/bin/python" \
  -r "$task_sdk/zephyr/scripts/requirements-base.txt" \
  'cmake>=3.20,<4' ninja
source "$task_sdk/.venv/bin/activate"
cd "$task_sdk/zephyr"
source ./zephyr-env.sh

# 显式载入公开树内已有模块；不解析私网 manifest、不执行 west update。
task_modules=()
while IFS= read -r task_module_file; do
  task_modules+=("${task_module_file%/zephyr/module.yml}")
done < <(rg --files "$task_sdk/framework" "$task_sdk/thirdparty" \
  | sort | sed -n '\|/zephyr/module.yml$|p')
test "${#task_modules[@]}" -gt 0
task_module_list=$(IFS=';'; printf '%s' "${task_modules[*]}")
task_out="$task_src/hello_world/outdir/ats3089p_dev_watch_sdnand_8b"

cmake -S "$task_src/hello_world" -B "$task_out" -G Ninja \
  -DBOARD=ats3089p_dev_watch_sdnand_8b \
  -DZEPHYR_MODULES="$task_module_list"
cmake --build "$task_out"
```

此路线直接编译仓库根的应用，不需要复制/软链到 `application/app_demo`。
`find_package(Zephyr ... ZEPHYR_BASE)` 与 `ZEPHYR_MODULES` 都是固定树已实现入口；
列表包含 framework 与 thirdparty 中现有 `module.yml`，补足脱离 west workspace 后不会自动发现的模块。
例如 display 模块定义其 CMake/Kconfig 入口，CMSIS 模块定义 CMake 入口。[应用][app] [模块解析][modules] [display module][display-module] [CMSIS module][cmsis-module]

验收目标：`zephyr/zephyr.elf`、`zephyr.bin`、`zephyr.hex`、`.config`、map/构建日志、
工具与 Python 依赖精确版本。**目前这些产物没有生成。**
README 提醒现代 GCC warnings-as-errors；应用 `prj.conf` 已有多项 warning suppression。
首轮遇到错误应记录完整日志并定位 API/编译器差异，不能以“最低版本满足”推定一定链接成功。[上游说明][readme] [现有抑制][prj]

## 完整打包与缺失物

编译通过后才复现 vendor `build.py` 流程；下面仍是**未执行**的第二阶段：

```bash
# Linux x86_64；Python 3 venv 保持激活；需另行提供 python2.7 的 python2 命令。
cd "$task_sdk/application/app_demo"
ln -s "$task_src/hello_world" hello_world
cd "$task_sdk/zephyr"
uv run --no-project --active build.py -n
# 菜单按名称选 ats3089p_dev_watch_sdnand_8b → app_demo → hello_world。
```

此流程会修改 SDK checkout 的 `.build_config`、输出目录。无需运行任何下载命令。
目标 `hello_world/outdir/ats3089p_dev_watch_sdnand_8b/_firmware/`；
`*.fw` 与 `_firmware/bin/app.bin` 不可和未后处理的 `zephyr.bin` 混用。
build.py 还拼装 NVRAM、SDFS、配置、boot image、checksum 后调用完整 maker。[打包流程][pack] [maker][maker]

| 所需内容 | 本树情况 / 后续获取 |
|---|---|
| EVK boot/ADFU/recovery blob | `boards/arm/ats3089p_dev_watch_sdnand_8b/` 有 `mbrec.bin`、`adfus.bin`、`adfus_u.bin`、`recovery.bin`、`bootloader.ini`、`nand_id.bin`；公共 `tools/prebuilt/leopard/` 有附加文件 [板目录][board] [prebuilt][prebuilt] |
| 链接用库 | 有 `libboot.a`、`libsocatp.a`；显示路径有 `libdisplay.a`、`libdisplay_gui.a`、`libvg_lite.a`、`libfreetype.a`、`libdrv_display_engine.a`，按条件导入；不承诺这些 blob 对任意 GCC 都 ABI 兼容 [SoC][soc] [显示][display] [GPU][gpu] [驱动][display-engine] |
| Linux maker 环境 | Python 2.7 + `PyMaker.pyo` 及其 `.so`/`CompoundFW`；动态库是否齐备需 Linux 主机查 ELF dependencies，再离线试打包；本轮未查 `ldd`、未装 Python 2 |
| 初次 SoC 配置/下载 | README 明确需 Windows config tool，仓库附 `tools/config_tool.rar`；不能由 Linux 上存在 maker 推翻该上游限制 [说明][readme] |
| 自写录音 codec | 树中确有 `adMUSIC.dsp`、`aeOPUS.dsp`；未跟踪 `aeRECORD.dsp`。MP3/Opus 某些硬件编码配置明确查找后者，不能把“有部分 DSP blob”视为编码链完整 [codec][codec] |
| CoMi 专属支持 | 实际板配置、原厂分区/镜像、校准与身份数据、签名策略、恢复入口均待取证；EVK 文件不补足这些项目 |

CoMi 自定义 app 的最小交付材料：匹配芯片的 vendor toolchain/运行库；
确认的 RAM/存储和引脚表；匹配板级配置、镜像头/链接地址、分区与资源配置；
可保留原厂启动链的应用装载方式；如启用强制验签，还需合法可用的签名/开发启动方式。
Linux 编译实验能先消除工具链未知，不能消除设备端未知。

## 授权与可复制范围

公开可下载不等于全树同一授权。这里只记录文件中的声明，不对不明 blob 推定授权：

- Zephyr `LICENSE` 是 Apache-2.0；`hello_world/src/main.c`、多数构建脚本也标 Apache-2.0。
  LVGL `LICENCE.txt` 为 MIT；Vivante driver 目录有许可文本和保留通知要求。[Zephyr license][license] [应用][main] [LVGL][lvgl-license] [Vivante][vivante-license]
- `zephyr/framework/CMakeLists.txt` 和 `framework/arithmetic/CMakeLists.txt` 等标
  `LicenseRef-BSD-5-Clause-Actions`。本轮许可文件清单未找到该引用的完整条款，
  不能只凭名称解释可再分发范围。[Actions 标记][actions-license]
- CMake 的 Apache SPDX 声明不能自动证明相邻 `.a/.bin/.dsp/.pyo` 的许可。
  本轮未发现覆盖全部 vendor blobs 的统一授权文件；对外发布前需取得具体适用条款。
  本仓库保存来源索引与调查结果，暂不复制 SDK 二进制。

## 固定源码索引

[readme]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/README.md
[app]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/CMakeLists.txt
[prj]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/prj.conf
[main]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/src/main.c
[board-conf]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/hello_world/boards/ats3089p_dev_watch_sdnand_8b.conf
[boilerplate]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/app/boilerplate.cmake#L20-L29
[python]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/python.cmake
[requirements]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/scripts/requirements-base.txt
[sdk]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/toolchain/zephyr/host-tools.cmake
[gnuarm]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/toolchain/gnuarmemb/generic.cmake
[gcc]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L623-L665
[cli]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L738-L818
[dispatch]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L820-L877
[pack]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L430-L610
[maker]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L890-L918
[sdfs]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_sdfs.py#L46-L57
[manifest]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/west.yml
[modules]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/cmake/zephyr_module.cmake
[display-module]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/display/zephyr/module.yml
[cmsis-module]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/hal/cmsis/zephyr/module.yml
[board]: https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/boards/arm/ats3089p_dev_watch_sdnand_8b
[prebuilt]: https://github.com/lvgl/lv_port_actions_technology/tree/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/prebuilt/leopard
[soc]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/soc/arm/actions/leopard/CMakeLists.txt
[display]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/display/CMakeLists.txt
[gpu]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/display/vg_lite/CMakeLists.txt
[display-engine]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/display/engine/CMakeLists.txt
[codec]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/media/codec_config.c#L270-L302
[license]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/LICENSE
[lvgl-license]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/thirdparty/lib/gui/lvgl/LICENCE.txt
[vivante-license]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/drivers/gpu/verisilicon/LICENSE.txt
[actions-license]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/framework/CMakeLists.txt#L1-L5
