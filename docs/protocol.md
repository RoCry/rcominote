# Boyi BLE 协议与独立工具

来源：官方 CoMi 1.1.2 APK 的原始 JS，及 2026-10-12 自有设备捕获帧。来源/迁移版本见 [证据索引](evidence/README.md)，解析实现见 [protocol.py](../src/rcominote/protocol.py)。这是设备的 Boyi 分支；Mova 的 UUID/opcode 不能混用。当前功能验收以[能力表](cli-capabilities.md)为准，调研优先级以[路线决策](research-routes.md)为准。

## GATT

短 UUID 使用 Bluetooth 基础后缀 `-0000-1000-8000-00805f9b34fb`。

| Service | Characteristic | 用途 |
|---|---|---|
| `0000e5e0` | `0000e5e1` | 控制 write without response |
| 同上 | `0000e5e2` | 命令回复 notify |
| 同上 | `0000e5e3` | 实时音频 notify，当前 CLI 未实现接收 |
| 同上 | `0000e5e4` | 离线文件数据 notify |
| `0000180f` | `00002a19` | 标准电池 read/notify |
| `0000f5f0` | `0000f5f1` / `0000f5f2` | write / notify；协议未确定，UUID与公开SDK vendor服务不符 |
| `e49a3001-f69a-11e8-8eb2-f2801f1b9fd1` | `…3002` / `…3003` | 日志服务形状；本轮未发命令/订阅 |

广播 manufacturer ID `14172`；既有样本 manufacturer payload 为 MAC 6 B + ASCII serial 10 B。该 ID 是选择 Boyi 广播的线索，不是芯片厂商证明。连接工具同时匹配 serial，避免取第一个同类设备。

## 控制帧

`D2 2D | version=01 | command:u8 | length:u8 | payload | CRC16:LE`

CRC 覆盖帧头至 payload，初值 0、多项式 `0xA001`；非反转端序的多字节字段见下表。payload 最多 255 B；解析器检查帧头、版本、长度和 CRC。

| 命令十进制（hex） | 用途/格式 |
|---|---|
| 1 (01) | GET_SERIAL，ASCII 回复 |
| 2 (02) | GET_BIND_INFO |
| 4 (04) | SET_TIME，年减 2000、月、日、时、分、秒各 1 B；本地时间 |
| 5 (05) | GET_DEVICE_INFO，前 8 B 为 total/free 各 u32 BE；byte 11..13 固件版本；byte 14 USB 模式 |
| 6..9 (06..09) | start / stop / pause / resume |
| 10 (0A) | GET_FILE_LIST，status 0 条目，1 失败，2 终止 |
| 11 (0B) | GET_FILE_DATA，文件名 14 B + 起始偏移 u32 BE；文件流走 e5e4 |

文件条目：status 1 B、名字 14 B、size u32 BE、kind 1 B（0=call，否则 note）。下载开始回复 status 0 + size u32 BE，结束 status 2。文件名样本是本机时钟 `YYYYMMDDHHMMSS`。完整设备状态布局由解析器保存 `raw` 以便回查；容量整数的单位没有独立设备规格证明，约 58 GiB 是按 MiB 理解的估计。

## 验证范围

- 迁移前：扫描、状态、文件列表、下载、sync、录音控制、校时均有既往实机记录；MP3 格式和解码验证也来自此前记录。
- 本轮：7 个捕获帧 oracle 测试通过；新工具重新 GATT 枚举与 `info` 成功。没有重新录音、下载私人录音、校时或切换 USB 模式。
- 当前下载要求声明长度、完整字节数与结束标志，通过后原子发布；失败不发布完整目标文件。`sync` 跳过逻辑仍不能证明远端文件内容未改变。录音导出不是固件/全盘备份。
- 不实现绑定、删除、格式化、复位、USB 模式切换、OTA 和任意 shell。`record`、`set-time` 会改变设备状态，需显式调用。
