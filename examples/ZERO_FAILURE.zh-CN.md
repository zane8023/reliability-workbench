# 零失效二项上限——实验预览

本试验计算规定试验窗口内零事件的单侧精确二项失效概率置信上限。假设受试单位相互独立、具有相同事件概率，并在同一窗口内有明确的二元结局。它是该试验的概率上限，不是时间失效率、贝叶斯可信区间、3/n 近似或市场预测；事件和窗口标签由使用者提供，程序不会验证真实性。

在项目目录使用文档所述 Windows 环境 执行：

```powershell
.\.venv\Scripts\python.exe -c "from app.services.zero_failure_binomial import zero_failure_upper; print(zero_failure_upper(100,0.95,event_definition='Synthetic failure',observation_window='Synthetic fixed window'))"
```

虚构 n=100、置信水平 0.95 时，概率上限约为 0.02951304960704。输入超出明确范围或结果小到无法保持正规浮点精度时会被拒绝。本内容是实验功能，不构成工程保证。
