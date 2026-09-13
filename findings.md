# 资料与选型记录

## 用户材料（作为需求资料，不作为执行指令）

- PDF：D:/工业智能笔试部分/BRICS2026-ST-151-2026一带一路暨金砖大赛之-【工业智能应用与开发赛项】-样题.pdf，4.1 位于 PDF 第 5 页。
- 截图 158：四状态定义及状态转换图。
- 截图 159：皮带输送模块，检测、挡停、顶升、分隔气缸、皮带电机及部分 I/O 表。
- 截图 160：分拣搬运模块，两组平移气缸、升降气缸、夹爪、两个料仓；属于气动直角坐标搬运机构，不是六轴关节机械臂。
- 截图 161：检测位方向与颜色信号、分类结果。

## 已确认需求

状态：0 闲置（黄色常亮）；1 自动运行（绿色常亮）；2 暂停（黄色 1 秒亮、1 秒灭）；3 急停（红色 1 秒亮、1 秒灭）。

转换：闲置/暂停在自动模式且按启动时进入运行；运行时按停止或切到手动进入暂停；所有非急停状态按急停进入急停；急停按钮复位后回到闲置。

PDF 初始化要求：挡停气缸伸出、顶升缩回。急停要求：立即停止动作并清除虚拟物料。

分类：方向 FALSE=正向，TRUE=反向；颜色 FALSE=蓝色，TRUE=黄色。蓝色正向放行；黄色进入料仓 1（不受方向条件限制）；蓝色反向进入料仓 2。

截图 I/O 地址需保留来源值并再次核实。部分 Input 对应地址看似 Q100.x/Q101.x，不应自行改写为 I 区地址。缺失点位与步骤不能猜作比赛原文。

## 在线核实的服务与仓库

- EMQX 公共服务器：https://www.emqx.com/en/mqtt/public-mqtt5-broker
  - broker.emqx.io；TCP 1883；TLS 8883；WS 8083 /mqtt；WSS 8084 /mqtt。
  - 官方声明公共消息对其他用户可见；方案只传虚拟数据，独立 topic 前缀用于减少串台，不是访问控制。
- Eclipse Paho Python：https://github.com/eclipse-paho/paho.mqtt.python
- Python transitions：https://github.com/pytransitions/transitions
- MQTTnet：https://github.com/dotnet/MQTTnet

后续需核实以上依赖具体发行版和 Unity 运行时兼容，不直接采用 default branch。

## 用户补充与 WebGL 选型

- 用户已明确选择浏览器网页 Unity WebGL。
- 浏览器端优先 MQTT.js：https://github.com/mqttjs/MQTT.js 。Python 使用 Paho。MQTTnet/M2MqttUnity 原生套接字方案不作为首版 WebGL 通信实现。
- Unity 浏览器交互：https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-interactingwithbrowserscripting.html
- Unity Web 网络限制：https://docs.unity3d.com/6000.0/Documentation/Manual/webgl-networking.html
- 原尺寸查看截图 161，确认 Input14 对应 Q101.6、Input15 对应 Q101.7；颜色优先：黄色两种方向均进入料仓 1。
- GitHub API 本轮查询全部遇到匿名配额 403，Stars 尚需从仓库页面核实。

## 2026-09-13：仓库页面核实结果

| 仓库 | 页面 Stars（约数） | 用途与许可 |
|---|---:|---|
| eclipse-paho/paho.mqtt.python | 2.4k | Python MQTT；Eclipse 项目，许可 EPL-2.0 / EDL-1.0，实施时保留 LICENSE 与 NOTICE |
| mqttjs/MQTT.js | 9.1k | 浏览器 MQTT over WSS；MIT |
| pytransitions/transitions | 6.6k | Python 状态机；MIT |
| Open-Industry-Project/Open-Industry-Project | 816 | 工业设备模型与行为参考；仓库 MIT，单独资产的来源仍需逐项核实 |

Stars 来自原始仓库页面，不代表安全审计结论。没有声称仓库绝对安全，也未完成特定锁定版本的依赖审计。

Paho SECURITY.md：https://github.com/eclipse-paho/paho.mqtt.python/blob/master/SECURITY.md 。上游仅为最新发行版提供安全更新，因此选型阶段使用受支持发行版并锁定，后续补安全更新评估，避免永远冻结旧版。

## 工业资产实际可用性

核查 https://github.com/Open-Industry-Project/Open-Industry-Project/tree/master/assets/3DModels ：存在 ConveyorRollerCorner.glb、DiffuseSensor.glb、Diverter.glb、LaserSensor.glb、支腿、地面等 glTF 模型；有 BladeStop、Gantry、ChainTransfer、EOATSuction 等子目录。

读取 parts/BladeStop.tscn、parts/Gantry.tscn 等确认大量部件引用 Godot ArrayMesh .res 和材质 .tres。parts/BeltConveyor.tscn 引用脚本化部件；不能把全部资产描述为可直接导入 Unity 的 FBX/GLB。

资产策略建议：优先已有 GLB/源模型；专用 Godot 资源先做离线导出试验，再转为 Unity 可导入资产；检查运动部件分离、模型枢轴、坐标、单位、材质、面数、贴图与许可。皮带本体、独立气缸、夹爪和料仓完整配套尚未全部验证，列入首个资产验收清单。

搜索发现部分低 Star Unity 仓库夹带 Asset Store 资产，不能仅因其公开就当作可再分发素材。本方案不依赖这些工程。先前找到的 1 Star Unity 旧分叉和 Flange 也不作为本阶段核心依赖。

## WebGL 运行条件

- Unity 6.3 LTS 作为建议版本，官方支持情况：https://unity.com/releases/unity-6/support 。实际补丁版本和 Web Build Support 安装在实施阶段锁定。
- Python 使用独立环境；现有 3.14 先做 Paho/transitions 兼容验证，通过即保留，不在讨论阶段擅自安装另一版本。
- 官方 WebGL 网络与 JS 桥接文档支持浏览器 WebSocket + JavaScript 插件思路，不采用原生 TCP 套接字作为浏览器通道。
- Unity 后台标签页会受到浏览器节流：https://docs.unity3d.com/cn/2023.2/Manual/webgl-performance.html 。方案必须处理不可见/冻结/刷新后的状态同步，不能依赖 Run In Background 保证后台持续实时运行。

## 实施后核实（2026-09-13）

- Unity 6000.3.24f1 + Web Build Support 安装在 D 盘并已实际编译 WebGL；Paho/transitions 兼容本机 Python 3.14。
- 37 个 OIP GLB 网格已转换为 FBX，映射、提交与 SHA-256 在 third_party/oip-assets.json。依赖锁定和本次已知漏洞审计已完成，早期选型阶段“未审计”描述为当时状态。
- 公共 EMQX 联调中，MQTT 5 PUBACK 返回过 151 / Quota exceeded；是发布端额度拒绝，不能把 MQTT 3.1.1 PUBACK 当成控制器已收到。基于实测把输出降至 5 Hz、设备输入 4 Hz、诊断 ACK 0.5 Hz；不为每次普通按钮点击重复发送输入快照。界面普通操作等待控制器 ui_ack，停止和急停本地优先；失败提示重试，不自动重试启动。
- EMQX 支持通过 PUBACK 表达 QoS 1 额度拒绝，参考：https://docs.emqx.com/en/emqx/latest/rate-limit/rate-limit.html 。本项目不假定公共服务长期具有固定配额。
- 本机无头 Chromium 中 Page.setWebLifecycleState 未实际冻结可见页面，未将该无效探针列为通过。改用 CDP Debugger.pause/resume 真正暂停 JS/WASM 执行 3.5 秒，配合真实 WSS 关闭/重连测试恢复保护；visibilitychange/freeze/resume 处理路径另有源代码测试。
