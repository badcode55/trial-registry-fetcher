# 文献注册信息抓取工具

这个工具用于读取一份“文献 PDF 文件名 + 注册 ID”的清单，并尝试抓取已经接入的网站信息。当前版本只会实际抓取 UMIN-CTR；NCT 和其他网站的 ID 会先记录到索引中，后续可以继续接入。

## 这个程序会做什么

- 读取 `examples/literature_ids.txt` 这样的清单。
- 对 `UMIN...` 编号，到 UMIN-CTR 网站获取研究注册信息。
- 对 `NCT...` 编号，先记录为 `pending_source_integration`，等待之后接入师姐的 NCT 代码。
- 对 `not found`，记录为 `not_found`，表示当前没有找到注册 ID。
- 生成 Excel 可以直接打开的 CSV 文件，中文和日文不应乱码。

当前版本不会根据文献题目、关键词或 PDF 文件名自动搜索注册库。

## 项目结构

```text
.
├── README.md                         使用说明
├── PROJECT_PLAN.md                   开发计划，仅 dev 分支保留
├── requirements.txt                  Python 依赖列表
├── examples/
│   └── literature_ids.txt            示例输入清单
├── output/
│   └── .gitkeep                      输出目录占位文件，运行结果不会提交到 git
├── scripts/
│   ├── run_example.sh                macOS/Linux 终端运行脚本
│   ├── run_example.command           macOS 双击运行脚本
│   └── run_example.bat               Windows 运行脚本
├── trial_registry/                   程序代码
│   ├── cli.py                        命令行入口
│   ├── runner.py                     批量处理和输出索引逻辑
│   ├── input_readers.py              读取 TXT 输入清单
│   ├── registry_ids.py               判断 UMIN、NCT、not found 等 ID 类型
│   ├── sources/                      不同注册网站的适配器
│   └── exporters/                    CSV、JSON、Markdown、TXT 导出器
├── tests/                            自动测试，仅 dev 分支保留
└── umin_ctr_scraper.py               旧入口，保留兼容
```

## 第一次使用

请先确认电脑已经安装 Python 3。

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

Windows 如果 `python` 可用，也可以运行：

```bat
python -m pip install -r requirements.txt
```

## 一键运行示例

macOS 或 Linux 终端：

```bash
bash scripts/run_example.sh
```

macOS 也可以双击：

```text
scripts/run_example.command
```

Windows：

```bat
scripts\run_example.bat
```

脚本会读取：

```text
examples/literature_ids.txt
```

并把结果写入：

```text
output/
```

## 手动运行示例

批量处理示例输入：

```bash
python3 -m trial_registry.cli --input-file examples/literature_ids.txt --input-format txt --formats csv --output-dir output
```

单独查询一个 UMIN ID：

```bash
python3 -m trial_registry.cli UMIN000019339 --formats csv --output-dir output
```

## 如何查看结果

运行后，先打开总索引：

```text
output/index.csv
```

总索引中每一行对应输入清单中的一篇文献。常见状态如下：

- `saved`：已经抓取并保存结果。
- `pending_source_integration`：这个注册网站还没有接入，例如当前的 NCT。
- `not_found`：输入清单中标记为未找到注册 ID。
- `invalid_input`：输入行格式不符合要求。

如果某一行是 `saved`，请查看这一列：

```text
result_csv
```

它会指向该文献单独生成的 CSV 文件。

## 输入文件格式

TXT 文件每行写一篇文献：

```text
- 11 Ikeda 2016.pdf: UMIN000019339
- 11 Arezzo 2021.pdf: NCT04438655
- 11 Horie 2007.pdf: not found
```

冒号左边是文献文件名，右边是注册 ID 或 `not found`。

## 开发说明

新增注册网站时，主要做两件事：

1. 在 `trial_registry/registry_ids.py` 增加 ID 识别规则。
2. 在 `trial_registry/sources/` 增加一个新的 `RegistrySource` 适配器。

这样可以避免改动批量处理和导出逻辑。

## 测试

开发分支可以运行：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_umin_ctr_unittest -v
```
