# 从已导出的系统镜像到可备份、可恢复

2026-10-12更新。目标：在这台CoMi上运行自写固件，并能恢复官方状态。**目前尚未具备试刷条件。** 参考板编译、原始ARM函数模拟与实机启动是不同验收层。

## 已确认与关键缺口

| 问题 | 当前证据 | 仍缺的决定性证据 |
|---|---|---|
| 已提取什么 | [完整system映射镜像](mapped-image-export.md)，927632 B，头/正文checksum通过 | [原始system前64 B已独立双读](nor-partition-prefixes.md)，与映射头不同；具体转换仍未知 |
| 固件存储布局 | [实际ACPT](partition-readback.md)：18项覆盖4 MiB；[缓存JEDEC线索](nor-driver-readback.md)匹配Zbit系列 | 原始boot、recovery、资源、配置等分区内容 |
| 录音数据存储 | [SD协议后端](card-state-readback.md)，与启动NOR分离 | 不应把录音sync当整机备份 |
| 保留录音能力 | 实际[MP3 DSP选择](recorder-codec-dispatch.md)，[资源路径](dsp-resource-path.md)指向NOR K区704 KiB | [完整目录已取得](nor-partition-prefixes.md)：aerecord.dsp位于24d400、110148 B；[完整540 B头已双读确认](record-dsp-header.md)，含3组非零bank；[断点导出已开始](record-dsp-export.md)，仍缺完整文件正文及加载运行验收 |
| 显示/音频BSP | [显示](display-board-evidence.md)、[pinmux](board-pinmux-evidence.md)、[音频](audio-open-path.md)实际指令与配置线索 | 物理引脚/外围型号、真实采样/显示、自写镜像启动 |
| 软件ADFU入口 | [实际应用重启代码](application-reboot-path.md)写ADFU标记并触发watchdog | 应用损坏时的独立入口、恢复态身份和可验证退出 |
| 启动校验 | [SDK安全启动能力](boot-security-source-audit.md)及实际镜像头 | CoMi boot/ROM实际策略、签名/加密处理及可接受镜像 |

## 已排查的资源取得路径

- **映射读**：已能完整导出当前system；[映射到raw的证据仍缺](mapping-candidate-audit.md)。不把SDK地址公式直接推广到其他分区。
- **NOR/SDFS shell**：[实际printk后端](printk-backend-readback.md)及[UART输出链](console-target-followup.md)已定位；现有BLE通道不回传其hex正文。[静态日志ring实测](printk-ring-capture.md)已取得4096 B，但mdb/help会自覆盖；[完整offset0扇区](nor-sector-zero.md)已取得512 B，32行各有独立双覆盖、无冲突；[同连接22次读取实测21.762 s](nor-warm-capture.md)，与原22次会话约245 s的结果一致；下一步扩展已知文件范围。释放后的fread heap buffer仍不是可靠读回对象。
- **F5F0**：[实际固件归属](f5f0-firmware-definition.md)确认Bluetooth OTA传输；启用通知存在应用状态变化，未建立备份命令或独立恢复。
- **普通录音下载**：[实际固定录音路径](recording-download-path.md)不接受直接指定NOR资源路径。保持CLI文件名限制。
- **其他dbg入口**：[完整35项表](actual-dbg-command-inventory.md)未提供新的、已验证只读且能回传原始NOR内容的路径。dumpbuf写文件；snandr有长度/缓冲问题，不作为替代。
- **官方产物/App**：[官方页面复查](official-acquisition-next.md)未取得匹配固件；[Android 1.2.4](android-runtime-followup.md)停在登录页，用户选择暂不登录。OEM相似设备协议不能替代CoMi官方包。
- **ADFU helper**：[静态初始化审计](helper-initialization-decompile.md)发现条件擦写；没有匹配CoMi的无损探测/备份配方。Ubuntu能跑分析、构建与主机脚本，不会自动获得Mac所连接设备的USB接口。

## 接下来按价值推进

1. **优先取得新的原厂/物理证据。** 匹配CoMi版本的升级包、恢复包、生产工具或正式恢复说明，能直接推进boot/资源/恢复判断；App登录仍按用户选择暂缓。若软件线索不足，实物UART/SWD/存储接口确认或同型号备用机是后续选项，尚未执行。
2. **资源读回方案须先解决正文出口。** NOR K目录/文件规则已明确；[SDFS失败返回0](sdfs-nor-read-path.md)意味着必须核对可信长度、累计字节和重复读一致性。只有返回码或日志不是成功证据。
3. **有新文件后再做完整性分析。** 固定哈希，校验容器、目录范围、分段数据和设备配置覆盖；[DSP加载器](dsp-file-loader.md)接受空sections且不检查初始seek错误，不能用加载成功替代完整性验证。
4. **恢复入口独立验收，再做自写程序。** [实际DSP地址转换](dsp-address-map.md)已证实不同于参考SDK；移植不得直接采用参考板MCU地址。 先证明不依赖应用的入口、退出方式、匹配工具/原厂镜像及恢复结果。之后才是最小启动→显示/按键→录音/BLE。当前不存在可推荐直接执行的试刷步骤。

## 可以复用的离线验证

所有脚本SHA绑定同一原始system镜像，拒绝其他输入；模拟器只执行指定ARM片段并拦截外部调用，不证明硬件工作：

```sh
uv run tools/verify_display_pixels.py artifacts/mapped-system/mapped-system.bin
uv run tools/verify_audio_adapter.py artifacts/mapped-system/mapped-system.bin
uv run tools/verify_sdfs_read.py artifacts/mapped-system/mapped-system.bin
uv run tools/verify_dsp_header.py artifacts/mapped-system/mapped-system.bin
```

显示像素、ADC参数映射、SDFS短读/失败、DSP头部边界都有独立手工oracle。进一步增加相邻函数反汇编，只有能推进上述读回、BSP或恢复缺口时才有价值；不能用离线测试数量代替缺失的实机验收。
