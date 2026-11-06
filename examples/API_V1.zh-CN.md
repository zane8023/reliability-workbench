# 实验性进程内调度接口合同

[English](API_V1.md) | [项目说明](../README.zh-CN.md)

本实验性源码预览于 2026-11-06 新增，整合基线为已审查公开提交 `addfb5aedf15eb8fb3c7c2a92f2ddebfde441b7e`。它是 Python 源码适配层，不是运行中的 HTTP API、网页工作台、安装包或部署。没有新增监听服务、数据库、会话、鉴权、文件上传、AI 服务或持久化。原公开计算器与报告渲染器保持不变。

## 入口与数据边界

- `dispatch(operation, envelope)` 接收支持的操作名字符串和符合 JSON 结构的 Python 字典。`operation` 是独立参数，不是请求正文中的字段。
- 外壳须含 `contract_version: "1"` 和 `input` 对象，不接受其他顶层字段。按操作校验输入后才调用公开函数。数值字符串和用布尔值代替计算数值会被拒绝；在底层模型允许的位置，普通 JSON 整数和浮点数仍可使用。
- `parse_json_body(body)` 是可选的字节解析助手。它接受最多 1,048,576 字节的严格 UTF-8 JSON，拒绝重复键、NaN/Infinity 字面量及 `1e309` 等浮点指数溢出。它可以返回任意 JSON 根值，随后由 `dispatch` 要求对象外壳。非 bytes 输入抛出 `TypeError`；格式、尺寸、重复键、非有限数或 UTF-8 错误抛出 `ValueError` 或其子类。解析错误不会自动变成调度器错误外壳。
- 字节上限只适用于解析助手，不适用于已解析的字典。调用方负责传输、日志、资源和文本编码策略。没有额外的嵌套深度/节点预算、取消、超时或网络安全保证。仍遵循 binary64 舍入，包括极小十进制数可能舍入为零；这不是任意精度十进制输入。
- 请求与结果在内存中处理。成功结果可能包含输入观测、参数或标签，报告包含 Base64 HTML；不要意外写入日志或对外传输。失败消息不回显提交的键名、值或原异常文本。这不构成全部依赖与调用方都没有 I/O 的证明。

## 支持的操作

| 操作 | 输入合同 | 结果与边界 |
| --- | --- | --- |
| `arrhenius.evaluate` | `model_name: "arrhenius"`；`parameters` 含数值 `activation_energy`、`test_temperature`、`use_temperature`；单位 `temperature_unit`（`K` 或 `degC`）、`activation_energy_unit`（`eV` 或 `J/mol`）、`humidity_unit`（`fraction` 或 `percent`）沿用公开默认值。可选 `life_conversion` 为 null，或只含 `input_life`、`input_condition`（`test` 或 `use`）、`time_unit` 的对象。 | 已公开的正向加速因子及可选寿命换算。不接受内部治理输入。已识别但未开放的模型返回 `unsupported_model`；不存在的模型拼写返回 `invalid_input`。不赋予正式现场失效预测资格。 |
| `reliability.evaluate` | `model` 为 `weibull` 或 `exponential`；`parameters` 分别且仅为 `{scale, shape}` 或 `{failure_rate}`；另含 `time`、`time_unit`，可选 `quantile_probability` 默认 0.1。 | 给定参数的可靠度、失效概率、风险率和分位时间，不是 Weibull 拟合。原有零时间行为与数值范围保护保留。 |
| `exponential.fit` | `observations` 为 1–10,000 个只含 `kind`（`exact` 或 `right_censored`）和正数 `time` 的对象；另含 `time_unit`。 | 指数点 MLE，至少需要一个完整失效事件；不新增置信区间或预测。 |
| `kaplan_meier.estimate` | `failures` 列表；可选 `right_censored` 列表，默认空；显式非空 `time_unit` 标签。两列表合计 1–10,000 个非负有限数。 | 原事件/风险集点估计。零时间与全删失数据仍有效。该函数接受非空单位标签，不使用其他时间模型的较窄单位枚举；不会识别单位混用。 |
| `zero_failure.upper_bound` | 整数 `sample_size` 为 1–10,000,000；数值 `confidence_level` 严格在 0 与 1 之间；`event_definition`、`observation_window` 为有意义的 UTF-8 字符串，各最多 500 个字符。 | 声明窗口内的精确单侧二项概率上限，不是时间失效率或现场失效预测。 |
| `report.render_saved` | `records` 为 `{kind, data}` 对象列表；可选 `locale` 为 `en`（默认）或 `zh-CN`；可选 `title` 为 null/默认标题，或 1–160 个字符。 | 仅展示的 HTML 资产，含 MIME 类型、字节数、SHA256 和 Base64 字节。渲染器不执行计算或写文件。 |

Arrhenius 寿命换算、给定参数可靠性和指数拟合采用 `second`、`minute`、`hour`、`day`、`year`。原模型各自的约束仍适用，不把指数流程的正数/失效数门槛强加给 Kaplan–Meier。

当前五种保存结果报告为 `arrhenius`、`fixed_reliability`、`exponential_fit`、`kaplan_meier`、`zero_failure_binomial`。需提供完整结果并保留原验证状态、假设和警告。报告只展示选定字段，不独立验证算术或工程适用性。限制为 1–25 条记录、渲染器序列化后的记录输入最多 256 KiB、输出资产最多 8 MiB。结果中的其他元数据不会自动展示；没有图表。

公开源码另有 Nelson–Aalen，但本调度器没有 Nelson 操作，保存结果渲染器也不接受 Nelson 种类。CSV 流程、行业格式校验、通用求解、HTTP 路由和原工作流也不是本次新增的调度操作。

## 合成示例

在本项目源码目录中运行，使用项目所需依赖。示例不会创建文件。

```python
import base64
import hashlib
from app.api_v1 import dispatch, parse_json_body

request = parse_json_body(b'{"contract_version":"1","input":{"time_unit":"hour","observations":[{"kind":"exact","time":1},{"kind":"exact","time":2},{"kind":"exact","time":3},{"kind":"right_censored","time":4},{"kind":"right_censored","time":5}]}}')
response = dispatch("exponential.fit", request)
assert "result" in response, response
result = response["result"]
assert result["total_exposure"] == 15.0
assert result["scale"] == 5.0
assert result["validation_status"] == "synthetic_case_checked"

saved = dispatch("report.render_saved", {
    "contract_version": "1",
    "input": {"records": [{"kind": "exponential_fit", "data": result}],
              "locale": "zh-CN", "title": "合成点估计"},
})
assert "result" in saved, saved
asset = saved["result"]
raw = base64.b64decode(asset["content_base64"], validate=True)
assert len(raw) == asset["byte_size"]
assert hashlib.sha256(raw).hexdigest() == asset["sha256"]
assert asset["presentation_only"] and not asset["calculation_performed"]

bad = dispatch("reliability.evaluate", {
    "contract_version": "1",
    "input": {"model": "exponential", "parameters": {"failure_rate": 0.2},
              "time": "1", "time_unit": "hour"},
})
assert bad["error"]["code"] == "invalid_input"
print("合成指数尺度：", result["scale"], result["time_unit"])
```

其他数学示例：[Arrhenius 与给定参数/指数计算](README.zh-CN.md)、[Kaplan–Meier](KAPLAN_MEIER.zh-CN.md)、[零失效上限](ZERO_FAILURE.zh-CN.md)。

## 响应与错误

成功外壳为 `{"contract_version":"1","result":...}`，保留同版本公开函数完整的 JSON 兼容结果，以及其中已有的警告和来源。Arrhenius 保留原 `formula_validation_status`/`validation_scope`，其他计算保留其 `validation_status`；零失效仍为 `experimental_synthetic_checks_only`，适配层不升级任何状态。

失败外壳为 `{"contract_version":"1","error":{"code":"...","message":"...","fields":[...]}}`：

- `unknown_operation`：不支持的操作名或非字符串操作。
- `invalid_request`：外壳/input 不是对象、缺少 input，或外壳含未知字段。
- `unsupported_contract_version`：版本缺失、非字符串，或不等于 `"1"`。
- `invalid_input`：操作字段、类型、单位、数据或数值范围被拒绝。
- `unsupported_model`：已识别的加速模型不在公开 Arrhenius 范围内。
- `internal_error`：未预期失败，细节不返回。

`fields` 只包含安全的 schema 级路径或为空；当前 Pydantic 错误使用空列表。本模块没有 HTTP 状态码和路由。HTTP 路由仍为未来工作，不是已实现服务。

## 验证与来源边界

既有本地调度器源码和测试已对照记录哈希，再以窄范围增量整合到当前公开代码。本次修正只收紧适配层输入边界并修正/补充测试。原公开计算器、报告、CSV 流程、Nelson 实现、许可证和依赖声明不变。适配层没有新增依赖，依赖各自条款及继承源码的来源限制仍适用；不据此宣称整项目权利全部获证。

定向验证命令为 `python -m unittest discover -s tests -p "test_api_v1.py" -v`。2026-11-06 的本次集成通过 120 项定向测试（36 项调度器测试和 84 项受影响的既有测试）、双语示例及 40 个本地文档链接检查。环境为 Linux x86_64、Python 3.12.14、Pydantic 2.13.4、NumPy 2.3.5、SciPy 1.17.0，未安装或更改依赖；不等于新增 Windows/Python 3.10.11 兼容性验收。未新增完整套件、浏览器视觉、HTTP 安全、项目安装、VDI 或现场使用验收声明。合成结果不能证明模型假设和决策适用性。
