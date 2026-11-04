# 合成示例说明

[English](README.md)

所有示例参数均为虚构数据，不作为实际产品参数或现场预测。

- `synthetic_arrhenius.py`：使用给定活化能与温度计算加速因子及寿命换算，不能验证失效机制。
- `synthetic_fixed_reliability.py`：给定 Weibull 参数，计算可靠度、失效概率、风险率和分位寿命。时间和尺度应使用同一单位；形状小于 1 且时间为 0 时，风险率为奇异值，返回 `null` 并提示。
- `synthetic_exponential_fit.py`：三条完整失效和两条右删失数据的指数分布点估计。该方法假设独立同分布指数寿命与独立、无信息的右删失；计算本身不验证这些假设，也不提供置信区间。一个失效事件可给出点估计，但失效数少时会提示证据有限。

以上示例均不包含 Weibull 拟合、行业校准或市场预测。运行方法见[安装与验证](../INSTALL.zh-CN.md)。

## 已保存结果的离线报告

`synthetic_saved_report.py` 只读取固定的合成 `saved_results.json`，不调用计算器，并且只向明确指定的已有目录写入 HTML。Arrhenius 示例保存的是之前打印的六位小数加速因子，属于已舍入的展示快照，不代表完整精度的计算输出；原寿命换算值未被保存在快照中，null 表示未提供；其他记录也是合成结果。报告仅展示白名单字段，不含图表、外部资源、任务数据库或原始观测。用户提供的记录不会被渲染器验证其科学正确性。

例如，先自行创建一个空的 `report-output` 目录，然后执行：

```powershell
.\.venv\Scripts\python.exe -B -m examples.synthetic_saved_report --output-dir .\report-output --locale zh-CN
```

输出文件名固定为 `reliability-report.html`；已有文件不会覆盖。渲染器本身不做文件读写，示例程序仅读取合成快照并写入明确指定的目标目录。

另附[中文合成静态报告](synthetic-report.zh-CN.html)供查看；已自动检查结构，浏览器视觉检查尚未完成。

完整失效与右删失数据的示例、假设和限制见 [Kaplan–Meier 合成示例](KAPLAN_MEIER.zh-CN.md)。
