# 从已导出的系统镜像到可备份、可恢复

2026-10-12更新。目标：在这台CoMi上运行自写固件，并能恢复官方状态。**目前尚未具备试刷条件。** 参考板编译、原始ARM函数模拟与实机启动是不同验收层。

## 已确认与关键缺口

| 问题 | 当前证据 | 仍缺的决定性证据 |
|---|---|---|
| 已提取什么 | [完整system映射镜像](../mapped-image-export.md)，927632 B，头/正文checksum通过；[原始512 B头转换已匹配](../raw-storage-codec.md)，同一状态解码recovery头且checksum通过 | [完整boot已通过头/正文checksum](../boot-complete.md)；原始system正文转换、完整recovery及独立恢复仍未验收 |
| 固件存储布局 | [实际ACPT](../partition-readback.md)：18项覆盖4 MiB；[缓存JEDEC线索](../nor-driver-readback.md)匹配Zbit系列 | 原始boot、recovery、资源、配置等分区内容 |
| 录音数据存储 | [SD协议后端](../card-state-readback.md)，与启动NOR分离 | 不应把录音sync当整机备份 |
| 保留录音能力 | 实际[MP3 DSP选择](../recorder-codec-dispatch.md)，[资源路径](../dsp-resource-path.md)指向NOR K区704 KiB | [完整目录已取得](../nor-partition-prefixes.md)：aerecord.dsp位于24d400、110148 B；[完整540 B头已双读确认](../record-dsp-header.md)，含3组非零bank；[完整110148 B文件已取得](../record-dsp-export.md)，216块双覆盖、目录checksum和全部段结构通过；仍缺自写固件加载运行验收 |
| 显示/音频BSP | [显示](../display-board-evidence.md)、[pinmux](../board-pinmux-evidence.md)、[音频](../audio-open-path.md)实际指令与配置线索 | 物理引脚/外围型号、真实采样/显示、自写镜像启动 |
| 软件ADFU入口 | [实际boot](../actual-boot-flow.md)识别应用的ADFU标记；recovery校验失败也转ROM表`0x19c`入口；[备用boot前512 B为FF](../boot-recovery-prefixes.md) | ROM实际目标/协议、boot损坏时入口、恢复态身份和可验证退出；静态路径不等于救砖验收 |
| 启动校验 | [SDK安全启动能力](../boot-security-source-audit.md)及实际镜像头 | CoMi boot/ROM实际策略、签名/加密处理及可接受镜像 |

## 已排查的资源取得路径

- **映射读**：已能完整导出当前system；[映射到raw的证据仍缺](../mapping-candidate-audit.md)。不把SDK地址公式直接推广到其他分区。
- **NOR/SDFS shell**：[实际printk后端](../printk-backend-readback.md)及[UART输出链](../console-target-followup.md)已定位；现有BLE通道不回传其hex正文。[静态日志ring实测](../printk-ring-capture.md)已取得4096 B，但mdb/help会自覆盖；[完整offset0扇区](../nor-sector-zero.md)已取得512 B，32行各有独立双覆盖、无冲突；[同连接22次读取实测21.762 s](nor-warm-capture.md)，与原22次会话约245 s的结果一致；现已完成216块录音DSP读回；下一步优先boot/recovery内容。释放后的fread heap buffer仍不是可靠读回对象。
- **F5F0**：[实际固件归属](../f5f0-firmware-definition.md)确认Bluetooth OTA传输；启用通知存在应用状态变化，未建立备份命令或独立恢复。
- **普通录音下载**：[实际固定录音路径](../recording-download-path.md)不接受直接指定NOR资源路径。保持CLI文件名限制。
- **其他dbg入口**：[完整35项表](../actual-dbg-command-inventory.md)未提供新的、已验证只读且能回传原始NOR内容的路径。dumpbuf写文件；snandr有长度/缓冲问题，不作为替代。
- **官方产物/App**：[官方页面复查](../official-acquisition-next.md)未取得匹配固件；[Android 1.2.4](../android-runtime-followup.md)停在登录页，用户选择暂不登录。OEM相似设备协议不能替代CoMi官方包。
- **ADFU helper**：[静态初始化审计](../helper-initialization-decompile.md)发现条件擦写；没有匹配CoMi的无损探测/备份配方。Ubuntu能跑分析、构建与主机脚本，不会自动获得Mac所连接设备的USB接口。

## 接下来按价值推进

优先级以[当前路线决策](research-routes.md)为准；不再把补齐recovery日志读回作为默认任务。

1. **优先取得新的原厂/物理证据。** 匹配CoMi版本的升级包、恢复包、生产工具或正式恢复说明，能直接推进boot/资源/恢复判断；App登录仍按用户选择暂缓。若软件线索不足，实物UART/SWD/存储接口确认或同型号备用机是后续选项，尚未执行。
2. **先确定高效原生传输。** 复用SDK和完整system/boot，补齐实际CDC命令表及生产工具选择逻辑；明确是否存在正文读回。旧批量NOR日志出口归档，已有数据保留，不能继续用慢速采集替代传输路线决策。
3. **继续核对原始存储与映射视图。** 固定哈希，校验容器、目录范围、分段数据和设备配置覆盖；[DSP加载器](../dsp-file-loader.md)接受空sections且不检查初始seek错误，不能用加载成功替代完整性验证。
4. **恢复入口独立验收，再做自写程序。** [实际DSP地址转换](../dsp-address-map.md)已证实不同于参考SDK；移植不得直接采用参考板MCU地址。 先证明不依赖应用的入口、退出方式、匹配工具/原厂镜像及恢复结果。之后才是最小启动→显示/按键→录音/BLE。当前不存在可推荐直接执行的试刷步骤。

## 可以复用的离线验证

所有脚本SHA绑定同一原始system镜像，拒绝其他输入；模拟器只执行指定ARM片段并拦截外部调用，不证明硬件工作：

```sh
uv run tools/verify_display_pixels.py artifacts/mapped-system/mapped-system.bin
uv run tools/verify_audio_adapter.py artifacts/mapped-system/mapped-system.bin
uv run tools/verify_sdfs_read.py artifacts/mapped-system/mapped-system.bin
uv run tools/verify_dsp_header.py artifacts/mapped-system/mapped-system.bin
```

显示像素、ADC参数映射、SDFS短读/失败、DSP头部边界都有独立手工oracle。进一步增加相邻函数反汇编，只有能推进上述读回、BSP或恢复缺口时才有价值；不能用离线测试数量代替缺失的实机验收。
