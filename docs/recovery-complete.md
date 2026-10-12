# 完整 recovery 与应用启动交接

2026-10-13。自有 C261CF0430 / FW010004。**本机 recovery 原始与明文镜像均完整取得，63,288 B，头及正文校验通过。缺失的应用启动交接代码已补齐；整机备份、刷写、独立恢复仍未验证。**

## 取得了什么

证据目录：[recovery-complete-2026-10-13](evidence/recovery-complete-2026-10-13/)。

| 产物 / 检查 | 结果 |
|---|---|
| [原始镜像](evidence/recovery-complete-2026-10-13/recovery-raw.bin) | NOR `4000` 起63,288 B；SHA256 `14a899d181c38430931649169671a4812fa44e7a32978f2c3beded51472b1a01` |
| [解码镜像](evidence/recovery-complete-2026-10-13/recovery-decoded.bin) | 既有32 B重置转换；SHA256 `19625b7b70eb8e4a91c889792c0ca383f51ea205629e67565b59c47d15e09906` |
| 独立旧前缀 | 原始、明文前48,128 B均与旧产物一致；边界块93另外双读一致 |
| 缺失尾部 | 块94..123各独立读两次，30对全部一致；最后块裁去200 B |
| 头 | 512 B；与独立头SHA一致；LE32加法和 `ffffffff` |
| 正文 | 62,776 B；LE32和 `aaa4f495` + 存储值 `555b0b6a` = `ffffffff`，模2³² |
| 独立复核 | root与Astra核对完整镜像、旧前缀、块112..115及六段代码/literal；Astra独立重算加法和 |

使用[SD桥接](sd-file-bridge.md)：固定 `fread` → printk ring → SD → Boyi下载。每次读取先采不含NOR行的基线，再采带唯一文件标记的结果；核对设备身份、固定代码guard、原始帧/ACK/STOP/F1、命令/offset绑定和环形连续32行。修正版 `checked_read` 对全部缓存重新离线复验通过；不同缓存/输出立即报错，不填零、不自动更换算法。

[实际采集报告](evidence/recovery-complete-2026-10-13/acquisition-report.json)：复用预先取得的93对，剩余采集约1090.4 s（18分10秒），无失败/重试。[report.json](evidence/recovery-complete-2026-10-13/report.json)是随后修正版的离线复验，约0.6 s，不能当采集耗时。尾部只有15 KiB，当前流程仍不足以支持高效4 MiB整片备份。

副作用：62次producer读取，每次基线/结果各一个4 KiB文件，共124个文件仍在SD；[名字、路径和哈希清单](evidence/recovery-complete-2026-10-13/sd-files.json)。扩展名沿用下载接口的`.mp3`，内容不是录音。未审计删除命令，未清理；未写NOR、复位或执行新代码。采集前后均为本机FW010004、录音空闲。[captures.tar.gz](evidence/recovery-complete-2026-10-13/captures.tar.gz)保留全部62组结果与基线，报告移除个人录音列表，原始帧/命令保留。

## 缺失代码回答了什么

启动复制参数呈现镜像 `1100e098` → RAM `18000000`；对应交接入口 `18000450` 来自镜像 `1100e4e8`。以下是完整镜像中的**静态解释**；ROM复制helper及RAM执行未实测。校验通过不等于执行证明。

[可复现指令/literal](evidence/recovery-complete-2026-10-13/handoff.json)限定六个完整模块：unmap `180000b8..c8`、sum `180000e8..100`、checker `18000100..20c`、jump `18000218..21e`、map `1800021e..22e`、handoff `18000450..4b0`；末端不含，literal另列。

1. **映射**：交接函数禁IRQ、执行DSB，调用未展开的准备helper `180014e8`；保存slot0两字后，将 `40010300/304` 写为 `1000000f` 与物理offset（attribute非零则OR `80000000`）。随后调用未展开的invalidate形状helper `180000a4`。参考SDK称bit31为CRC enable；不能称为验签开关，也未从这些写入证明具体转换算法。
2. **正常ACTH布局**：头在 `10000000`；SP取 `+200`，entry取 `+204`。entry须为奇数，且unsigned(entry−`10000000`)≤`200000`，即奇数 `10000001..101fffff`。SP保存至 `180018dc`。头长度按u16 `+24` 向下取4字节；头LE32和须为 `ffffffff`，正文和加 `+1c` 存储值须为 `ffffffff`。
3. **其他分支**：也接受头在base+`200`、向量在base的布局，此时正文从base计和后减头 `+20` 存储值。两处magic皆不匹配且base+`18`非零返回−10；为零则沿第一向量布局。entry不合法返回−12。body-size为零直接成功、不做头/正文校验。这是观察到的分支，不能作为制作试刷镜像的建议。
4. **大小与授权边界**：非零size limit可触发−13，但交接caller传0，故此限制关闭；完整checker内未见分区末端检查。头/正文错误分别−14/−15。这里是普通32位加法校验；实际完整函数没有参考SDK `IMAGE_F_ENCRYPTED` / `image_security_data_check` 分支。**仅说明这个局部gate；更早ROM/boot授权、准备helper、全启动链是否接受新镜像仍未知。**
5. **成功跳转**：六字节stub `MSR PSP,r0; BX r1`。它自身不复位、不改MSP/VTOR/CONTROL；不能忽略准备helper和应用startup对CPU/硬件状态的要求。

### 失败恢复存在实际别名问题

handoff用局部 `[sp+4]` 保存旧 `40010300`，却也将它作为checker的 `entry_out`。checker在后续大小/校验检查**之前**写入候选entry。因此−13/−14/−15失败路径虽清映射再“恢复”，第一字可能已经是候选entry，而非旧映射；第二字仍取保存的旧offset。−10/−12发生在覆盖之前。

此别名同时存在于实际指令与[固定参考C的 `app_image_check` / `boot_nor_ram`](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L368)。**不能把“校验失败返回”当可靠映射恢复，更不能当整机自动回滚。** 未在设备制造失败。

## 如何离线复现，以及下一道门槛

```sh
# 仅读取仓库镜像；独立重算校验、解码固定六段Thumb指令，不连接设备。
uv run tools/inspect_recovery_handoff.py \
  docs/evidence/recovery-complete-2026-10-13/recovery-decoded.bin
```

`src/rcominote/experiments/recovery_tail.py`保留固定范围采集与缓存复验，不进入默认CLI。新采集须显式 `--create-sd-files`；完整缓存可离线复验，但仍需原始已校验system镜像核对代码guard。旧 `archive/recovery_export.py`慢速默认路线继续退役。

这次补齐了原厂recovery及本地system准入/交接契约。下一阶段仍抓三项：匹配ATS3085L/LARK M4 BSP与库；原厂完整生产包/host与原始表示；独立可退出的加载/恢复入口。[后续两个param原始槽已完整取得](param-slots.md)，主槽有效、备用槽全FF；boot1、个体NVRAM和完整资源仍未完整备份，system映射镜像也不是物理NOR原始镜像。暂存直接XIP→SD失败原因、通用文件管理和细碎callee审计，不将本次有界成功扩大成整片备份/可安全刷机结论。
