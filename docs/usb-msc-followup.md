# USB MSC线索的实际覆盖边界

2026-10-12，完整FW010004 system映射镜像离线核查。[搜索与字节证据](evidence/usb-msc-followup-2026-10-12.json)。无主机磁盘访问、USB切换或设备I/O。

**实际存在MSC弹出状态查询，但本轮未找到MSC初始化→描述符→磁盘后端的完整链。** 不能把`mass_storage`或`usb msc ejected`字符串当成可用的启动NOR导出能力。

## 正面证据仅到状态查询

USB hotplug片段`10054590..100545bc`调用`1009a40c`，返回非零时设置退出相关状态并记录`usb msc ejected`。

完整`1009a40c..1009a416`读取global=`18045244`的一个byte，提取bit2后返回。固定SDK [MSC_EJECTED与getter](https://github.com/lvgl/lv_port_actions_technology/blob/26f51e584940d5b141cd1d09d2629d69b595f579/action_technology_sdk/framework/usb/class/mass_storage.c#L110-L145)与该形状一致。没有实读global值，没有取得LUN、disk number、SD/NOR读回callback。

因此此getter的存在不能证明初始化已链接、运行或成功；也不能推断状态恒定或MSC必然不存在。

## 限定搜索

在927632 B完整已校验镜像中执行两类搜索：

1. 每byte检查18 B device descriptor紧接9 B configuration header，wTotalLength介于9..4096，按bLength遍历须正好结束。仅命中`100dcd4a`和`100dcda7`，均为已确认的[CDC配置](usb-cdc-config.md)，VID/PID10d6:b00a、configuration75 B。
2. 对镜像正文所有半字对齐Thumb BL/B.W候选解码，查直接目标`1009a200`（已验证描述符注册helper）。仅命中`1009a67a`，即CDC初始化。

没有命中其他候选不等于不存在：描述符可能分离存放、动态构造、编码或来自其他镜像；调用可能间接、内联或使用其他注册入口。未把数据区误解码当新增函数证据，也未根据阴性搜索修改功能判断。

## 对不拆机备份的影响

目前USB正面证据是[受测试模式控制的CDC](usb-cdc-startup.md)，其[已审计命令](usb-cdc-command-map.md)包含身份配置与SD格式化，没有已建立的固件/DSP导出接口。MSC后端仍未知，不能假定它暴露NOR或为整片备份提供捷径。

下一份能改变判断的证据应是实际MSC初始化/存储callback、独立取得的匹配官方镜像，或真实且可归属的USB描述符。继续重复扫描相同字符串不会解决这些缺口。
