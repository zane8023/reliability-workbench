# Kaplan–Meier 生存点估计（预览）

在项目根目录按 INSTALL.zh-CN.md 安装后执行：

```powershell
.\.venv\Scripts\python.exe -c "from app.services.kaplan_meier import kaplan_meier; import json; print(json.dumps(kaplan_meier([1,2,2],[2,3],time_unit='hour'), indent=2))"
```

合成数据包含 1、2、2 小时三次失效和 2、3 小时两次右删失。1 小时后生存率为 0.8，2 小时后为 0.4；同时间删失个体在该时刻失效计算中仍属于风险集。结果是以独立非信息性右删失为假设的点估计，不是置信区间、寿命分布拟合或预测；不支持延迟进入、左删失或区间删失。

请以适当的数值精度提供时间：调用前已舍入的浮点值无法恢复；无法精确表示为浮点数的整数时间会被拒绝。
