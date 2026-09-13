# 第三方来源与适配

核实日期：2026-09-13。

| 项目 | 版本/提交 | 使用方式 |
|---|---|---|
| Eclipse Paho Python | v2.1.0，af64a4365c6ac5a7a4d339e7b00f44df91353b35 | 上游 GitHub tag 源码下载供核对；运行使用校验后的官方 wheel |
| transitions | 0.9.3，f970687f48f807dd5974f59c4d76abed2bd1e7bd | 同上；四状态转换定义 |
| MQTT.js | v5.15.2，88d5ac864a3724f852d5121da35e9f932ffe6f70 | 上游 tag 核对；锁定 npm 包并本地打包到 WebGL 模板 |
| Open Industry Project | d3bcbd453a31086b83c5bad313475df3179f31f9 | 复用 37 个 GLB 网格，Blender 转换为 FBX |

依赖上游地址与完整许可见 `dependencies.json` 和旁边的许可证文件；OIP 每个文件的来源、源文件与转换结果 SHA-256 见 `oip-assets.json`。

OIP 适配仅提取、居中和导出已有网格；Unity 中重新装配并替换轻量材质，未运行 Godot 工程脚本。沿用框架、龙门、挡停、传感器、托盘、支脚和链式输送部件。皮带表面、地面、标记和测试物料是基础几何，用于仿真展示。

依赖源码缓存位于 `.cache/upstream/`，不重复提交整个上游仓库。实际运行依赖通过 `requirements.lock` 的 wheel SHA-256 与 `web/package-lock.json` 的 npm integrity 固定。npm 安装使用 `--ignore-scripts`；esbuild 通过锁定的官方平台包运行。Python 运行依赖和 npm 依赖审计本次均未发现已知漏洞，此记录有时效性。

重新转换模型：先将 OIP 上述提交检出至 `.cache/upstream/oip`，再运行：

```powershell
& 'D:\blender 5.2\blender.exe' --background --factory-startup --python scripts/import_oip_assets.py
```

Unity、Unity Hub、Blender 安装包不属于本仓库分发内容，各自使用其官方许可。
