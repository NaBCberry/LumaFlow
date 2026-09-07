# Contributing to LumaFlow

欢迎提交可复现的问题报告和小范围改进。较大的交互、协议或架构调整，请先开 Issue 讨论。

## 开发环境

主要开发和验证平台为 Windows 10/11 x64，建议使用 Python 3.12。CI 同时验证 Python 3.10 和 3.12。

安装 VLC 和 FFmpeg，并确认 `ffmpeg -version` 可执行。在项目根目录运行：

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
.\env\Scripts\python.exe main.py
```

`requirements.txt` 声明运行依赖，`requirements-dev.txt` 额外提供便携包构建工具。项目当前是桌面应用源码，不要求通过 `pip install .` 安装。

## 提交前检查

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
.\env\Scripts\python.exe -m unittest discover -s tests -p "*test*.py"
Remove-Item Env:QT_QPA_PLATFORM
git diff --check
```

- 测试放在 `tests/`，新文件优先使用 `功能名_test.py`；完整命令也包含历史 `test_*.py` 文件。
- 保持现有代码风格，Python 使用四空格缩进，避免无关格式化。
- 用户可见的文字同时更新 `resources/i18n/zh-CN.json` 和 `en-US.json`。
- 行为修复应提供回归测试；媒体改动还应手动验证播放、暂停、定位、结束重播和媒体切换。
- 不提交真实用户配置、凭据、日志、缓存或构建产物。测试数据应小巧且有权分发。
- 通道显示选择不得修改 CSV 或设备协议；设备输出改动需要独立的实机验证。

## 便携包

在已安装开发依赖的 Windows 环境中运行 `python build_portable.py`。构建脚本优先使用项目的 `env` 虚拟环境，并通过 `LumaFlow.spec` 构建、检查归档和生成校验和。

版本号统一维护在 `core/metadata.py`，发布时同步更新 README 和 CHANGELOG。生成的 ZIP 及 SHA-256 文件应作为 GitHub Release 附件上传，不进入源码 Git 历史。发布前须在干净的 Windows 环境验收；当前 CI 不构建或发布二进制文件。

## Pull Request

说明问题、改动范围、测试结果和兼容性影响。UI 改动附上实际截图，避免只提供概念图。

代码贡献遵循仓库的 [GPLv3 许可证](LICENSE)。`resources/CSVfile/` 中的参考样本不包含在代码许可内，请遵守 README 中的[样本数据说明](README.md#许可与样本数据)。
