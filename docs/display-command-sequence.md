# 实际屏幕命令与复位顺序

2026-10-12；C261CF0430 / FW010004。承接[板级定位](display-board-evidence.md)，完整校验系统映射镜像离线追踪。无设备I/O。[证据JSON](evidence/display-sequence-analysis-2026-10-12.json)保留九个原始窗口、SHA256及五个完整函数的Thumb/MCLASS解码。

## Resume callback与28字节表

panel initializer保存的Thumb callback `10027d01`对应`10027d00..10027d98`。其literal引用同一panel data=`180056f0`，日志字符串为`panel resuming`、`panel active`；命令表日志标签另为`ch1115_lcd_init`。这是静态回调内容，不证明本次运行已调度执行。

按实际指令顺序：

1. 清data+1c8 bit0、置data+58为0。
2. 对data+50设备调用GPIO helper，pin24，逻辑value=1。
3. 对data+54设备调用相同helper，pin25，逻辑value=1。
4. 等待helper `1009c02c`参数r0=10、r1=0。
5. GPIO pin24，逻辑value=0。
6. 同一等待helper参数r0=120、r1=0。
7. 从`100c7b6e`开始逐byte读取28项；每项调用`10027ad0`，device取panel data首word。因此这里补齐了此前缺失的实际I2C_0 → command helper调用关系。

```text
AE 0C 11 40 A4 A7 D5 F0 A8 27 D3 00 20 02
A1 C8 DA 12 AD 30 81 1F D9 1F DB 20 8D 14
```

循环counter从0开始，每次加1，比较`1c`退出；不会发送其后字符串字节。命令helper逐项构造`00,command`、len2、flags2、address3c。返回值在该循环被忽略；日志`panel active`不证明全部I2C写成功。

随后调用`10027c88`，再调用另一helper（r0=data+4内容、r1=6）。后者本轮未展开，不命名其用途。

## GPIO数值不是直接电平

完整GPIO helper `100a2012..100a2032`把pin转换为bitmask，读取device data首word：若相应bit已置位，先将value异或1，再按结果调用API+0c或API+10。因而上面的1/0是逻辑值，不能直接说reset引脚实际先高后低。需要继续审计GPIO配置flag与driver、或电气测量；等待参数的时间单位亦未核实。

## 条件发送AF

`10027c88..10027cf2`在data+58≤1且data+1c8 bit1未置位时调用同步helper、置bit1，并向同一command helper传`AF`；随后调用定时相关形状helper，stack参数含100。若bit1已置位则直接返回0；data+58>1返回−1。此处不把未展开helper参数换算成毫秒，也不声称显示已经点亮。

## 独立fill callback

另一注册callback `10027e0d`对应完整函数`10027e0c..10027e7e`。它申请200 B buffer，循环五页，发送页字节`B0..B4`；列命令由`data+1cb`的byte加28后拆成高/低nibble。每页数据是控制byte`40`加72个`FF`，经`10027dc0`发送73 B到地址3c，末尾释放buffer。

这进一步支持72列、5组8-bit页的显示组织，但尚不能把fill callback当作正常framebuffer提交路径，也不能确定FF在屏幕上的亮暗效果。列偏移公式已知，当前data+1cb未知，不能宣称固定列起点28。分配返回值没有本地NULL检查，I2C返回值也未用于终止循环；这些是原厂静态路径的限制，不应照搬成新驱动的错误处理。

## 仍缺什么

已有可复核命令表、逻辑复位顺序、I2C控制byte和页/列传输形状。仍需GPIO极性与pad映射、等待单位、I2C时钟/pinmux、正常像素转换/窗口约束、控制器命令语义对照及实屏验证。此次没有修改屏幕、烧录或验证恢复。
