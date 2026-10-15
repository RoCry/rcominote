# 路线图

2026-10-15 定稿。唯一的执行计划；历史“下一步”见 `docs/archive/`，不作为计划。

目标顺序：完整备份 → 可恢复 → RAM 跑自写代码 → 自写固件从 NOR 启动。学习为主，不做完整替代固件。

## 决定

- 拆手上这台机器。砖了再买一台继续。
- 备份走物理路线（SPI 夹子 / SWD），BLE 逐页导出停止。
- 写 NOR 之前必须有通过 `tools/verify_full_dump.py` 的双读一致 dump。
- USB/ADFU 路线搁置，拆机后看磁吸触点走线再定。
- 不再搜 ATS3085L M4 BSP；没有就裸机写。

## 里程碑

| # | 目标 | 完成标准 | 状态 |
|---|---|---|---|
| M1 | 全片备份 | 两次独立读取 4 MiB，`verify_full_dump.py` 全部 known slice 匹配且两份一致 | 等拆机，[issue #1](https://github.com/RoCry/rcominote/issues/1) |
| M2 | 可恢复 | SWD 只读 attach 读到 CPUID `410fc241`；或夹子回写同一镜像后设备正常开机、BLE `info` 一致 | 待 M1 |
| M3 | RAM 跑自写代码 | SWD 把最小程序载入 SRAM 执行，UART 打印或 OLED 出图 | 待 M2 |
| M4 | 自写固件进 NOR | boot 分区换成自建镜像，上电从它启动并点屏；随时能用 M1 镜像恢复 | 待 M3 |

M4 范围：时钟、GPIO、UART、72×40 OLED。之后再决定做简单录音机（SD + 麦克风）还是给原厂固件打补丁去 App 绑定。

## 拆机前准备（离线，现在可做）

- [x] `tools/verify_full_dump.py`：dump 对照 9 个已知 raw 切片 + 分区 FF 比例表。
- [ ] 工具型号确认：编程器（CH341A 需 3.3 V 版或改装）、调试器（J-Link / DAPLink）、USB-TTL。接在 Ubuntu 还是 Mac。
- [ ] 查 ZB25VQ32 datasheet：封装、读指令 0x03/0x0B、最高频率；确认 flashrom 支持该 ID（`flashrom -L | grep -i zb25`）。
- [ ] 从 system 映射镜像里把 UART0 TX/RX、I2C OLED 的 GPIO 号和 MMIO 基址整理成一张表，供 M3 用（已有：GPIO28 CTRL `0x40068074`=UART0，MEM slot0 `0x40010300`，参考结构体 `firmware/reference/lark_registers.h`）。

## 拆机当天清单（用户动手，agent 跟进）

1. 关机。拆外壳，先拍整板两面高清照（含 SoC、NOR、磁吸触点附近走线、任何测试点）。
2. **断电池**再夹 NOR。NOR 是 SOIC-8 或 USON-8；USON 没有引脚可夹，需飞线到测试点或拆芯片。
3. 读两次：

   ```sh
   flashrom -p ch341a_spi -r dump-a.bin
   flashrom -p ch341a_spi -r dump-b.bin
   uv run tools/verify_full_dump.py dump-a.bin dump-b.bin
   ```

   夹子读不稳时降速或拔掉夹子重新夹；不要试任何写命令。
4. 找 SWD：Cortex-M4 需要 SWDIO/SWCLK/GND（可选 nRST）。通常是 PCB 上 3–5 个裸焊盘。拍照后用 OpenOCD 只读 attach：

   ```sh
   openocd -f interface/jlink.cfg -c "transport select swd" -c "adapter speed 1000" \
     -f target/cortex_m.cfg -c "init" -c "mdw 0xE000ED00" -c "shutdown"
   ```

   读到 `410fc241` 即 M2 的 SWD 分支完成。若读保护或无焊盘，M2 改走夹子回写验证。
5. 看磁吸触点到板上的走线数：只有两根（VBUS/GND）则 USB 路线彻底关闭。

停止条件：任何一步出现板子发热、短路、夹子读数每次不同且无法复现，停下拍照记录，不继续。

## M3/M4 工作方向（拆机后）

- 用 OpenOCD `load_image` 把 `firmware/minimal/` 的 ELF 载入 SRAM，`resume` 到入口；先验证 RAM 标记写入（`mdw`），再加 UART 输出。
- UART 引脚和基址来自原厂固件反汇编（[GPIO28 实读](archive/gpio28-word-live-2026-10-14.md)、[pinmux](board-pinmux-evidence.md)）。
- 自写 boot 镜像需满足 recovery checker（`just check-image`）和 boot0 的 ACTH 头格式（`docs/boot-complete.md`）；是否有签名验证见 `docs/boot-security-source-audit.md`。
- 备份镜像的 boot0/param 分区是恢复底线；M4 只替换 boot1 或 system 时保留 boot0，保证能回退。
