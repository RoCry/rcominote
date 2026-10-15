# SDK生产包：默认生成链与CoMi材料缺口

2026-10-13。固定SDK `lvgl/lv_port_actions_technology@26f51e584940d5b141cd1d09d2629d69b595f579`。
源码核对＋未修改ATF打包器的离线实验＋maker静态反编译/样例恢复；没有运行maker、下载器或helper，没有设备I/O。
[来源hash、配置与封装实验](evidence/production-package-contract-2026-10-13.json)均绑定固定Git blob。

**当前默认 `.fw` 是外层生产/测试容器；其中的 `upgrade.fw`、原始NOR镜像与BLE AOTA各有不同契约。**
公共LARK材料仍不足以形成匹配CoMi的生产包。后续取得文件时，先核对内容与生效配置，不按扩展名或目录名选工具。

## 默认生成链：哪些配置实际生效

[zephyr/build.py][build]先从编译输出读取SoC，再按顺序组装 `_firmware/bin`：

| 顺序 | 输入 | 语义 |
|---|---|---|
| 1 | `tools/prebuilt/<soc>/common/bin`、`<soc>/bin`、`<soc>/prebuild` | 家族默认材料；前两次复制展平文件，prebuild保留目录 |
| 2 | 板目录的adfus/adfus_u、mbrec、afi、bootloader.ini、nand_id、recovery、fw_product | 存在才覆盖同名文件 |
| 3 | 应用prebuild、应用配置prebuild；配置E_CHECK、fwimage.cfg、bin | 后面的文件覆盖前面的；目录合并保留未覆盖文件 |
| 4 | 后续boot后处理、应用镜像、签名替换等 | 不能只据最初家族目录推断最终包内容 |

`firmware.xml`也按板→应用→应用配置覆盖。[前置组装源码][build]
因此 `CHIP_NAME="ATS3085L"`、S/E命名板目录或一份LARK cfg，均不能替代最终组装目录和完整生产配置。

[build_firmware.py的main][main]默认调用 `generate_earphone_firmware()`；名称中的earphone不限制它只用于耳机。
它走如下路径：

1. `parse_config()`生成分区/版本参数，复制 `bin → bin_orig`；之后才在 `bin`重建SDFS、追加系统SDFS、加CRC及条件加密。[快照顺序][snapshot]
2. 从 `bin_orig`生成 `fw_maker.cfg`、`product.ini`。生效include依次为 `fw_product.cfg`、可选 `fwimage.cfg`、`config/fw_configuration.cfg`。[配置生成][production]
3. Linux经 `python2 -O PyMaker.pyo`产生 `bin_orig/ATT/upgrade.fw`；Windows用maker.exe。[内部包生成][maker]
4. 将ATT目录和大于4 MiB的DFU文件交给 `build_atf_image.py`，生成外层 `.fw`。这些大文件不生成内层maker的WFILE，直接从bin_orig加入ATF；恰好4 MiB仍走内层。[大小分支][production] [外层生成][maker]
5. 另外按存在的OTA XML分别生成 `ota_firmware.bin`、`ota_full.bin`等；不是把外层 `.fw`直接改名为OTA。[默认调用][main]

此默认路径**没有include `fw_maker_ext.cfg`**。
另一套 `generate_firmware()`调用 `generate_maker_ext_config()`；`generate_att_image()`也有条件读取扩展cfg，但本版main没有调用这两条方法。
这解释了为何不能把旧扩展配置中的helper选择直接并入当前默认生产配置。
这是固定源码调用关系，不是对未知CoMi官方构建链的观察。

## 四类产物不能互换

| 产物 | 来源与边界 | 后续用途 |
|---|---|---|
| 外层 `.fw`，magic `ACTTEST0` | ATF头、目录、CRC及嵌入文件；默认包含ATT目录中的 `upgrade.fw`，还可有测试资源/大文件 | 找生产包中的helper、配置与内层文件；不是BLE OTA或整片NOR镜像 |
| 内层 `upgrade.fw` | maker消费 `bin_orig/fw_maker.cfg`；两种封装、文件FAT/XOR分支已静态确认；DB转换未实现 | 需同包maker/匹配host与配置，不能假定其payload已经是物理NOR字节 |
| `*_raw.bin` | [generate_raw_image()][raw]以ff初始化disk_size，复制后处理bin中enable_raw且storage_id=0的文件到分区address | 是构建产物，不是实机备份；缺少不参与构建的个体配置/原有内容，不能替代全片读回 |
| `ota_*.bin`，AOTA或其包装 | 独立OTA打包器；已有[容器与实机验收研究](ota-container-contract.md)及 `inspect-ota` | 设备从host请求升级字节；不提供固件导出能力 |

原始镜像与内层生产包取自不同处理阶段，**把提取的明文system直接塞进raw布局，不能据此称为可刷镜像**。
转换、加密和启动授权仍需匹配目标；这里没有验证CoMi能接收任何生成文件。

### 内层maker：已解出的边界

[固定二进制、地址和字节证据](evidence/maker-package-static-2026-10-13.json)。
`PyMaker.pyo`为Python2.7，版本字符串`1.1.170825.1`；用uncompyle6 3.9.3静态反编译，关键封装分支再核对xdis字节码。
include/parser部分存在反编译控制流伪影，不作为完整可执行源码。
`libScript.so`、`libFileSystem.so`和`CompoundFW`含符号/DWARF；Astra独立核对原生读取路径。

| 格式 | 内容顺序 | 确认依据/限制 |
|---|---|---|
| legacy | 12 B `SFDNABDWFTCA`，4 B DB长度，DB，image | producer `CombineDbNImg`与两个native reader一致；magic不含NUL；整数为producer native signed int，在随包Linux上为LE32 |
| type100 | 12 B `100TMFWFSTCA`，4 B image长度，改写后的image，DB | `CombineDbNImg100`；两个已审legacy reader不接受此magic，不能混用解包路径 |
| CompoundFW另一格式 | 16 B magic `WFDNUOPMOCSTCA\0\0`，64 B头/64 B目录项，512 B对齐payload | 独立writer/DWARF观察；不是默认内层格式证明；MD5命名字段在已审writer中为零 |

`--type=100`强制第二种封装；AUTO只在输入BASEFILE被识别为type100时保留它。
`--mf 1`调用`Py_SetEncryptMode`，**不是**type100选择器。完整最终BASEFILE/配置仍须核对。
Linux `EncryptFw`调用`Py_106`；Windows分支直接复制DB，不能把某平台的转换推广到全部host。

legacy原生路径为`ExtraFirmware@11f44 → GetFirmwareBin@1245c → XYZ_108@1baa9 → SQLite`。
DB不是直接假定为明文SQLite；转换涉及2048 B包装、块重组及后续原语，本轮未实现完整解码。
外层16 B没有芯片/板型/version字段，不能从magic判断ATS3085L兼容性。

文件payload在独立FAT image中：`ReadFileInFW → FSOpen(type2) → FatReadEncryptFile → ReadBlock`。
逻辑文件分10 MiB块，物理名字为`\NAME~BLOCK`。
每块前15 B为`112233445566778899aabbccddeeff`时走`XYZ_121`；否则`XorEncrypt@26c72`逐字节XOR `38`，长度不变。
后者已独立实现并通过下面的真实随包样例核对；不代表CoMi NOR本身使用此编码。

### 随包样例：43个文件已恢复，但不是CoMi恢复包

bootloader maker目录保留明文`sample.db`和`temp.img`；[完整清单、hash与布局](evidence/maker-sample-2026-10-13.json)。
镜像实际6,635,520 B，FAT声明1 GiB，是裁剪的已用数据载体；所有引用cluster均在实际文件范围内，未补零伪造完整卷。

- 恢复43文件：`Launch.pyo`＋30个PE宿主模块＋12个目标配置/镜像。31项SCRIPT_PYD名称/长度全部匹配FileTable；该表File列为NULL，没有内容hash，清单匹配不冒充密码学验证。
- `Launch.pyo`反编译成功：`ProductionThread → Upgrade.UpgradeFW(port, log_file, script_dll, fw, int(device_index))`。[宿主续查](host-selection-followup.md#2026-10-13-recovered-maker-host-conditional-default-now-identified)确认port为预先构造的transport对象；样例USB＋指定DLL可追到CClassical、31 B USBC上传/切换包头，但没有CoMi选择依据。
- CHIP_NAME、CHIPID、BOARD_NAME、USB_ADFU_PROTOCOL_SWITCH、ADFU/ADFUS/ADFUS_U、STORAGE_ID_FILE、VID/PID等12张表全空；SDK_TYPE为USDK130、SCRIPT_TYPE为PYTHON_EXT。模板没有给出匹配CoMi的生效配置。
- 恢复XML注明LARK、2 MiB/11项；system@4000，CoMi为4 MiB/18项、recovery@4000/system@24000。**不同布局，不能作为目标恢复配方。**
- `adfus.bin`、`adfus_u.bin`、`boot_recovery.app`分别逐字节等于已审bootloader LARK参考文件；不是新发现的CoMi专用helper。6792 B stub仍缺其预期追加payload。
- 样例product.ini在前段写BOOT；与上述当前源码生成器的BOOT最后写入不同。旧样例不代表当前默认脚本，更不代表CoMi工厂流程。

可复现恢复（只读SDK；输出目录须不存在；不import/加载/运行任何恢复成员）：

```sh
uv run tools/inspect_maker_sample.py "$HOME/w/_tmp/lv_port_actions_technology" \
  --output artifacts/maker-sample-NEW
uv tool run uncompyle6 artifacts/maker-sample-NEW/Launch.pyo \
  > artifacts/maker-sample-NEW/Launch.bytecode-source.txt
objdump -d -C --start-address=0x26c72 --stop-address=0x26c93 \
  "$HOME/w/_tmp/lv_port_actions_technology/action_technology_sdk/bootloader/tools/utils/linux-x86_64/maker/libFileSystem.so"
```

提取器先核对三个源文件SHA，再检查双FAT一致性、LFN/cluster边界、43项数量、四个已恢复内容hash、31项清单与三份既有helper。
未知源或XYZ_121分支直接报错；没有把这个固定样例工具宣传为通用`.fw`解密器。
不要直接运行PyMaker或反编译文件：模块顶层加载共享库，清理函数还会删除同目录的sample.db/temp.db/temp.img。

### 后续实际官方type100包

[Actions测试盒官方包](actions-official-tester-2026-10-13.md)补上真实交付样本：外层ACTTEST0八成员CRC全通过，内层确为type100；FAT恢复56个文件，包装DB保留未解。
XML/参数CRC确认ATS3085C测试板16 MiB/21项，recovery/system地址4000/24000，但与CoMi板名/容量/分区不同。其product.ini有实际擦写/verify/最后写BOOT请求，不是只读备份流程。
同页DUT包为另一套外层头/目标helper架构，7个文件进入未实现XYZ_121分支并保留原始编码数据。不要把“已恢复FAT成员”说成“已解开全部生产数据库/文件内容”，也不要将两个官方包互拼。

### 外层格式已用原厂源码验证

未修改的 [build_atf_image.py][atf]对两个惰性输入执行成功：`payload.bin=616263`，`aligned.bin=bytes(range(256))*2`。
输出2048 B，SHA256 `041c59f53f31a2a74aece0a3f33c7d11f36f7b0618272eb1f1589a69eef3832f`。
独立读回核对（整数为little-endian）：

| 字段 | 固定生成器格式 |
|---|---|
| 头 | 本次2项输出为512 B；magic bytes0..7=`ACTTEST0`；CRC@8；count@12；version@16=`0x01000000`；total@20；body CRC@24 |
| 目录 | offset32，每项32 B：name12、reserved4、offset4、length4、reserved4、CRC4；源码输入上限15，但上限存在下述缺陷 |
| CRC范围 | header bytes12..511；body bytes512..end含padding；每文件CRC仅原始长度 |
| 对齐 | 每个文件补零；已经512 B对齐的输入仍多补512 B；实验中的第二文件位于1024、长度512，文件末尾另有512 B零 |

这是**外层封装实验**，未运行完整maker，没有生成官方CoMi固件；CRC不是签名或目标授权。
生成器按目录遍历顺序收集文件，没有建立可重现的完整包排序；不将本次固定输入hash推成所有生产包hash。

**15项边界缺陷已离线复现。** 14个单字节输入输出7680 B，声明总长/首文件偏移正确；15个输入声明8192 B却输出8704 B，首文件offset仍为512、该位置为零而非输入01。
原因是32+15×32恰好512，头padding公式再加512，却不调整目录/total；producer仍exit0，头/body CRC也仍匹配。
因此“工具成功＋CRC通过”不能替代长度/目录/文件内容核对；本轮记录问题，不修改上游生成器。

## 写入脚本为什么不能用于只读连接

默认 [product.ini生成器][production]写入 `adfu_switch`、波特率、`payload=32768`；按storage ID/地址排序。
第一遍遇BOOT请求 `serase <boot file_address> 16384 0`，其他DFU项请求 `swrite`；分存储初始化/verify/clear_history后，第二遍才写BOOT，最后 `disconnect reboot`。

**启动块写在最后，不代表可中断或自动恢复。**
若仅把本机boot地址0代入这条参考脚本的16 KiB擦除，范围将覆盖CoMi的两份boot和两份param（[实际ACPT](partition-readback.md)）。
未确认完整包和独立入口前，不能把生成脚本拿来“试连接”。`verify_fw`的名字也不证明设备已重新启动成功。
这只是host脚本请求；host内部执行/错误处理、CoMi实际接受行为仍未验证。

## LARK公共配置的适用边界

| 材料 | 已确认 | 不应推成 |
|---|---|---|
| 两树LARK `fw_product.cfg` | USB协议切换YES，adfus/adfus_u load01010000/run01010001；zephyr存储ID缓冲01022000，bootloader用01018000且另有RECOVERY_IM | 同名文件可跨树混用，或已知CoMi ROM USB identity/host enum |
| LARK `fw_maker_ext.cfg` | 另选 `mp_usb_lark.bin`，NANDID01008000；旧存储MFP、退出与工厂信息选项 | 当前默认生效配置、硬件长按reset，或个体配置保留保证 |
| `mp_usb_lark.bin` / `_old` | 均9972 B，hash不同；current SHA93871f6d…，old SHAa7400e56…；不是四种已知adfus别名；current配置还残留在LEOPARD扩展cfg | 新增已匹配CoMi下载工具；本轮不展开其指令/初始化审计 |
| LARK `common/firmware.xml` | 仅4项：boot@0、recovery@1000、system@20000、data@60000；无SYS_PARAM、无storage_id | 能直接输入当前生产器的完整配方；与实际18项布局相同 |

当前parser按SYS_PARAM文件生成参数；LARK旧表没有该项，且raw/production方法直接取storage_id。
缺项与实际recovery@4000/system@24000的差异均由固定文件可见；本轮不伪补字段、不以占位镜像声称完整打包成功。

## 下一份有用材料应包含什么

优先获取 **匹配ATS3085L/该板版本的完整生产目录或正式升级包**，而非孤立system.bin/helper。
至少保留：最终firmware.xml、fw_product/fwimage/fw_configuration及实际被include的扩展cfg、bootloader.ini、product.ini/生成配置、helper准确版本、boot/recovery/param与资源、所用host/tool版本。
对升级包先区分ATF、maker内部包、AOTA与raw；对生产目录核对覆盖顺序、目标地址及保留个体配置策略。
有这些材料后再决定应审计哪个下载器、如何读回和哪些内容能恢复。随包host模块可继续静态追选择条件；它们不能解除目标配置、数据线或独立退出的缺口。

[build]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/build.py#L456-L545
[snapshot]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L424-L445
[raw]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L872-L888
[production]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L1010-L1103
[maker]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L1105-L1131
[main]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_firmware.py#L1162-L1190
[atf]: https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/tools/build_atf_image.py
