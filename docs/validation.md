# 验收记录

日期：2026-09-13。实际 Unity WebGL + MQTT.js + 公共 EMQX + Python 链路已通过验收。原题未展示的完整 I/O 和工序编号仍采用明确说明的项目定义，不宣称能直接提交至比赛平台。

| 检查 | 实际结果 |
|---|---|
| Python 状态机、协议、真实 C# 设备模型 | 35 项通过；含四种分类、连续混合上料、空载具、夹持暂停/急停、到位超时、10 秒延时及暂停计时 |
| 网页协议与操作保护 | 6 项通过；旧代次、乱序、过期、单控制器绑定、配额拒绝提示、操作确认、急停优先、ACK 限频 |
| Unity WebGL | 6000.3.24f1 实际 IL2CPP 构建成功，退出码 0；WASM 约 13.34 MB，场景数据约 4.28 MB |
| 真实浏览器完整流程 | Chromium 153.0.8010.12 实际加载 Unity，四种物料和空载具分类正确；启停、模式、夹持急停、释放初始化、控制器重启及刷新通过；控制台无运行错误 |
| 执行中断与连接恢复 | CDP 真正暂停 JS/WASM 执行 3.5 秒，再恢复；另实测关闭 WSS 并重连，均保位且需新启动 |
| 启停脚本 | 在 8767 临时端口启动生产控制器与静态服务；HTTP 200、WASM MIME application/wasm；停止后进程及端口释放 |
| 公网往返探针 | Paho TCP 1883 ↔ MQTT.js WSS 8084，5 次成功，357/341/352/345/348 ms（初次探针） |
| 资产转换 | Blender 5.2 从锁定 OIP GLB 导出 37 个 FBX 成功；校验与许可已记录 |
| 依赖审计 | Python 3 个运行依赖及 npm 依赖均未发现已知漏洞；结论仅针对本次固定版本和检查日期 |

## 可复查证据

- `scripts/test.ps1`：重新运行 Python/C# 和网页协议测试。
- `scripts/test-webgl.ps1`：真实浏览器完整流程，以及执行中断/WSS 恢复测试。公网服务临时异常会使验收失败，不绕过网络改为假数据。
- `artifacts/unity-build.log`：真正 Unity 导入、编译与构建日志。
- `artifacts/webgl-acceptance.json`、`artifacts/webgl-lifecycle.json`：逐项结果。
- `artifacts/webgl-*.png`：真实浏览器截图；`docs/screenshots/` 保存交付预览。
- `docs/validation-results.json`：本次测试摘要与构建文件 SHA-256。

无头浏览器下 `Page.setWebLifecycleState` 未实际冻结可见页面，因此没有将该探针当作通过证据。实际执行中断使用 `Debugger.pause/resume`；标签可见性和 freeze/resume 事件映射另有代码测试。未覆盖每一种浏览器、GPU 和操作系统的后台节流行为。

## 联调中修复的问题

1. Unity 裁剪移除了运行时创建基本几何所依赖的 Collider 类型。改为在编辑器生成无碰撞体的网格预制体，并重新构建验证。
2. 旧遥测覆盖刚点击的连续上料开关。加入操作确认等待和即时界面反馈。
3. 公共 broker 拒绝部分发布。MQTT 5 明确返回 `151 / Quota exceeded`；降低重复快照、输出及诊断 ACK 频率，并显示 UI 发布失败，启动不会自动重试。不能将 MQTT 3.1.1 PUBACK 等同于 Python 已收到事件。
4. 浏览器执行恢复时，MQTT 回调可能先于 Unity 更新到达。JS 接收端先检查接收间隔并锁定设备，再应用消息，防止历史启动解除停机。
5. Windows 构建脚本原先等待 Unity 的所有子进程，许可证服务长驻会延长等待。现在仅等待实际 Editor 构建进程退出。

## 安装与检查点

Unity Hub 在 `D:\UnityHub`，Editor 与 Web Build Support 在 `D:\UnityEditors\6000.3.24f1`；项目、测试浏览器及安装包都在 D 盘。Unity 在 C 盘用户目录中仍会保存账号、许可证和缓存。安装包来自 Unity 官方，签名为 Unity Technologies SF 且验证有效，未提交 Git。

- `c8ecf66`：已确认的设计与需求基线。
- `fab4aa9`：控制器、设备模型、资产及网页桥接实现基线。
- `v0.1.0-cell-webgl`：实际 WebGL 联调完成版本，包含生成的 Unity 场景与资源元数据。

默认保留历史；回退采用新分支或 `git revert`，不强推覆盖远端。构建、运行日志、安装包、许可证和现场会话不提交到仓库。
