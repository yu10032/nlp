# 离线匹配模型

当前提供可训练的 PyTorch MLP、按问题家族划分的入口，以及冻结句编码器后的训练脚本。
后端目前使用名称基线，尚未加载自训权重；正式候选召回、验证集阈值选择和问题级评测仍待实现。

在 `work` 中执行（训练依赖按需要安装，不属于后端启动依赖）：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ./training
.\.venv\Scripts\python.exe -m course_matcher.data --input data/annotations/example-pairs.jsonl --output data/annotations/example-split
.\.venv\Scripts\python.exe -m course_matcher.train --config training/configs/default.toml
```

训练首次运行会下载配置中的句编码器，缓存位于 `artifacts/encoders/`；当前搭建框架不执行此下载。
训练输出在配置指定的独立 run 目录，已有目录不覆盖。选择最佳权重只看验证损失，不读取测试集。
示例问题与课程均为开发玩具数据，正式实验需另建数据版本，不混入报告中的测试结果。

匹配头特征为 `|u-v|`、`u*v` 和余弦相似度，输出 logits，训练使用 BCEWithLogitsLoss。
只有匹配头参数更新，预训练编码器固定。后续推理服务应同时固定编码器、图谱版本、候选预算和权重版本。
