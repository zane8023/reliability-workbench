# 可选行业配置：预览

`synthetic-domain-config.json` 是虚构示例，不含真实参数或推荐值。`app.validators.domain_config.validate_domain_config` 只校验内存中的草案记录，不自行读取文件、联网或调用计算。格式有效不代表参数准确、来源真实、模型适用或工程安全。`verified_by_user` 仅是使用者声明，并非独立验证证据；未知值仅在 `unverified` 下允许，不会自动填入默认值。来源文本和参考条目不会被访问或核实，需另行审查。

在项目目录使用已安装的环境执行：

```powershell
.\.venv\Scripts\python.exe -c "import json; from pathlib import Path; from app.validators.domain_config import validate_domain_config, parse_domain_config_json; print(validate_domain_config(parse_domain_config_json(Path('examples/synthetic-domain-config.json').read_text(encoding='utf-8'))))"
```

该草案尚未接入计算。范围数值沿用参数所声明的单位；校验器只比较数值，无法核实单位或科学适用性。

读取 JSON 时应使用 `parse_domain_config_json` 拒绝重复键和非有限数字，并限制输入长度；直接传入已解析对象时，调用方必须自行保证解析过程没有丢失重复键。

字符长度限制在调用方已将文本读入内存后生效；处理不可信文件或网络数据时，读取前还须限制输入字节数。
