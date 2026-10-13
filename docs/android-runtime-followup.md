# Android runtime and independent host follow-up

## 2026-10-13：第三主机与完整HCI证据

**安卓同样缺第二个日志帧的首244 B，缺片已在手机HCI边界。**
全11条Actions通知与此前Linux HCI逐字节相同；没有修复日志出口。
[逐包收据、源哈希、参数及状态复核](evidence/android-log-hci-loss-2026-10-13.json)。

本轮问题：新接入的安卓能否提供可靠诊断主机，以及非root bugreport是否能
补齐原始ATT证据？与Astra交叉审查后，限定一次身份/状态基线、一次
PREPARE→START→help→STOP、一次独立结束状态；没有重试help、加填充命令、
录音、改卡配置、读内存或刷机。用户无CoMi账号，真实官方录音页路线仍不可用。

### 手机与工具

- Redmi K30 Pro，Android12/API31，release OS；只用已授权ADB，无root。
  REA设备Evidence `ev_ab2211882b6116224238bc408d201a20cbd634b6621acff46383f1b5733389d5`。
- 当前手机未安装`com.seeyon.comi`；不能沿用下方旧PID/活动页。
  官网1.1.2 APK下载且SHA匹配旧固定样本；MIUI USB安装拒绝，未安装官方App。
- 用户确认MIUI要求插SIM卡才能开启USB安装；通过正常手机文件管理器安装
  本仓库[21KB诊断APK](../tools/android_probe/README.md)，没有改系统验证机制。
  包`site.rocry.rcominote.probe`，只申请CONNECT权限；没有Internet/OTA/任意命令。
- 源码构建、签名/manifest核对通过；Java解码器用独立旧help基线验证1234个
  切分点，拒绝历史缺片及重复ACK。Python独立验证器不相信APK成功标签。

### 非root抓包验收

[文章](https://mp.weixin.qq.com/s/IBtYaujbdvznn1ZPwdj6VA)启发采用bugreport及保留
`.last`；[AOSP说明](https://source.android.com/docs/core/connect/bluetooth/verifying_debugging)
还明确区分常驻压缩摘要与用户开启的完整HCI。两者实际对照：

| 条件 | 实际产物 | 能证明什么 |
|---|---|---|
| 原先disabled | bugreport没有raw snoop成员；AOSP `btsnooz.py`解出2132记录：781command、1351event、**0ACL** | 系统摘要可取得，不能分析本轮ATT载荷 |
| Developer options Enabled，蓝牙重启后`mSnoopLogSettingAtEnable = full` | `FS/data/misc/bluetooth/logs/btsnoop_hci.log`，515846 B，3338记录；没有`.last`成员 | 原始H4载荷可取；记录original/included均完整、reported drops均0 |

全量bugreport包含其他App/周边设备信息，留ignored `artifacts/android-20261013/`，
不进Git。零reported drops不是控制器/logger绝不漏记的证明。

使用已有BlueZ5.72 `btmon -r`独立解码；新固定样本验证器直接读原始btsnoop，
绑定连接事件与同连接GATT发现，拒绝截断、未知分片布局或哈希变化：

```sh
uv run tools/verify_android_probe.py artifacts/android-20261013/info-before.jsonl
uv run tools/verify_android_probe.py artifacts/android-20261013/help.jsonl  # 预期exit1
uv run tools/verify_android_log_capture.py artifacts/android-20261013     # 对照成功exit0
```

最后一条成功只表示**失败样本的逐字节对照通过**，不把诊断失败改记成功。

### 实测与归因边界

身份经过Boyi CRC及GET_SERIAL核对为`C261CF0430`；初始FW010004、NOTE/idle。
手机请求MTU512，实际247；help时HCI确认双向PHY2M、Data Length251 B、
连接间隔15ms。不是“请求1M/512便实际使用1M/512”。

连接HCI handle5，由#2458 enhanced connection complete绑定public MAC；
#2534发现Actions写/通知value handle`0x16/0x18`，不沿用Mac特征对象的handle。

| HCI包 | 相对独立成功help基线 | 安卓回调 |
|---|---|---|
| #2599、#2605 | PREPARE、START两个精确ACK | 逐字节相同 |
| #2609–2611 | 第一512 B帧，244+244+24 | 完整，逐字节相同 |
| #2612–2613 | 第二512 B帧仅`[244:488]`、`[488:512]` | 缺`[0:244]`，逐字节相同 |
| #2614 | 第三199 B帧 | 完整，逐字节相同 |
| #2616、#2620–2621 | help ACK、STOP ACK、F1原始尾部 | 全部留存；损坏流不重新同步 |

全部13条应用通知（含两条Boyi）及6条特征写与HCI一致。Actions11条还与
Linux独立HCI完全相同，因此**不是这次Android回调或Java/Python拼帧引入的缺片**。
它显著削弱某个主机栈专有错误或随机无线丢包假说，但不证明缺失包从未上空口。

APK在首个坏header停止研究命令，连接可用时独立发送STOP，保存4.5s原始清理窗口；
总约6.85s，整体false、严格STOP确认false。原始ACK/F1不是坏流恢复成功。
随后新连接`info`成功，完整52 B状态payload与独立初始查询一致；仍NOTE/idle、
FW010004、total/free59634/59598。没有新录音/删除，未做完整文件字节比较。

### 改变了什么决策

- Android主机/无root完整HCI路线已实测成立；Actions可靠日志路线仍未成立。
  不再用换主机、调START延迟、填充命令重复同一help试验。
- 第三个主机的完全相同缺口，使后续优先审**实际固件异步发送队列、HCI
  缓冲区与失败处理**。ring保存层8位回绕是另一机制，不会单独解释完整帧头也缺失。
- **实际镜像的异步失败链已闭合**，见下方；不再只是参考SDK候选。
  仍缺失败现场/空口证据，不能宣布本次缺片根因。
- 完整NOR备份、独立退出、匹配恢复包、自写固件运行的条件均未解除。

### 新的实际固件证据：入队成功后仍可丢包

[固定镜像、20个代码窗口SHA、11份源码SHA与精确调用点](evidence/android-tx-path-2026-10-13.json)。
同一完整927632 B系统镜像SHA `ce2ddd3271b7856915dd3b564257a5bf5e99c7d88d651a392c19a2aa8e2a1e2f`；
普通Capstone离线分析，不冒充REA或硬件执行。Astra两次有界审查后，主调查者独立
复核全部20段原始SHA、stream/HCI两张dispatch表，以及失败释放关键指令。

| 实际地址 | 静态行为及边界 |
|---|---|
| `100517fc`→ops `100bd7f8`→`100b194a` | 真实日志writer按MTU−3分片；底层负返回不推进offset，按配置重试；未发现简单的“失败也跳过首片”分支 |
| `1006bfc8`→`100b241e`→`10077568`→`10076dc4`→`100b4df2` | notify分支创建ATT0x1b buffer并复制payload；ATT可先入队后返回0 |
| `1007821c`→`100b3ed2`→`100748f8` | channel/L2CAP进入conn发送；`100749b4`将buffer入conn+38队列，随后返回0 |
| `10074ce0`→`10074b84`→`10071fa4` | 异步drain从同一conn+38队列取包，执行HCI发送；最初stream调用已返回 |
| driver表`100bc3f8`，send `100354e8`→`10034f94` | init注册表和dispatcher读取同一driver槽；共享HCI TX ring申请失败时可返回−22，清TX上下文 |
| `10074db4`→`10074dc6`→`1006d3d4` | 未分片错误分支释放原buffer，没有重新入队、没有给最初日志writer返回失败 |

**已证明的静态性质：** 这份CoMi固件存在“上层接受通知→稍后下层发送失败→队列项
释放”的路径，发送成功ACK/接受长度不等于逐包送达。它能解释为何首个512 B帧正常、
某个后续通知缺失、再后面的通知仍正常，比ring文本回绕更贴近本次边界。

**尚未证明的现场归因：** 未读当时driver槽`180014f4`、ring占用/claim返回、错误计数
或设备ACL分片状态；没有证明为什么恰好丢第4个help通知。重复释放只保留为条件性
所有权疑点，未观测引用数或内存损坏，不当作另一项已确诊bug。

```sh
uv run tools/inspect_log_tx_path.py artifacts/mapped-system-20261012.bin \
  > artifacts/android-20261013/tx-path-NEW.json
```

工具校验镜像、20窗口及dispatch表，输出线性Thumb窗口；literal pool/跳表不据此
当可执行代码，字节复验也不证明运行时选择。下一步只取能区分此候选的发送现场或空口
证据；不以更多邻近callee、START延时排列或盲改驱动代替缺失观察。

文章可复用的是原始证据、对照实验与非root抓包。其其他设备MSPLIM、加密类名
不能推广为本机内核、安全扩展开启或线上加密策略；本机M4已有实际CPUID证据。

## 2026-10-12：既有官方App运行态

Scope: existing installed `com.seeyon.comi` on the connected, owned Android phone.
Read-only package/process/task/socket/log inspection; one temporary local ADB
forward, removed afterward. No app install/update, launch, login, device binding,
recording, deletion, firmware update, root, or permission change.

## Observed

| Question | Runtime evidence | Boundary |
|---|---|---|
| Installed app version | `1.2.4`, version code `10`, min SDK 21, target SDK 34; installer `com.heytap.market` | Package manager declaration; APK byte identity not acquired in this pass |
| Debuggable application | Package flags `[ HAS_CODE ALLOW_CLEAR_USER_DATA LARGE_HEAP ]`; `DEBUGGABLE` absent | Release flag does not determine WebView debugging by itself |
| Existing process | `pidof com.seeyon.comi` → `14564` | Already running; this investigation did not launch it |
| Existing app task | Task 237 has only `com.seeyon.comi/.launcher.ui.login.AccountLoginActivity`; sleeping, not visible, idle | Activity-manager state, not a screenshot or proof of all persisted authentication state |
| WebView inspection surface | `/proc/net/unix` exposes `@webview_devtools_remote_14564` | Socket presence alone does not prove a responsive debug endpoint |
| CDP discovery | Forwarded that exact socket to ephemeral localhost port 61907; `GET /json/list` received zero bytes and timed out after 5 seconds | No target, current page URL, script, or network request recovered |
| Scoped retained logs | REA `read_adb_logcat`, PID 14564, requested newest 500 lines → 0 lines / 0 bytes | Empty retained window; no conclusion about earlier requests or disabled logging |

REA package inspection Evidence:
`ev_c3f2afa24c8f3481c33ae386fb4192acb5281fe2c36f813c163f829c3ccd55a2`.
Scoped log Evidence:
`ev_caec44ce290337221bc46ee382dd0e98eae41958ed1fb8a8273eed662b5eeda7`.

REA `inspect_adb_window` returned no focus declarations; Evidence
`ev_fee3a9ff30281525a7975bf1d116b105cdfed41b41fa0b461b09feadbe471fca`.
This does not identify a foreground app. Direct task inspection supplies the
narrow CoMi activity observation above. REA browser discovery did not return
within the observation period and was cancelled; no successful REA browser
Evidence is claimed. The independent bounded HTTP request establishes the
endpoint timeout.

Ignored local records: `artifacts/android-runtime/{package.txt,activity.txt,unix-before.txt}`.
They contain host/device metadata and are intentionally not committed. Empty
`cdp-targets.json` is a failed request artifact, not a valid target listing.

## Blocker and next useful action

Owner response in this session: **暂时不登录**. Authenticated runtime research is
explicitly deferred; no further phone actions are part of this pass.

The observed CoMi task is at the account-login activity. An authenticated recorder
page and its upgrade workflow have not been observed. Login-dependent navigation
stopped here; no credentials were requested or submitted, and no alternative
activity/deep link was used to bypass the login flow.

To resume this route: owner opens CoMi normally, completes any required login,
and leaves its recorder page open. Then re-observe its current PID, exact WebView
socket, page target and page sources. A now-responsive endpoint can provide the
actual loaded URL/assets; observing a normal update-status page may reveal a
firmware metadata route without initiating an update. If the WebView socket
remains unresponsive, retain that as a separate transport blocker rather than
inferring absence of a firmware-update feature.

This pass proves neither a current recorder page URL nor firmware acquisition,
backup, update or recovery capability. The old bundled `noteweb` URL remains
static historical evidence; it has not been corroborated in app runtime.
