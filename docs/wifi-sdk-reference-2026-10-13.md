# 已取得 SDK 的 Wi-Fi 文件传输实现

2026-10-13；仅固定源码审阅，无设备 I/O、SDK 执行或吞吐测试。

**REC_JX3 确有录音文件经 Wi-Fi/WebSocket 传输的真实主机代码，依赖外接 ESP32-C3；不是 Actions 芯片内置 Wi-Fi 的证据，也不是 CoMi 本机已安装或启用 Wi-Fi 的证据。当前源码快照还存在普通 BLE 首次启用路径的初始化缺口，不能宣称整套链已经可运行。**

## 来源与适用范围

第三方仓库 [`szsheep/rec_jx3@6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b`][repo]。本轮核对 Ubuntu 完整 clone HEAD；本地已取得的 177 个作用域内文件全部重新通过 manifest SHA-256。固定文件摘要、获取方法见 [source manifest](evidence/recorder-reference-2026-10-13/source-manifest.json) / [获取报告](domestic-sdk-followup-2026-10-13.md)。这不是 Actions 或 CoMi 官方发布。

该包为 LEOPARD/M33；应用 board 名 `ats3085s_dev_rec_card`，SPI 模块注释称主机 S3089P。二者均不能改写成本机 `ats3085l_dvb_watch_ext_nor_max` / Cortex-M4 的匹配 BSP。[平台差异与实际 GATT/录音链比较](domestic-sdk-followup-2026-10-13.md)。

## 外部 Wi-Fi 硬件合同

| 来源 | 明确内容 | 限制 |
|---|---|---|
| `spihd_config.h:43–98`、`wifi_proto/Kconfig:3–7` | ESP32-C3 从机；主机 `SPI_2`，20 MHz、CPOL+CPHA（mode 3）、8-bit、MSB first、single-line SPI | 源配置，不是实测频率/吞吐 |
| `spihd_transport.c:36–74,209` | 实际绑定 SPI device，以上宏填入 `spi_config`，调用 `spi_transceive` | 真实硬件调用代码，不是 mock |
| `board_gpio_ctrl.c:30–39` | GPIO57 驱动从芯片 CHIP_EN，高有效；通知输入 GPIO16 | 参考板接线，不能套到 CoMi |
| `board_gpio_ctrl.c:63–78` | GPIO50/49 控制 Wi-Fi/BLE 天线选择 | 本机是否有该开关、天线/射频链未知 |
| `spihd_config.h:45–59` | 老注释写“C3 GPIO9→主机 GPIO26”，有效宏却为主机 GPIO16 | 与 board helper 的 16 一致；26 不采用为已验证引脚 |

原始来源：[配置][config]、[实际 transport][transport]、[GPIO helper][gpio]。因此此方案要求额外 Wi-Fi 芯片及其固件、供电/通知/SPI 和射频硬件；仅换手机 App 或打开本机配置字段不能凭空获得这条链。

## 当前构建是否只是 mock

`prj.conf:252–254` 启用 `CONFIG_WIFI_PROTO_APP`、`CONFIG_SPIHDR_TRANS`、`CONFIG_REC_CARD_SYNC`。`src/CMakeLists.txt:9–11` 根据这些开关添加三个模块；SPI 模块编译 `spihd_master/transport/host_wifi_proxy/manager`；Wi-Fi 模块只编译 `wifi_proto.c`、`md5.c`，明确排除 `wifi_proto_mock.c`。源码含 mock 文件不等于当前构建走 mock。[prj.conf][prj]、[构建分派][cmake]、[Wi-Fi 模块 CMake][wifi-cmake]。

但有明确整合边界：

- `app_main.c:39–42` 不在启动时初始化 SPI/proxy，注释委托按需 `spihd_manager_activate()`；`54–59` 启动 WS 协议任务。
- `spihd_manager.c:29–81` 完整顺序是 `spihd_init → spihd_activate → host_wifi_proxy_init → wifi_proto_init`。
- 完整 `application/rec_card` 符号引用核对中，manager 的实际调用只在 `system_app_shell.c:635`；该 shell 路径先选择 Wi-Fi 天线。
- 普通 BLE `ble_dp_start_wifi()` 在未 ready 时直接调用 `spihd_activate()`（`1131–1137`），没有调用上述 manager。`spihd_activate():1955–1985` 是已有 worker 的状态检查/投递/等待，不替它创建 worker 或注册 Wi-Fi/WS 回调。

故**真实源实现存在，普通 BLE 冷启动的初始化连接未闭合**；可能依赖此前 shell 激活或尚未并入的应用修订。本轮不修补、不运行，也不把该缺口外推为硬件不能实现。[manager][manager]、[BLE 启动][ble]、[master][master]、[shell:620–646][shell]、[app 初始化][app]。

## 文件传输工作流：源中真实做了什么

1. BLE 启用接口 `ble_dp_start_wifi():1090–1185` 拒绝正在录音；准备 AP SSID/密码，再 `host_wifi_start(HOST_WIFI_MODE_AP, …)`。代码明确由 ESP32 建 AP、手机连接；返回 0 仅表示指令已接收，实际 AP/WS 状态经事件回来。函数上方旧注释说 `start_saved`，当前代码实际使用显式 AP 参数，应以代码为准。[BLE 路径][ble]。
2. `app_wifi_bridge.c:21–68` 将 AP ready、终端加入/离开、WS 连接/断开事件转交设备状态和 Wi-Fi 协议；`wifi_proto.c:144–145` 向 proxy 注册 WS 数据接收 hook。[bridge][bridge]、[wifi_proto][proto]。
3. `ws_proto_task.c:89–101` 真实 handler 表包含握手、列表、同步、删除、停止及 FOTA。`432–487` 的 SYNC_FILE 读取 `session/start/end`，检查文件存在和文件系统容量，再启动独立传输线程；并非只有协议名或固定测试回复。[WS task][task]。
4. 传输线程 `164–249` 通过 `rec_fm_open_by_sid(session)` 打开实际录音流，按请求起点 seek，`stream_read` 每块最多 2838 B；批次四个 PDU，经 `wifi_proto_sync_content_append()` 进入 SPI `CMD_SEND_WS_SYNC=0x36` / `CMD_SEND_WS_SYNC_END=0x37`，由从机 `EVENT_NEED_MORE_DATA` 驱动下一批。结束发送 `CMD_SYNC_STOP` 并关闭流。[WS task][task]、[SPI command 定义][session]。

可复用价值是“录音文件→协议 PDU→SPI 协处理器→Wi-Fi”的主机分层与流控源码。20 MHz 是配置时钟；2838 B 是源块大小，均不是手机端有效速度、可靠性或 CoMi 实测结论。FOTA handler 的存在也不证明本机可用 Wi-Fi 刷机或独立恢复。

## 从芯片材料仍有缺口

完整树内的 `docs/new_spi_docs/wifi_manager_design.md` 指定 C3 + S3089P，并列出从端 `wifi_manager.c`、`wifi_proxy.c`、`spihd_slave.c`。本轮完整 tracked 路径检索未找到这三个同名实现；设计文档的 30 MHz/4092 B 也与当前主机宏 20 MHz/3072 B 不同，不能照文档替换代码参数。[固定设计文档][design]。

仓库另有 `framework/wifi/esp/wifi_hosted/wifi_slave/esp32_wifi_demo`，README 写 **4-bit SPI / 40 MHz**，构建步骤为 `idf.py set-target esp32c6`。这是另一条 ESP hosted 参考例，不能据其存在宣布已取得当前 C3 SPI-HD/WS 从机配套固件。[该 demo README][demo]。本轮没有据通用 ESP32 目录名扩大到整仓所有潜在别名实现。

## 对 CoMi 的结论

这份新源码证明“已取得的第三方 Actions 录音卡 SDK 包含外接 Wi-Fi 文件传输设计及主机实现”。它不能证明 ATS3085L 自带 Wi-Fi、CoMi 有 ESP32-C3、CoMi 固件实现相同 AP/WS 协议，或 CoMi App 的通用 Wi-Fi 页面适用于本机。确认本机能力仍需对应硬件/原厂固件/官方型号功能的正证据；参考代码可用于未来平台设计，不能作为对当前设备发送新命令的依据。

[repo]: https://gitee.com/szsheep/rec_jx3/tree/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b
[config]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/spihd_trans/spihd_config.h#L43-L98
[transport]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/spihd_trans/spihd_transport.c#L36-L74
[gpio]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/device/board_gpio_ctrl.c#L30-L78
[prj]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/prj.conf#L252-L254
[cmake]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/CMakeLists.txt#L9-L11
[wifi-cmake]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/wifi_proto/CMakeLists.txt
[manager]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/spihd_trans/spihd_manager.c#L29-L81
[ble]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/ble/ble_data_provider.c#L1090-L1185
[master]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/spihd_trans/spihd_master.c#L1955-L1985
[shell]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/main/system_app_shell.c#L620-L646
[app]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/app/app_main.c#L39-L59
[bridge]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/app/app_wifi_bridge.c#L21-L68
[proto]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/wifi_proto/wifi_proto.c
[task]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/sync/ws_proto_task.c
[session]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/application/rec_card/src/spihd_trans/spihd_session.h#L90-L96
[design]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/docs/new_spi_docs/wifi_manager_design.md
[demo]: https://gitee.com/szsheep/rec_jx3/blob/6c8baddd29e0c1f4fe7998c57116fa99fc89ef1b/framework/wifi/esp/wifi_hosted/wifi_slave/esp32_wifi_demo/README.md

## 补查：本机 `WIFI_OTA_VIEW` 字符串

本轮从[固定原厂 system](evidence/minimal-image-2026-10-13/original-system.bin.gz)直接复核三个 NUL 结尾字符串：`100c398a` 为 `view_id == WIFI_OTA_VIEW`；`100c39a3` 为 `WEST_TOPDIR/application/bt_watch/src/recorder/record/record_wifi_ota_view.c`；`100c39ef` 为 `wifi_ota_state == %d\n`。它们提供一个实际编入镜像的命名线索，但字符串自身不能区分“Wi-Fi 传输”与“名为 Wi-Fi OTA 的状态/进度界面”。

对固定 LVGL 本地树和 REC_JX3 本地应用子树搜索文件名 `record_wifi_ota_view` / `wifi_ota_view` 无命中；对 LVGL `application/`、REC_JX3 完整固定 clone 的 `application/` 与 `framework/` 搜索 `WIFI_OTA_VIEW`、`wifi_ota_state`、`record_wifi_ota` 也无命中。未取得该确切 view 源码，因此本次**既不把它判成纯通用 UI，也不把它当作真实 Wi-Fi 后端证明**；不继续扩展名称猜测或逐函数追踪。
