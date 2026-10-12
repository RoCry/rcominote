# ACPT flags不能直接证明加密、签名或可恢复性

2026-10-12。离线审计固定SDK `26f51e584940d5b141cd1d09d2629d69b595f579`。CoMi实机事实仍为[CRC通过的ACPT表](partition-readback.md)；本轮无新增设备I/O、写入、启动模式切换或SDK工具执行。

## 三种标志，三个上下文

| 来源 | 位/值 | 实际源码用途 | 对CoMi不能推出什么 |
|---|---|---|---|
| ACPT `part.flag` | bit1=`2` | build工具从XML写入；OTA patch/param写入请求加密 | 不能单凭表证明Flash字节已加密，或定位密钥 |
| image header `ih_flags` | `IMAGE_F_ENCRYPTED=4` | `app_image_check`在特定header布局下调用security检查 | 不等于ACPT flags=2；未读实际header不能断言启用 |
| cache映射地址 | bit31 | `soc_memctrl_mapping(...,enable_crc)`为CRC映射置位 | 不可将此处bit31解释成写加密标志 |
| OTA写地址 | bit31 | patch/param加密请求传给storage write | 相同位在不同接口具有不同语义；不能照搬到mdb地址 |

以上逐行来源保存在[来源摘录与SHA256](evidence/boot-security-source-audit-2026-10-12.json)。源文件路径和行号见下文，均对应同一固定提交。

## flags=2与实际打包可能分离

`bootloader/tools/build_firmware.py:574–580`独立把XML `enable_encryption=true`写成flag2；`:405–425`先生成表/版本、保存original binaries，再仅在pre_encrypt且efuse文件存在时执行encrypt_files，缺文件只有全局强制开关为真才报错。该版本默认强制开关False。

因此**存在源码允许的“表声明加密、该工具阶段未加密”路径**。并非证明CoMi走了这个路径。`:496–515`真正的加密委托外部fw2x、encrypt_fw和efuse文件，本次没有运行或取得CoMi匹配输入。工具生成table version0100（`:548–559`），实机是0101；再次说明参考SDK不等于厂商构建版本。

## CRC转换、写加密与签名独立

- `framework/ota/libota/ota_file_patch.c:142–171`：CRC模式把32B payload扩为34B，计算CRC16并追加两字节；加密模式另把写地址bit31置1。两标志分别设置，不能把缓存视图直接当原始Flash字节。
- `framework/ota/libota/ota_upgrade.c:462–475`：old mapping依CRC标志创建；patch配置分别传CRC和encrypt。
- 同文件`:1156–1184`：param更新路径依据ACPT加密标志置写地址bit31，并要求长度32B对齐。该路径有擦除/写入，本研究未执行。
- `bootloader/soc/arm/actions/leopard/soc_boot.c:174–207`：boot_to_part按type/mirror选择entry，把file_offset写入system_phy_addr，再依flashid选择启动实现；这里传递的开关是CRC位，不是ACPT加密位。

## 签名检查受构建条件控制

`bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c:229–255`：检查header校验和；特定run_off且image flag4时走image_security_data_check，否则走镜像校验和。

`soc_boot.c:79–166`：CONFIG_SOC_SIGN_ENABLE下查RSA2048_PSS TLV、检查key存在，再验证签名；未启用则security函数直接return0。此外源码在CONFIG_FLASH_LOAD_OFFSET==0时undef签名开关。该配置差异无法从当前ACPT推出。函数源码里提到ROM API不代表实机实际使用同一ROM函数；当前参考实现调用verify_signature。

结论：尚不能判断CoMi接受未签名自写镜像，也不能判断它拒绝。需要实机header、实际boot检查分支或官方构建/恢复资料。

## recovery区不等于救砖验收

`bootloader/application/ota_app/src/ota_recovery/recovery_main.c:296–332`：参考恢复流程先检查升级进行状态；无任务时跳过；temp-part/SD后端受配置控制，初始化失败也退出；需要ota_upgrade_check处理升级数据。

`bootloader/application/ota_app/src/main.c:21–82`：GPIO/TXRX ADFU检查受配置控制；存在boot失败→OTA、OTA失败→ADFU的源码路径。没有证明CoMi的按键/引脚、构建配置、ROM入口、退出方法或USB枚举。不能把已读`fw0_rec`配置或正常App的`reboot adfu`帮助视为独立恢复保证。

## 下一份决定性证据

1. 实际启动信息引用与镜像头，核对当前system/param物理偏移、镜像选择、header flags。
2. 实际映射/原始读取实现，验证是否去CRC、解密、重定位；选已知内容做原始与映射视图对照后才扩展备份。
3. boot/recovery实际检查流程与匹配官方镜像；验证脱离当前应用仍可进入、退出并恢复的通道。

现有CLI仍只有查询、固定映射读回和离线分析；无整片备份/烧录能力。本轮结论是缩小未知项和排除错误推论，未证明上述三点已完成。
