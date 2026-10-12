# 不拆机：Ubuntu 上已跑通参考应用编译

2026-10-12，用户授权 `ssh ubuntu`，并要求通过 GitHub 同步代码。

**已完成真实构建：固定 Actions SDK、GNU Arm 10.3.1、Python 3.13，生成 ELF/BIN/HEX。**
目标是公开参考板 `ats3089p_dev_watch_sdnand_8b` 的 `hello_world`，不是已适配 CoMi 的固件。
这一步消除了“公开 SDK 能否在现有 PC 上编译”的未知；芯片/板级引脚、原厂分区、签名和恢复入口仍未知。

## 在 Ubuntu 复现

仓库：`~/w/_hw/rcominote`，已配置 GitHub origin。初次环境需要 `git curl tar bzip2 sha256sum uv cmake ninja`。
本轮已有 CMake/Ninja/uv/just，没有修改系统软件、Docker 配置或常驻服务。

```sh
ssh ubuntu
cd ~/w/_hw/rcominote
git pull --ff-only
bash tools/setup_sdk.sh
uv run --locked tools/build_sdk.py \
  --sdk "$HOME/w/_tmp/lv_port_actions_technology" \
  --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10"
```

- `tools/setup_sdk.sh`：固定 SDK checkout、下载并校验 GNU Arm 包；SDK 放 `~/w/_tmp/lv_port_actions_technology`，工具链放 `~/.cache/rcominote/`。已有 SDK 如果提交不符或有 tracked 改动，立即失败，不覆盖。
- `tools/build_sdk.py`：PEP 723 + `build_sdk.py.lock` 固定 Python 依赖，直接 CMake 编译，显式载入本地模块，不访问 SDK 私网 west manifest。默认 4 jobs，不使用 GPU。
- 自定义输出：在上述build_sdk.py命令追加`--out artifacts/another-build --jobs 4`。
- 输出目录含 `build.log`、`build-manifest.json`、`zephyr/zephyr.{elf,bin,hex,map}` 和 `zephyr/.config`。manifest 记录工具/包版本、命令、时间、产物哈希和 SDK 工作区状态。
- 不调用 vendor maker、下载器、烧录工具；不会连接 CoMi。

## 实测环境与产物

| 项目 | 结果 |
|---|---|
| 主机 | Ubuntu，Linux x86_64；本轮仅 CPU 编译 |
| SDK | `26f51e584940d5b141cd1d09d2629d69b595f579`，Zephyr 2.7.0 vendor fork |
| 编译器 | GNU Arm Embedded 10.3-2021.10，GCC `10.3.1 20210824` |
| Python | uv CPython 3.13.15；setuptools 提供旧脚本所需 distutils |
| CMake / Ninja | 3.28.3 / 1.11.1 |
| 干净构建 | 804 步；首次约 21.0 秒；修正输出位置后的干净构建约 16.6 秒，不含首次下载/依赖安装 |
| ELF 架构 | ARM v8-M.mainline、Thumb、单精度硬浮点 ABI、DSP 扩展；仅证明参考目标编译选项 |
| 最终 BIN | 1,197,764 B；SHA-256 `b183889dd5f4204f6c5a1045a68aba34d2756ae9528be11f586555bea7d76d90` |
| 最终 HEX | 3,369,156 B；SHA-256 `9806071d2845f86ba74c7c1eae394b47e6f2c3e045cebdac3fa9b62e1ed17fd4` |
| 最终 ELF | 10,486,404 B（含 debug）；SHA-256 `7b47d00da127f002866f5fa4f0c5d21031be8882d2299de2186cefd0c5eb8d95` |
| 链接占用 | FLASH 1,197,764 B，SRAM 317,952 B，PSRAM 5,765,728 B；这是参考板链接结果，不是 CoMi 内存实测 |

两次构建的 BIN/HEX 逐字节哈希相同；ELF 含构建路径，哈希不同。没有据此声称跨机器绝对可重现。
完整日志/镜像留在 Ubuntu `artifacts/`，并复制至本 Mac 的 `artifacts/ubuntu-build-isolated/`；不把参考固件二进制放进 Git。
精简机器可读证据见 [ubuntu-build-2026-10-12.json](evidence/ubuntu-build-2026-10-12.json)。

工具链来自 [Arm 官方固定下载](https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2)，
官方 URL 重定向至 `armkeil.blob.core.windows.net`；保存的归档 SHA-256：
`97dbb4f019ad1650b732faffcc881689cedc14e2b7ee863d390e0a41ef16c9a3`。此值来自本轮下载样本，脚本用它防止后续内容漂移。

## 实际发现并处理的问题

**SDK 会写回源码目录。** freetype 的 [CMakeLists.txt 第 5 行](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/display/font/freetype/CMakeLists.txt#L5)
将 `LIBRARY_OUTPUT_PATH` 指向 `framework/display/`，首轮把受 Git 管理的 `libfreetype.a` 从 2,231,562 B 换成 2,103,358 B。
这是生成产物写回，不是手改 SDK 源码。保留该产物后只恢复本轮生成的这个文件。
现在通过 [`sdk_output.cmake`](../tools/sdk_output.cmake) 在 hello_world 的 project hook 中重定向该 target 的 archive 输出至构建目录。
第二轮验证 SDK tracked 文件零改动、BIN/HEX 不变。构建器也会在结束时检查 tracked 文件，意外改动即报错。

**构建成功仍有已知诊断：**

- 8 条参考配置依赖 warning（SPI/BT driver、standby、MPU、battery 等配置被依赖关系关闭）；保留原始 `.config` 和日志，没有加入全局忽略错误选项。
- CMake CMP0116 OLD 与 Python distutils 弃用提示。
- GCC 包中的 GDB 缺 `libncurses.so.5`，CMake 探测打印错误，但不影响 C/C++ 编译和链接。本轮未安装旧系统库，未验证 GDB/J-Link 调试可用。

## 不拆机还可继续做什么

1. 用此基线建立自己的最小应用、主机侧协议/状态机测试，验证依赖与链接；先不指定 CoMi GPIO。
2. 离线分析 ELF/map、启动镜像头和 AOTA 打包格式；完整 `.fw` 的 Python 2/x86 maker 仍是另一条未实测链路，见 [构建研究](build-feasibility.md)。
3. 沿已验证的 BLE log 握手实现限时默认日志采集；SDK 的只读命令、ACK/缓冲陷阱见 [不拆机诊断](noninvasive-diagnostics.md)。本轮只研究，未执行 shell/采集日志流。
4. 获取官方升级包或实际升级网络记录，离线识别 board/分区/签名。当前未取得 CoMi 原厂镜像。

首次刷写仍需要独立证据证明板级兼容与恢复入口；“SDK 已编译”不等于“CoMi 已能装自写固件”。
