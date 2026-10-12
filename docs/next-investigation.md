# 下一阶段：从可查询到可备份、可恢复

2026-10-12。目的仍是自写固件；不把参考板编译成功当作 CoMi 启动成功。

| 问题 | 当前状态 | 下一份决定性证据 |
|---|---|---|
| BLE可否返回存储内容 | 已独立核对6935不同映射字节，含744 B ACPT | 实际物理读取与映射视图的对应关系 |
| fread为何只有状态行 | 源码解释明确，实机输出路由仍有限 | 可返回原始Flash内容的确认路径 |
| 精确SoC/板级/分区 | 18项NOR配置覆盖4 MiB，缓存ID匹配Zbit系列；板级仍未知 | 当前boot-info、镜像头、控制器/板号 |
| 自写镜像是否可启动 | 未解决；ACPT flag2不能证明实机签名/加密状态 | 实际boot检查分支、映射与header |
| 应用失效是否还能恢复 | 未解决；有recovery配置但未验收 | 独立入口、匹配镜像、退出/恢复证明 |

最新证据：[ACPT表](partition-readback.md)、[加密/签名/恢复源码边界](boot-security-source-audit.md)。下文旧阶段记录保留历史上下文，字节计数及“分区未知”按本表更新。

## 现在能做的工作，按价值排序

1. **沿已证实的映射代码开展有界分析。** 已完成 app/system/kernel 帮助、两个固定配置 getter和线程表。依据实机入口及ABI核对，16字节代码已重读一致；不自动给出完整flash映射。没有明确映射前不盲读 SDK 地址；不重读已释放的 fread 缓冲。见 [读取路线](readback-routes.md)。
2. **取得实际固件产物。** 优先官方原版升级包、售后恢复包、匹配版本生产工具；其次官方 App 的实际升级页面/网络流程。已有1.1.2静态包无可用路径，1.2.4的两个不透明文件仍未归属。REA 已完成归档核查；现有JADX CLI另已反编译1.2.4外壳，原应用由native加载。1.1.2配置了远程页面，当前界面需真实App运行证据。[App 证据](app-upgrade.md)
3. **有镜像后再做格式与板级逆向。** 固定 SHA-256，识别启动头、分区、资源、签名封装，提取厂商设备树/配置/字符串与驱动线索。Ubuntu 可承担解包、编译和离线分析；SSH 不会让接在 Mac 的设备自动出现在 PC USB 树上。
4. **恢复入口单独验收。** 正常运行的 shell 里存在 reboot adfu 不能证明应用刷坏后还能进入。先取得准确模式入口与退出方法、工具行为，再进行恢复模式实验。当前尚未切换 ADFU。
5. **小块读回→分区备份→最小自写程序。** 每一步以前一步的证据为输入；备份覆盖 boot/应用/资源/配置与设备独有数据，静态区重复读一致。最后才进入真实板级最小程序启动、录音/BLE 验收。

## 不拆机的实际边界

继续 BLE/官方产物调查不需要拆机。若厂商不给资料、外露接口没有独立恢复入口、原厂命令也无法读出原始存储，则软件路线可能停在这里。此时拆机确认丝印和 UART/SWD/存储引脚，或取得同型号备用机，能减少关键未知；它们仍不自动绕过读保护、签名或校准问题。

本轮不需要用户执行额外操作。优先做有证据支持的读取/产物分析；一旦剩下必须改变启动状态或实物操作的步骤，先给出明确操作、预期观察和退出方法。

最新进展：[代码读回](mapped-code-readback.md)、[官方远程页面与原厂包](official-acquisition-followup.md)。

后续：已沿入口指令取得69 B、五个非连续位置的独立一致读回，实际字符串`_logsrv_init`支持与SDK初始化代码对应；[代码引用报告](code-reference-followup.md)。[当前官方页面复查](official-acquisition-next.md)仍未取得原厂固件。

公开LEOPARD helper已静态确认`rm`/`rs`读取处理器；NAND首次读取有延迟初始化，尚不能视为无写入备份路径。[helper证据](helper-static-followup.md)、[可复现Ubuntu反编译](offline-helper-analysis.md)。Android实机CoMi1.2.4停在登录页，用户选择暂不登录；[运行时记录](android-runtime-followup.md)。

进一步审计已证明该NAND初始化存在可达的条件擦除/编程路径，见[指令与调用链](helper-initialization-decompile.md)。另从相关设备线索取得两款官方APK，定位到AI DVR Link固件元数据POST和AOTA解析，但没有合法匹配账号/设备上下文或固件文件；[OEM线索边界](oem-protocol-lead.md)。这些App协议与CoMi不同，不可混用。

[vendor服务审计](vendor-service-followup.md)：公开SDK的`vendor_read`接收主机上传，完整命令表无固件读回；UUID与CoMi F5F0不匹配。SDK OTA通知订阅可能启动升级状态并关闭写保护，不能用作被动探测。下一步优先追踪实际CoMi代码中的F5F0及接收分发器；账号登录按用户要求暂缓，不影响离线分析。

实机后续已取得[380 B vendor代码/常量](vendor-code-readback.md)，独立重读一致；实际线程解析D22D/Boyi风格帧，而非公开SDK上传帧。直接调用1000b3b4是后续识别处理函数的具体入口；F5F0仍未归属。与此前logsrv样本合计449 B，不是完整固件。

该调用现已证明为[命令分发表](vendor-dispatch-followup.md)：23个官方请求编号+额外`3a`，后者引用`BT_NAME`，不能据此视为升级入口。累计997 B独立一致；固件备份/恢复仍未知。下一份有用证据是设备信息构造函数1000aad0的真实字段来源、F5F0实际绑定，或存储映射/启动元数据；不通过发送未知命令试错。

最新：[SD/MMC驱动状态](card-state-readback.md)已将录音存储追到SD协议类别、512 B逻辑扇区；累计2916 B独立一致。仍未知启动固件介质/分区，下一步优先追踪实际启动分区表引用，或SD初始化/CID处理。Android登录按用户要求暂缓。CLI没有完整备份、烧录、恢复能力。

[device表与独立Flash](boot-storage-device-readback.md)：实机31个对象，spi_flash ready且配置32 MiB；read wrapper实际位于RAM。下一跳是literal100bc294的底层Flash函数表；启动分区另走[已知sdfs帮助→实际shell descriptor→partition getter](partition-reference-route.md)。没有依据执行read callback、重启或烧录。

[NOR缓存ID](nor-driver-readback.md)已读：16405e，匹配Zbit 32 Mbit／4 MiB系列，driver32 MiB配置并非物理容量实证。下一份关键证据仍是启动分区；从已读logsrv分支1000bf3c→1000bf58追timer callback，比继续追分配器更直接。

[boot-info候选](boot-info-readback.md)：system/nor offset24000与ACPT相符，但param_phy字段为0；下步核对实际getter/镜像头与映射，不根据候选布局直接扩成整片备份。
