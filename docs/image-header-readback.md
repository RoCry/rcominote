# 当前映射镜像头：ACTH校验和与向量一致

2026-10-12，C261CF0430 / FW010004。完整512 B头部及8 B向量两次独立一致；头部32位加法校验通过。当前shell-code链3571 B，累计7455不同映射字节。无Flash写入、复位或模式切换。

## 读取依据与范围

已有多个实机代码地址位于100xxxxx，完整ACPT系统区与boot-info候选的system/nor offset同为24000。固定SDK APP_RUN_ADDR及app_image_check提供映射基址10000000候选。此次**不是从实际BL推得该基址**，而是在这些交叉证据下限定读取64 B，见有效magic及header_size后才读取声明的剩余448 B和后续向量8 B。

相比早期仅有SDK基址，这次增加了实际分区/启动信息关联；仍不以此证明整个cache窗口或raw Flash可读。没有读取MMIO、uncached窗口，也没有对未知区间扫描。

## 实读字段

| 字段 | 值 |
|---|---|
| mapped header | `10000000` |
| magic0 / magic1 | `48544341 / 41435448`（ACTH/HTCA字节） |
| SDK load_addr field | `1002d819`；不当作本次映射基址 |
| name | `b` |
| entry | `1002d819` |
| header size | 512 (`200`) |
| image size | 927120 (`e2590`) |
| image checksum field | `4e7a894a`，**正文尚未校验** |
| header checksum field | `07da0708` |
| protected TLV / TLV size | 0 / 0 |
| version / flags | 0 / 0 |
| IC-type bytes / storage-type | 全0 / 0；不凭它识别芯片 |
| vector at10000200 | SP=`01002b40`，reset=`1002d819` |

全部128个little-endian uint32 header words求和模2^32等于ffffffff，符合SDK app_image_check。reset向量为Thumb地址，与header entry相等。header SHA256=`911454d9fa79203ffa52b8af6073fd3f4a1106febb4459c0f181ea43e6271bc5`。

头部声明正文范围`10000200..100e2790`，当前仅取其中向量8 B和此前零散代码。header+body总长927632 B；此长度小于ACPT fw0_sys的1a5000容量，但两者的物理映射仍需证明。

## 安全标志的实机结论

当前头部flags=0、TLV长度0；没有置SDK的image flag4。它与ACPT中fw0_sys flags=2并存，实证两类标志不能混为一谈。**不等于整条启动链无签名/ROM安全限制**，也不证明原始Flash字节未加密。映射视图可能经过硬件处理；尚无原始视图对照。

## 下一步

镜像头给出了有界正文和校验oracle：可研究分块读取、丢行检测、断点续读，最终以正文加法校验字段验证映射镜像导出。先测可靠吞吐与输出边界，不把现有16 B逐命令模式直接扩展成无校验长任务。

即使正文导出成功，也只覆盖当前映射system镜像；boot/recovery/参数/NVRAM/资源及设备个体数据仍未完整备份。当前CLI新增的是头部验证报告，尚无完整镜像导出或原始Flash备份/烧录功能。

## 证据与复现

[首次](evidence/image-header-first-2026-10-12.json)、[重读](evidence/image-header-second-2026-10-12.json)、[分析](evidence/image-header-analysis-2026-10-12.json)、[结束状态](evidence/image-header-final-state-2026-10-12.json)。设备结束idle/FW010004。80项测试、24项子测试与wheel/sdist通过。

CLI仍为`uv run comi diag capture shell-code --out ...`和`uv run comi diag compare-references A B --shell --out ...`；报告新增mapped_image_header，长度/magic/头部checksum/vector不一致立即报错，image_checksum_verified保持false。

固定源码：[image_head布局](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/soc_boot.h#L51-L70)、[头部/向量/正文检查](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/bootloader/soc/arm/actions/leopard/boot/soc_boot_priv.c#L188-L255)。
