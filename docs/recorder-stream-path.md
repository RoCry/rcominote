# 编码输出：文件分支与异步stream分支

2026-10-12；FW010004完整校验镜像离线追踪，无设备I/O。[证据JSON](evidence/recorder-stream-path-2026-10-12.json)保留实际ops、函数及literal；通用stream写入函数只保留关键dispatch片段。

**capture output stream不是文件stream本身：其write handler先把输入交给ring helper，再同步转交文件分支；另一个线程从ring取数据发往运行时stream。** 未证明两个分支都成功，也尚未把第二分支定位到实际BLE characteristic。

## 对象关系

前篇[参数生产者](recorder-media-config.md)调用`1000df7c`。该getter返回全局`1800be84`中的对象；完整初始化`1000df88..1000dfce`分配4 B对象，用ops=`100baa18`调用stream factory并将返回stream存对象首word。参数生产者把这个stream放到capture output字段。

另一条`1005232c` factory使用ops=`100bcc6c`及传入路径，结果被保存到同一producer使用的全局`1800be74+4`，属于不同stream。其write slot+1c=`10051f21`，完整handler的断言literal明确为`fstream_write`及`framework/base/utils/stream/fstream.c`；成功路径调用底层`1002eba8`并更新写偏移。

## Write的两次交付

首stream ops+1c=`1009ef97`，实际函数`1009ef96..1009efb8`：

1. stream+54取得私有状态；NULL或len0则返回0。
2. 以状态+4、原buffer和原len调用`100ad56c`，与初始化/消费路径共同支持ring enqueue语义；helper本体尚未展开。
3. 不检查其返回值，恢复原buffer/len，尾调用`1000d9d4`。
4. `1000d9d4`取全局1800be74+4的文件stream，非NULL则调用通用stream write `100517fc`，否则返回−1。
5. 通用write在`10051860..1005186c`通过stream+50 ops的+1c分派，落到上述fstream_write。

因此该handler最终返回值来自同步文件分支，而非ring enqueue。即使文件写成功，也不能由这个返回值断言异步分支已完整接收；反之ring接收后文件分支仍可能失败。没有模拟buffer溢出或底层写失败，本段仅描述实际控制流。

## 异步消费者

stream open `1000def4..1000df62`创建线程，entry=`1000ddb9`，日志/线程名literal=`opus_ringbuf`。完整消费者`1000ddb8..1000de86`：

- 检查私有状态首word作为运行标志；ring的两个counter相等则等待参数10。
- 非空时，以helper `1006be24`返回值计算`u16((value−3)*2)`，再与ring可用量取较小者；不能在未展开helper前直接给这个值命名为MTU。
- 从ring helper `100ad55c`取数据，再检查另一个运行时对象+150的stream pointer；非NULL且运行标志仍置位，调用`10051980`，额外参数1。
- 取数据发生在target NULL检查之前；NULL路径可能消费但不发送。未跟随所有同步行为，不能由此定量断言实机丢失量。

该目标有前篇`ble stream open failed`上下文，但其对象生产者/ops尚未解析。因此暂称“异步stream分支”，不声称已确认BLE后端、加密、分包或送达。

## 编解码器名称与实际选择

实际`opus_ringbuf`/`opus_stream_init`标签不能用于判定编码格式。[后续实际分派证据](recorder-codec-dispatch.md)确认：该format1编码配置选中带`mp3e`标识的硬件记录及`aeRECORD.dsp`，进入DSP路径，与固定SDK的MP3编码配置一致。

静态选择已得到实际codec表支持；DSP加载/执行及输出文件帧仍未由本轮验证，也不推广到所有模式。
