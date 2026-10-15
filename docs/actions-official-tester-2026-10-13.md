# Actions官方测试盒材料：取得、差异与CoMi边界

2026-10-13。[官方入口](https://tester.actions-semi.com/all/latest/download/index.html)。
**首次取得具备完整恢复镜像、生产脚本和原生板级设计的官方LARK测试盒包；仍不是CoMi恢复包或完整BSP。**
先保存原始下载与SHA256，再做静态解包/比对；Astra独立分析helper/recovery，硬件支线解析BOM/PADS。
没有运行厂商程序、加载DLL、上传helper、操作设备或写Flash。

## 原始材料与复现

原始文件和HTTP收据：`artifacts/actions-official-20261013/`；[下载/原始成员/说明页证据](evidence/actions-official-acquisition-2026-10-13.json)。
保留首次下载时间、最终URL、长度、ETag和Last-Modified。服务器日期只作响应元数据，不当作固件构建时间。

| 官方原始包 | 字节数 | SHA256 |
|---|---:|---|
| [测试盒v0.0.3-b6fdbfea-230828][tester] | 1874160 | `bbe5d8b5b8db020fd70d05a3e57b51de6566656de29f27e653c269b2383c5edb` |
| [测试板V1.3_20230822][hardware] | 290512 | `2d14cf0cdc8155f712c62e998c7b6d03149c99ed70e137584e570e43c650bf3f` |
| [DUT v0.0.3-5cfeced9-20230828][dut] | 1784932 | `fb6a2944016644b58b0c878a05afe82959f1a721ff0f06a5e0346bed6650ed65` |

7z中取得两个FW及SCH/PCB/BOM共5个原始成员，分别固定hash。
测试盒FW：7574016 B，SHA256 `e6eec01b76b2b9fcfd8e05b3636a582e051a537c2d853cf2737dc1ac1ff49bfe`。
DUT FW：7596032 B，SHA256 `7acffc891f8df3d2e6b74b182fa0842ab4850279ad929c7b5b542c844a93473e`。

```sh
# 下载固定原始包，校验SHA，再静态解包；输出目录须不存在。
uv run tools/acquire_actions_tester.py artifacts/actions-official-NEW
# 完全离线复现首次保存的材料；仍核对所有固定SHA。
uv run tools/acquire_actions_tester.py artifacts/actions-official-replay-NEW \
  --existing artifacts/actions-official-20261013
```

工具保存原始文件、收据、archive成员、外层文件、原始type100 image/DB和FAT输出。
同一FAT读取代码也重新核对旧SDK样例：原有输出不变。首次独立解包与新工具的108个FAT输出逐字节一致；PE32/Python2.7签名核对通过。
DB包装未解密/查询；XYZ_121文件以`.encoded`留存并明确标记，不能当作解出的配置。

## 外层和内层：核查后的准确结果

[目录、全部hash/CRC、FAT块与布局](evidence/actions-official-packages-2026-10-13.json)。
实下载magic为 **`ACTTEST0`，末尾数字0，非Q**。

| 项目 | 测试盒 | DUT |
|---|---|---|
| 外层成员 | 8 | 6 |
| 头/正文CRC、声明总长 | 全通过 | 另一种已观察头布局；offset8为version，16..31为零，不报告现代格式CRC/总长通过 |
| 成员CRC | 全部8项通过 | 5项通过；config.txt存储CRC为零、计算值不同，明确未验证 |
| 内层 | type100 upgrade.fw | type100 UPGRADE.FW |
| FAT输出 | 56个，全部XOR38分支 | 52个；45个XOR38、7个XYZ_121原始编码块 |
| 宿主文件 | Launch＋28个PE模块 | Launch＋28个PE模块 |

CRC覆盖只证明一致性，不是签名、可信启动或目标授权。
两包均保留image后方的包装DB；没有把FAT文件直接冒充整个生产数据库。
FAT声明卷大小1 GiB，是maker载体属性，**不等于目标NOR容量**；目标容量来自XML/板级材料。

## 测试盒新增价值：完整但不同目标的LARK参考

XML标记LARK、`disk_size=0x1000000`，21项。
param.bin的ACPT和FVER CRC独立通过：板名 **`ats3085c_bt_tester_128m`**，版本`1.00_2308281729`。
这是包内配置身份，非对任何设备的现场识别。

| 字段 | 官方测试盒包 | 实际CoMi |
|---|---|---|
| 板名 | ats3085c_bt_tester_128m | ats3085l_dvb_watch_ext_nor_max |
| NOR配置 | 16 MiB/21项 | 4 MiB/18项 |
| recovery/system位置 | 4000/24000 | 4000/24000 |
| recovery文件 | 71680 B，2fef3528… | 63288 B，19625b7b… |

**前段地址相同提供比较价值，容量/分区/板名不同排除直接恢复。**
包内有boot、param、recovery、app、资源和product.ini；app.bin以向量表开头，不能从其明文字节直接推定最终Flash表示。
product.ini列出擦除boot、写param/recovery/app/资源、verify_fw，最后写mbrec并重启。
它是明确的写入脚本，不能当作只读连接或全片备份工具。
`nand_id.bin`仅8 B ASCII `12345678`；文件名不证明它包含有效CoMi Flash识别数据。
E_CHECK仍为512 B `empty`样例，不构成新救援入口。

### helper与恢复代码的实质差异

[完整差异清单、原始指令窗口与54文件SDK基线](evidence/actions-official-lineage-2026-10-13.json)。
SDK固定`26f51e584940d5b141cd1d09d2629d69b595f579`；只在明确列出的54份helper/boot材料中作精确hash比较。

| 项目 | 新取得测试盒包 | 已持有SDK Zephyr LARK |
|---|---|---|
| adfus.bin | 46560 B，SHA5e03e180… | 47608 B，SHAee57bd89… |
| adfus_u.bin | 47724 B，SHAc76a93eb… | 48792 B，SHA0aefabef… |
| 构建字符串 | Feb17 2023 08:42:59 | Apr24 2023 15:17:38 |

两份helper入口为ARM Thumb，内部base01010000；不是54份基线中任何文件的精确副本。
**新取得版本不等于更新版本。** 完整初始化/退出链尚未重审。
USB描述符与既有SDK逐字节相同：10d6:10d6，主描述符81 IN/01 OUT，other-speed为01 OUT/82 IN；端点差异仍存在，且不是CoMi ROM实测描述符。
新helper保留调用写状态例程的路径，例程36 B与SDK匹配；不能把它提升为只读备份helper，也没有现场NOR写入观察。

完整recovery中两段与实际CoMi逐字节相同：unmap16 B、sum32 24 B。
中央ACTH checker为248 B，实际CoMi为268 B；均可见magic、奇数入口范围、大小与加法校验结构，但完整checker、映射和handoff字节不同。
这提供了可对照的完整官方恢复实现，**不证明启动授权/交接行为等价**，不能替换CoMi recovery。

两包宿主文件均与旧SDK样例存在版本差异；只有c_math_lib.pyd同时匹配两包及旧样例。
测试盒三个重点模块标识Cython0.29.28，旧样例为0.29.14。编译器/文件hash差异不证明协议语义改变；本轮未反编译所有新宿主分支，不移用旧地址/选择结论。

## DUT必须单独处理

官网将DUT包放在US301B栏目。adfus_c.bin为16472 B，首64 B连贯解出MIPS32小端初始化指令，**不是CoMi Cortex-M4 helper**。
boot.bin以AcP2相关头开始，recover.app为ActsSysP，与测试盒ACTH材料不同；不据一个helper推断包内每个成员的ISA。
7个XYZ_121编码成员保留原始字节；没有绕过或猜补转换。
DUT包可作为另一套厂商生产工具/容器的参考，不能与测试盒LARK文件拼成CoMi固件。

## 硬件资料：官方参考，未解析CoMi接线

[原始成员、精确BOM单元格、PADS类型记录与原始字节](evidence/actions-official-hardware-2026-10-13.json)。

| 原始位置 | 已核实内容 |
|---|---|
| BOM Sheet1 B33..E33 | U2＝ATS3085C，QFNWB68 |
| BOM Sheet1 B27..E27 | UN1＝GD25Q128EWIG，SOIC8-W |
| BOM Sheet1 B77..E78 | JU2＝minUSB；J11＝USB-C连接器 |
| BOM Sheet1 D2 | 仍写V1.2_20230705；与文件名V1.3_20230822不一致 |
| SCH类型记录130/132 | USB_DM/USB_DP，记录位置29708/29884 |

SCH为PADS Logic binary v13；按固定[KiCad schema][kicad]核对20个目录项、5张图纸边界和footer，有限解析153条全局网络及placement reference。
PCB为PADS binary0x2026；固定[padsts parser][padsts]读取74项目录，保留未知区，重新序列化逐字节相同。
无损往返不证明电气解析完整；尚未建立芯片脚号、USB/ADFU键连线、复位或SWD拓扑。
板级参考不能外推CoMi磁吸触点、电源控制或实体SoC封装。BOM修订一致性也未解决。
完整复现脚本与原始解析输出保留在`artifacts/actions-official-20261013/hardware/`。

## 官方说明补齐了什么

[测试盒自身更新说明][tester-upgrade]明确要求USB连PC、按专用ADFU键开机、配置工具选择ADFU设备后下载。
[给DUT更新的说明][dut-upgrade]另走测试盒SD卡OTA文件流程；导出的是配置工具里的固件材料，不构成设备Flash导出接口证明。
页面对DUT OTA可靠性的描述属于该产品流程，不能视为CoMi已具备可恢复升级的证明。
说明页原始HTML、SHA和HTTP元数据已保存；没有对设备执行这些步骤。

## 当前可用结论与下一步

新增可用材料：官方完整LARK恢复实现、不同helper/宿主版本、有效包内板型/布局身份、原生测试板资料，以及两种官方升级流程。
仍缺：匹配CoMi的BSP/量产包、完整原始NOR备份、实际ROM传输与独立恢复验收；磁吸线数据接线/独立退出也未因此确认。

有价值的下一步是用**实际CoMi镜像作主证据**，针对完整官方recovery或新host中一个会改变进入/备份/退出决策的差异继续核对；不因地址/系列接近就上传参考helper或擦写测试盒镜像。

[tester]: https://tester.actions-semi.com/all/latest/download/files/ats3085c_bt_tester_128m-v0.0.3-b6fdbfea-230828.7z
[hardware]: https://tester.actions-semi.com/all/latest/download/files/ATS3085C_Production_Test_Board_V1.3_20230822.7z
[dut]: https://tester.actions-semi.com/all/latest/download/files/dut-test-fw-v0.0.3-5cfeced9-20230828.7z
[tester-upgrade]: https://tester.actions-semi.com/all/latest/bt-tester/tester-upgrade.html
[dut-upgrade]: https://tester.actions-semi.com/all/latest/bt-tester/function/fw_upgrade.html
[kicad]: https://github.com/KiCad/kicad-source-mirror/tree/ac8691a64afa0a78d04f0073e82896bcdec82657/eeschema/sch_io/pads
[padsts]: https://github.com/tscircuit/padsts/tree/a01e30148f8ce919773489e6cdb9ac852f728bb4
