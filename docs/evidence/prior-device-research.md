---
title: 致远CoMi Note — 实机协议与主控（Boyi/炬芯）
tags: [hardware, audio-recorder, reverse-engineering]
updated: 2026-10-12
---

# 致远 CoMi Note

> 历史笔记快照。下文关于 USB 仅充电、已证实 shell 的措辞已由
> [本轮核查](../archive/firmware-roadmap.md)修正；路径仅作来源，不是运行依赖。

## 结论（2026-10-12 实机更新）

手上这台实机落到 **Boyi** 一支并实测通过：BLE 广播 company id 14172，控制服务 `0000e5e0`。自写 CLI（`research/comi/`，在 rlcdv 仓）完成扫描、状态、文件列表、下载、远程录音 start/stop/pause/resume、校时，全部实机验证。录音文件为 **MP3（MPEG-2 Layer III，16 kHz 单声道，32 kbps CBR）**，文件名 `YYYYMMDDHHMMSS`（设备本地时钟）。读/下载**无需绑定**，未绑定客户端即可取数。

**主控：炬芯 Actions Technology（强证据，非拆解）。** 设备 GATT 除 Boyi 服务外还暴露 `e49a3001-f69a-11e8-8eb2-f2801f1b9fd1` 服务（rx `…3002` write、tx `…3003` notify）。该 UUID 与字符结构逐字节等于 Actions 公开 Zephyr SDK（`lv_port_actions_technology`，bt_watch 应用）的 **BLE log service**（`application/bt_watch/src/bt_log/log_service.c`）。另见 `f5f0`(write)/`f5f2`(notify) 服务，亦为 Actions bt_watch 风格的 sppble 流。此前炬芯 SDK 深读（`docs/research/wearable-hardware/08-actions-sdk-deep-read.md`）中 OTA 服务同属 `…-f69a-11e8-8eb2-f2801f1b9fd1` 家族。**仍未拆解、无板号/丝印**，故记为"主控厂商 = 炬芯，具体型号待丝印确认"（SDK 深读中该家族对应 ATS308x/ZS308x 系列）。

**陷阱（已触发并避免）：** `e49a3001` log service 会把 TLV type 0x01 当作 shell 命令执行，且无鉴权。SDK 源码摆明这点（`_logsrv_proc_console_text` → `shell_execute_cmd`）。本轮**未**向该通道下发任何命令——既非必要（Boyi 协议已够做上位机与同步），也避免对设备下发未授权 shell。主控结论完全由**被动 GATT 枚举 + 公开 SDK 源码比对**得出。

---
以下为 2026-10-09 APK 静态分析原文，作为协议出处保留。

## 结论（APK 静态）

2026-10-09官方APK静态分析：CoMi录音卡模块支持 **Boyi、Mova** 两套协议，均不同于金正M5 PRO实测协议。此前主控未知；**2026-10-12 实机 GATT 已指向炬芯（见上）。** Mova的Nordic风格UUID不证明Nordic主控。

此前包装样本型号 **SY-N2A3F-5H2**，CMIIT ID **26J11X2GE501**，64GB、蓝牙标称5.3、包装电池写400mA（单位不规范）。第三方认证记录 https://cmiitid.cn/2026-6996 对应北京致远互联软件股份有限公司，2026-04-15；不是工信部原始证书。

## APK及复核入口

- [官方产品页](https://www.seeyon.com/CoMiNote/index.html) · [官方下载入口](https://www.seeyon.com/CoMiNote/download.html)
- 官方链接 `https://www.seeyon.com//Public/Home/CoMi_release_1.1.2_2025-12-26.apk`
- 包名com.seeyon.comi，1.1.2，versionCode4；53,960,403字节；历史样本，不保证最新。
- SHA256 `b6f1409ccaa054406c47350b4c6b05231334633778a84dfe59d4fc5c5bd95118`。
- 未安装、登录、连设备或触发升级；未验证签名证书。
- 调用链：RecordingCardOpener → ApNoteSDK.launch（SDK常量1.0.0）→ Capacitor网页模块。实际适配在APK原始JS，非单搜Java蓝牙类。
- 工作目录 `/Users/rocry/.rclv/workspaces/tg--5394806415/comi-research/`；原始报告`findings.md`；JS `jadx/resources/assets/public/assets/index-Btih_BUR.js`。
- JADX有132个反编译错误；以下证据来自原始打包JS，不依赖失败方法。包名webnote不能独立认定公司实体。

## Boyi分支

- 广播company identifier字符串14172。
- Service `0000e5e0-0000-1000-8000-00805f9b34fb`；写e5e1，命令Notify e5e2，实时音频e5e3，离线音频e5e4，同后缀。
- `D2 2D`帧头；version1、1字节命令、1字节长度、payload、CRC16（A001、初值0、结果小端）。
- App实现SN、绑定、校时、录音/暂停/恢复、文件列表/下载/删除、USB、声控、分段、降噪、屏幕背光；不代表某台全部支持。

## Mova分支

- Service `6e400001-b5a3-f393-e0a9-e50e24dcca9e`。
- 命令Notify 6e400002；write 6e400003；音频6e400004；OTA写6e400005；文件6e400006；日志6e400007，后缀相同。
- company identifier20068；clientId `CPdSgm`；广播后续16字节SN。
- opcode开头：开始录音01、版本E3、USB E4、校时E5、OTA E6、Wi-Fi F3。
- [Mova Rec商店](https://play.google.com/store/apps/details?id=com.mova.rec&hl=zh)开发者Hong Kong NaoTeng Technology Co., Limited；只是命名关联，不证明其就是CoMi供应商。

## 实机 GATT 与实测（2026-10-12，serial C261CF0430）

- 广播：`CoMi Note 2F01`，manufacturer 14172 = `MAC(6) + serial(10)` → MAC `50:C0:F0:AE:7C:0E`，serial `C261CF0430`。
- 全部服务：
  - `0000180f`（电池，标准）。
  - `e49a3001-f69a-11e8-8eb2-f2801f1b9fd1`（rx `…3002` W/WwoR，tx `…3003` notify）= **Actions log/shell service**（主控证据）。
  - `0000f5f0`（`…f5f1` W/WwoR，`…f5f2` notify）= Actions sppble 流。
  - `0000e5e0`（Boyi 控制）：write `e5e1`(WwoR)、cmd notify `e5e2`、realtime notify `e5e3`、offline notify `e5e4`。ATT MTU 247。
- `GET_DEVICE_INFO` 实测：total 59634、free 59632（≈ 64GB 机标 58 GiB 可用），充电中、电量 100、固件版本字节 `01 00 04`（v1.0.4）、录音态 idle、分段时长档位 3、降噪 9。raw 内含字符串 `xink_test`（疑似工厂/品牌内部标识）。
- 本机 `GET_BIND_INFO` = 未绑定；读/列表/下载/远程录音均在未绑定下成功。
- 下载：1916 B 文件 0.25 s；远程 start→stop 产出 `20261012093244`（9.3 s，37180 B），`sync` 跳过已存、字节一致、ffmpeg 清洁解码。

> 注：另一条 USB-CDC 口 `/dev/cu.usbmodem1201`（"Hiveton App Serial"，SiFli RT-Thread）是**另一台** e-reader（`~/w/_hw/rcwodle`），不是 CoMi。CoMi 只经 BLE，插线仅充电。

## M5对照

金正M5 PRO实测GATT service1910、write1912、notify1911；JL帧 `01 | opcode | 00 | payload`；此前OTA镜像目标JL701N/AC791N，不能套给CoMi。原始研究 `~/w/_hw/rlcdv/research/vocmas/README.md`、`~/w/_hw/rlcdv/docs/research/20261008-vocmas-m5-ota.md`。

需实机BLE广播和GATT列表才能将该台落到Boyi/Mova一支；需板号、主控丝印或对应固件才谈主控/同板。

## 2026-10-11闲鱼样本

[商品1051307363068](https://www.goofish.com/item?id=1051307363068)，查询时标价160元。卖家称64G、全新、400mAh、包装/说明书/数据线/磁吸套齐全；**称需要卖家提供账号和密码才能使用**。这是卖家陈述，未验证实际账号限制，也未核实该台底标与此前样本相同。不能据“全新”或配件齐全推定可用个人账号绑定、权益转移。

相关：[[hengxiaoxin-hengzhiyi-r1-odm-soc-research]] · [[nintaus-m5-pro-vocmas-protocol-ota-research-2026-10]]
