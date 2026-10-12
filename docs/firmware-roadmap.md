# 自写固件：先解决板级识别与可恢复性

更新：2026-10-12。此文是研究路线，不代表已经验证能刷机。

## 证据决定路径

| 次序 | 要回答的问题 | 具体动作与产物 | 推进条件 |
|---|---|---|---|
| 1 | USB 是否能传输数据 | 已知数据线；记录插拔前后完整 USB 树、设备屏幕模式；核对 App USB 开关与枚举变化 | 按 VID/PID、序列号和插拔差分确认设备，不凭端口名字猜 |
| 2 | 主控与外围是什么 | 拆机，清晰记录正反面板号、SoC/存储/电源/音频器件丝印、屏幕软排线编号、测试点布局 | 精确 SoC、板版本、存储类型和供电电压；不要从 64 GB 容量推定 eMMC |
| 3 | 怎么回到原厂状态 | 获取对应型号原厂包及升级路径；查 ROM 下载模式、UART/SWD 测试点；确认能备份哪些区域 | 恢复入口不依赖当前应用仍能启动；保留校准、身份、分区和原厂镜像 |
| 4 | 能否装自写镜像 | 核对 secure boot/eFuse、签名要求、压缩/差分/完整包差异、bootloader 与存储布局 | 原厂包、实际配置或受控验证支持结论；参考 SDK 的默认值不足以证明 |
| 5 | 最小 bring-up | 为实板建立 BSP；先串口/日志和确定的 GPIO，再存储、麦克风、按键、屏幕、BLE | 对照真实板级引脚；以最小镜像证明一次构建→加载→观测闭环 |
| 6 | 录音产品固件 | 确认音频采样链、供电状态、存储掉电一致性、导出协议后再组合 | 音频质量/时钟/功耗用实测验证，格式与状态机用主机测试 |

优先级判断：USB 对照成本最低；芯片丝印最能收敛 BSP；恢复入口决定能否承担第一次固件实验。没有 CoMi 板级资料时，直接刷 bt_watch 示例没有可靠依据。

## 本轮修正的交接推断

- **“BLE-only / 线只能充电”**：此前连接方式的观察。App 存在 `SET_USB_MODE=0x13`，设备当前上报 `usb_mode=true`，仍不能据此确认 USB 数据线连通或某种 USB class。`usb-devices` 主要列串口，不出现 CoMi 串口也不能排除 MSC/HID/专用下载接口。
- **“未鉴权任意 shell 已存在”**：SDK 服务注册和命令分发确有对应源码；shell 执行受编译配置限制。CoMi 服务存在已实测，命令执行能力没有实测。
- **“OTA 不签名”**：外层容器 CRC 与固件签名是不同层；SDK 存在签名和 secure boot 支持。CoMi 状态未知。
- **“Mova OTA 已可用”**：App 常量/UUID 不等于完整升级实现，更不等于 Boyi 设备支持。见 [APK 分析](app-upgrade.md)。

## 最小采集步骤

```sh
just scan
just gatt --out artifacts/before.json
just comi info
# 全 USB 树，能包含非串口设备；不发送复位/探测指令。
system_profiler SPUSBDataType -json > artifacts/usb-before.json
# 人工使用已确认的数据线连接指定 CoMi 后再次采集。
system_profiler SPUSBDataType -json > artifacts/usb-after.json
diff -u artifacts/usb-before.json artifacts/usb-after.json
```

有人工动作时记录动作、线材和屏幕状态；没有插拔对照的 USB 快照不能给接口归属定论。此前 `/dev/cu.usbmodem1201` 已识别为另一台 Hiveton，不能用它测试 CoMi。

将来尝试日志通道时，先核对 framing 与编译路径，再限定最小诊断动作；本轮不提供通用命令执行器。将来添加 flash 目标时必须先有准确目标选择、分区保护、失败不自动启动和实机验收，当前 `just` 默认只列出命令。

## 明确未知

SoC 精确料号/架构、RAM/PSRAM、主固件介质与录音存储连接、显示控制器/分辨率/引脚、麦克风通道与接口、电池充电/检测电路、按键与唤醒、ROM 下载入口、串口电平、安全启动状态、原厂固件 URL、板级 SDK 授权及闭源库依赖。以上均不能从现有 BLE GATT 单独反推出。
