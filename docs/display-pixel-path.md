# 实际像素提交与页转换

2026-10-12；C261CF0430 / FW010004。完整校验镜像离线分析，无设备I/O。[原始证据](evidence/display-pixels-analysis-2026-10-12.json)保存九个窗口及完整函数解码。

## 入口、回调与ABI边界

panel API+8=`10027a55`，提交入口为`10027a54..10027abe`；init把`10027e85`注册到data+6c，提交入口将同一data+6c传给调度helper。回调`10027e84..10027f8e`消费窗口和buffer状态。这补齐正常提交至像素转换的静态关联；没有实际提交图像。

参数行为：r0=device；r1/r2截成byte保存到data+1cb/+1cc；r3指向descriptor，读取其+8/+a的u16保存到data+1cd/+1ce；第五参数buffer经`100a0ada`转换后存data+1d0。后续行为支持这些值分别为x、y、宽、高。

入口仅比较descriptor的u16(+c)是否≥u16(+8)，失败返回−33；若busy bit(data+1c8 bit0)已置位，返回−16。否则设置busy、保存参数并调度，返回0。没有在完整入口中看到窗口界限、8行对齐、buffer大小或NULL检查。

**+c的字段身份只能暂记为stride/pitch候选。** 固定SDK当前[descriptor](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/zephyr/include/drivers/display.h#L199-L212)采用u32 pitch/width，与实际这里的u16读取不匹配。不可直接套当前SDK结构或pitch单位；实际转换明确只使用保存的宽度作为行跨度。

## 像素转换的确定行为

callback申请200 B临时buffer，首byte=`40`，先发送`AF`。令保存的宽度为W、y为Y、高为H、列为x：

- 页起点为`u8((Y >> 3) - 0x50)`，对正常Y=0..39即`B0..B4`；页终点为起点加`H >> 3`后截byte。
- 每页发送页命令，然后将保存的x加28，拆高/低nibble发送列命令。
- 每页内第c列读取8个little-endian u16：第k项地址为`buffer + 2 * (W * (page_row + k) + c)`，其中page_row初始0、每页加8。
- u16非零则置输出bit k；等于零则不置。输出是垂直8像素打包，低bit对应本页第一行。并未计算颜色亮度或灰度阈值。
- 每页发送`40`加W个数据byte到已定位的I2C data helper；最后释放临时buffer、清busy，并条件调用completion形状callback。

例如单列连续8个u16中仅第0、7项非零，对应输出byte应为`81`；这是静态算法推导，未以设备或指令仿真验证。

完整循环没有使用descriptor的+c字段。Y低3位没有用于像素移位，H低3位被丢弃；不应把任意非8行对齐窗口交给该路径。正常72列的数据消息73 B能容纳于200 B分配，但函数本身未检查W上界；也没有本地malloc失败检查。新实现应显式规定输入布局、范围和生命周期，不照搬缺失检查。

另一个API函数`10027a00..10027a26`只接受数值`10`，否则返回−134。固定SDK enum中`10`对应RGB565，结合u16采样支持RGB565输入的解释；确切旧ABI仍待核对，不能单凭该数值宣称完整像素格式兼容。

## Buffer地址转换：新线索，不是raw备份通道

`100a0ada..100a0af8`对输入地址作无内存访问的整数转换：

| 输入区间，末端不含 | 返回 |
|---|---|
| `10000000..14000000` | 输入+`04000000` |
| `18000000..1c000000` | 输入+`04000000` |
| 其他 | 0 |

这是实际firmware存在alias转换意图的证据，补充此前仅搜索literal的[映射缺口审计](mapping-candidate-audit.md)。函数没有查询物理Flash偏移、分区或MMU slot，也不读取返回地址；不能证明这些alias在当前硬件全部可读，更不能推出物理NOR连续映射。本轮未跟随任何转换结果。

## 后续

显示BSP已有提交入口、命令表和bit打包规则；仍缺GPIO电气极性、等待单位、I2C pinmux/速率及实屏验证。进一步研究应核对旧descriptor ABI与实际调用者，避免以当前SDK字段名解释不同布局。

## 实际指令仿真验收

新增独立PEP723脚本，无设备连接：

```sh
uv run tools/verify_display_pixels.py artifacts/mapped-system/mapped-system.bin
```

Unicorn 2.1.4 Thumb/MCLASS执行原始callback `10027e84..10027f8e`。脚本先要求整个镜像SHA256完全匹配；仅拦截allocator/free和已审计command/data helper，返回成功并记录参数，其他跳出callback的执行立即报错。RAM为仿真初始化值，绝不代表设备当前状态。每例100,000指令上限，未正常返回即失败。

手工golden与实际指令输出：[结果JSON](evidence/display-pixel-emulation-2026-10-12.json)。

| 图案/窗口 | 手工期望数据（含40控制byte） | 实际结果 |
|---|---|---|
| 2列×8行，第一列仅行0/7非零，第二列仅行1非零；x=3 | 40 81 02；页B0，列11/0F | 一致，231条含hook入口指令 |
| 1列×16行，仅行0/15非零；y=8 | 40 01、40 80；页B1/B2，列11/0C | 一致，268条 |
| 1列×9行，仅第9行非零；y=1 | 40 00；仅页B0，尾行被丢弃 | 一致，150条 |

同时核对200 B分配、对应释放及busy清零。期望字节来自手工图案，未调用复制转换算法的Python实现。这比只阅读反汇编多了一层可执行验证，但external helper成功、内存分配成功及无completion callback都是受控条件；不覆盖真实I2C、同步/调度、像素提交入口、地址alias、错误路径或屏幕亮暗。本篇此前单列81示例现有实际指令层面佐证，依然不是实机验收。
