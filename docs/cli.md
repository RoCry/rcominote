# CoMi uv CLI

安装依赖与入口：

```sh
uv sync --all-extras
uv run comi --help
```

Python≥3.13；依赖与工具版本固定在 `uv.lock`。正式包 `src/rcominote/`，在仓库根目录运行 `uv run comi`，由uv管理项目环境。不依赖 rlcdv 或旧 `tools/comi.py`。

设备命令默认按广告序列号选择自有 C261CF0430；Boyi 操作连接后再次核对 GET_SERIAL。其他自有设备通过各命令 `--serial SERIAL` 选择。诊断 code profile 仅支持当前有证据的设备/入口，不能移植到其他设备盲读。

## 发现与状态

```sh
uv run comi doctor             # 离线环境与能力边界；不扫描
uv run comi capabilities
uv run comi scan --seconds 8   # 被动扫描
uv run comi info --out artifacts/info.json
uv run comi gatt --out artifacts/gatt.json
uv run comi recording-info
uv run comi settings show
```

成功结果通常是 JSON；参数错误非零退出，设备/协议失败向 stderr 输出 JSON 错误。证据文件拒绝覆盖。macOS 的宿主终端需有蓝牙权限；官方 App 先断开。Linux 设备访问依赖本机 BlueZ/适配器/权限；SSH 不会把 Mac 的 USB/BLE 自动转发过去。`doctor`不把“依赖已安装”说成“蓝牙权限已通过”。

## 录音与导出

```sh
uv run comi record start
uv run comi record pause
uv run comi record resume
uv run comi record stop
uv run comi files
uv run comi download NAME_FROM_FILES --out artifacts/recordings
uv run comi download NAME_FROM_FILES --offset 17 --out artifacts/recording-ranges
uv run comi sync --out artifacts/recordings
uv run comi set-time
```

录音操作检查起始状态、响应格式及操作后的实际状态；不接受错误状态上的重复操作。`set-time`使用主机本地时间，现有协议没有已知时钟getter，因此只报告匹配响应和请求时间，不宣称读回成功。

下载要求声明长度、完整字节、结束帧，且和文件列表长度一致；超量、短读、断连、错误状态或无声明立即失败。临时`.part`成功后以不覆盖方式原子发布，输出SHA-256。失败清理临时文件，不能把半个MP3当成功。

`sync`跳过已存在同大小的普通文件，明确标注 `verification=size_only`，不能当成和设备内容哈希一致。大小不同或符号链接拒绝覆盖；选择新目录自行核对。设备未提供文件hash，CLI hash只标识本次收到的字节。

录音测试产生的原文件不会自动删除；没有实现设备删除/格式化/解绑命令。

## 设置

```sh
uv run comi settings set noise 8        # 0..16
uv run comi settings set usb on         # on/off
uv run comi settings set indicator off
uv run comi settings set voice off
uv run comi settings set backlight on
uv run comi settings set segment 1h     # 30m/1h/2h/3h
```

所有setter均显式选择；已有值相同就返回 `already_matches`，不重复发送。设备报告null时拒绝setter。设置后的 `GET_DEVICE_INFO` 必须等于请求值，收到ACK本身不算成功。失败不会自动猜测/追加其他命令。

当前实机确认noise可写并读回；其他setter来自固定官方App源码，设备支持仍以读回为准。segment四档来自App标签映射，不是已证明的固件边界。当前设备indicator/voice报告null，backlight报告false。精确协议依据见 [能力规格](cli-capabilities.md)。

## 日志、固定诊断与代码样本

```sh
uv run comi diag probe --out artifacts/prepare.json
uv run comi diag capture version --out artifacts/version.json
uv run comi diag capture platform --out artifacts/platform.json
uv run comi diag capture commands --out artifacts/commands.json
uv run comi diag capture kernel --out artifacts/kernel.json
uv run comi diag capture stacks --out artifacts/stacks.json
uv run comi diag capture code --out artifacts/code1.json
uv run comi diag capture code --out artifacts/code2.json
uv run comi diag compare-code artifacts/code1.json artifacts/code2.json --out artifacts/analysis.json
uv run comi diag text artifacts/platform.json
```

其他profile：`logs` 默认实时日志、`threads` 详细线程表、`nor-header` NOR头读取尝试。`threads`已观察到设备端长输出截断；`nor-header`已知没有数据正文，不是备份工具。所有日志会话限1–30秒、默认5秒，结束发送STOP并等待结束帧；`transport_ok`表示传输完整，**不代表命令成功或正文完整**。固定代码读取另校验每个请求的数据行；缺行、短行、重复行均使`ok=false`并非零退出。

`code-literals`在核对入口指令后读取其两个常量（8 B）；`code-references`进一步读取固定引用，总计69 B、五个非连续位置。两次采集可用`diag compare-references FIRST SECOND --out REPORT`离线比较。[证据与推导](code-reference-followup.md)。

`vendor-code`核对本次会话的`vendor`与`vendor_read`入口，读取固定380 B：两个入口、后者至已证实常量池前的连续代码及六个常量。常量/后续代码读取前还要求入口字节精确吻合。两次采集用`diag compare-references FIRST SECOND --vendor --out REPORT`比较；连续Thumb代码合并后解码，避免16 B传输行拆断32位指令。[实机代码分析](vendor-code-readback.md)。

`vendor-handler`读取固定580 B，含32 B已有调用链校验、实际命令分发表和`0x3a`处理函数/引用。逐层核对入口、BL、表尾和literal；每四行刷出并等待正文，失败停止后续读取。两份捕获用`diag compare-references FIRST SECOND --handler --out REPORT`比较，输出58项分发表，明确将TBB表与literal排除出代码。[分发表及未知边界](vendor-dispatch-followup.md)。不发送`0x3a`或其他新增应用命令。`platform`增加固定只读`BT_NAME`查询，与`BT_LE_NAME`分别报告。

code只读固定映射地址的16 B，并在同会话核对当前logsrv入口；不接受任意地址、长度或shell文本。离线比较拒绝重复采集身份（包括复制同一文件），要求两次样本一致，返回解码与hash，不执行机器码。此能力不等于完整flash dump、板级适配或可恢复备份。

## 一键只读验收

```sh
uv run comi verify --code --out artifacts/verification-NEW
```

新建独立目录，依次保存身份/状态、GATT、平台诊断、可选两份code与离线比较、结束状态和manifest。要求开始idle；不会开启录音、改设置、重启或刷写。失败仍保留已取得的证据并非零退出。code可选且限定FW1.0.4。

USB主机描述符：`uv run comi usb snapshot --out artifacts/usb.json`（macOS）；`uv run comi usb diff BEFORE AFTER`离线比较。`snapshot`不会打开设备端点。

## 开发与独立分发

```sh
just check       # 格式/lint/脚本语法、离线真实帧和故障序列测试
uv build         # wheel + source distribution
```

参考板SDK构建仍是独立研究工具，仅Linux x86_64。准备脚本默认下载固定SDK和工具链；构建脚本显式接受`--sdk`、`--toolchain`、`--out`、`--jobs`：

```sh
bash tools/setup_sdk.sh
uv run --locked tools/build_sdk.py \
  --sdk "$HOME/w/_tmp/lv_port_actions_technology" \
  --toolchain "$HOME/.cache/rcominote/gcc-arm-none-eabi-10.3-2021.10" \
  --out artifacts/sdk-build --jobs 4
```

APK固定样本提取仍用`uv run tools/apk_evidence.py ...`。这些研究脚本不参与设备CLI运行；`justfile`仅保留每日检查入口。

旧研究记录中的 `tools/comi.py`、`tools/log_capture.py` 等路径与命令对应当时提交；截至c523137可按原命令复现。当前统一使用以上入口；旧脚本已迁入包，不保留两份实现。

`device-info-code`沿已验证的命令05调用链读取601 B（112 B既有校验点），含52 B设备信息构造、常量和两个容量getter。读取前逐层验证指令、literal、callee入口；两份捕获用`diag compare-references FIRST SECOND --info --out REPORT`离线核对。[字段来源](device-info-fields.md)。没有新增写入或固件备份命令。

`storage-code`扩展device-info-code至937 B，沿实际容量getter、卷名表、RAM挂载对象及函数表定位statvfs callback。`diag compare-references FIRST SECOND --storage --out REPORT`逐字节核对两份捕获。新增336 B含40 B RAM元数据；当前指针/flags/代码不吻合即停止，不自动跟随新地址。RAM并非原子快照，重启后固定地址可能失效。[存储绑定证据](storage-binding-readback.md)。

`disk-code`在storage-code上增加550 B（共1487 B），跟随FatFs、磁盘registry与实际指针，到`sd`后端和`MMC_1`设备对象；没有调用init/read/write/ioctl。用`diag compare-references FIRST SECOND --disk --out REPORT`离线核对并输出`disk_metadata`，复算缓存簇容量，拒绝未知free-cluster缓存。[证据与限制](disk-registry-readback.md)。新增RAM地址每次由当前父指针核对；值变化即停止，不能作为通用dump。

`card-code`沿disk-code新增544 B，共2031 B固定SD/MMC驱动代码与状态引用；离线输出`card_metadata`；逐层核对当前指针和调用指令，不调用init/read/write/ioctl、不访问MMIO。两份采集用以下命令比较；[实机驱动状态与边界](card-state-readback.md)。

```sh
uv run comi diag capture card-code --out artifacts/card-first.json
uv run comi diag capture card-code --out artifacts/card-second.json
uv run comi diag compare-references artifacts/card-first.json artifacts/card-second.json \
  --card --out artifacts/card-analysis.json
```

`boot-code`继承card-code校验，沿实际device_get_binding→31项device表→Flash实例/回调读取2931 B；其中字符串区有重叠。`diag compare-references FIRST SECOND --boot --out REPORT`输出`device_names`、`flash_configuration`；32 MiB是配置容量，不是芯片容量实测，也不是完整固件备份。[证据](boot-storage-device-readback.md)。裸`just`仅列命令；`just check`才执行检查。

`nor-code`继承boot-code，沿实际NOR read目标、地址模式helper读取缓存ID/flags；固定3101 B读取、3068不同字节。`diag compare-references FIRST SECOND --nor --out REPORT`输出`nor_state`；不发送JEDEC命令或调用Flash函数。[ID与容量边界](nor-driver-readback.md)。

`printk-state`：核对owned设备、完整固定镜像头及三段实际代码/literal后，读取console device、init/panic、字符hook共10 B。逐次flush和验收，不执行fread或跟随返回指针。`diag inspect-printk CAPTURE`离线重新校验并解释保存状态。[两次实测与边界](printk-runtime-state.md)。
