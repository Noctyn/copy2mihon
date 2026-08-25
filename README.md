# copy2mihon

将拷贝漫画（CopyManga）的书架订阅和阅读历史导出为 Mihon / Tachiyomi 兼容的 `.tachibk` 备份文件。

## 功能特性

- **直接导出**：通过 Token 导出书架订阅与阅读历史，生成标准 `.tachibk` 备份文件。
- **备份合并**：支持将云端数据合并至手机已导出的 `.tachibk` 文件中，精准更新已读章节与历史时间戳，不破坏原有书架与其它图源数据。
- **自定义 API 域名**：支持切换官方域名、镜像站（如 `copymanga.tv`, `api.copymanga.org`）或自定义反代域名，并自动补全协议前缀。
- **自动重试与断线重连**：针对网络波动及长列表分页拉取内置自动重试与指数退避。
- **文本清洗**：自动修复乱码章节名（如 Latin-1 误解码的 UTF-8 文本）。
- **分类管理**：支持自定义书架分类、多分类标签映射或留空未分类。
- **离线转换**：支持将本地 JSON 格式的订阅数据转换为 `.tachibk`。
- **备份检查**：内置 `inspect` 命令查看 `.tachibk` 文件内容。

## 运行环境

本项目使用 [uv](https://github.com/astral-sh/uv) 进行依赖和环境管理。

## 快速使用

直接启动交互式向导：

```bash
uv run copy2mihon
```

## 命令行使用

### 1. 合并到现有备份（推荐）

将云端数据注入手机导出的备份文件中：

```bash
uv run copy2mihon merge --token "<YOUR_TOKEN>" -b backup.tachibk -o merged.tachibk -c "拷贝漫画"
```

指定自定义镜像域名：

```bash
uv run copy2mihon merge --token "<YOUR_TOKEN>" -b backup.tachibk -u "https://www.copymanga.tv"
```

### 2. 导出完整备份（订阅 + 历史）

```bash
uv run copy2mihon export --token "<YOUR_TOKEN>" -o backup.tachibk
```

### 3. 仅导出书架订阅

```bash
uv run copy2mihon export --token "<YOUR_TOKEN>" --no-include-history -o backup.tachibk
```

### 4. 仅导出阅读历史

```bash
uv run copy2mihon export --token "<YOUR_TOKEN>" --history-only -o backup.tachibk
```

### 5. 转换本地 JSON 文件

```bash
uv run copy2mihon convert input.json -o output.tachibk -c "拷贝漫画"
```

### 6. 查看备份文件内容

```bash
uv run copy2mihon inspect backup.tachibk
```

## 参数说明

### `export` 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-t, --token` | 拷贝漫画 Token（必填） | - |
| `-o, --output` | 输出文件路径 | `copymanga_backup_YYYY-MM-DD_HH-MM.tachibk` |
| `-b, --existing-backup` | 待合并的现有备份路径 | 无 |
| `-c, --category` | 书架分类名称（传入 `none` 禁用分类） | `拷贝漫画` |
| `-u, --base-url, --url` | 拷贝漫画 API 地址或镜像站 | `https://www.mangacopy.com` |
| `--include-history` | 是否导出阅读历史 | `True` |
| `--no-include-history` | 不导出阅读历史 | `False` |
| `--history-only` | 仅导出阅读历史 | `False` |
| `-s, --source-id` | 图源 ID | `6696312508930833206` |
| `--source-name` | 图源名称 | `拷贝漫画` |
| `--proxy` | HTTP / SOCKS 代理地址 | 无 |
| `--no-export-json` | 不同时生成 JSON 文件 | `False` |

### `merge` 参数

| 参数 | 说明 | 默认值 |
|---|---|---|
| `-t, --token` | 拷贝漫画 Token（必填） | - |
| `-b, --backup-file` | 现有的 `.tachibk` 文件路径（必填） | - |
| `-o, --output` | 输出文件路径 | `<原文件名>_merged.tachibk` |
| `-c, --category` | 分类名称（传入 `none` 禁用分类） | `拷贝漫画` |
| `-u, --base-url, --url` | 拷贝漫画 API 地址或镜像站 | `https://www.mangacopy.com` |
| `-s, --source-id` | 图源 ID | `6696312508930833206` |

### 环境变量

- `COPYMANGA_BASE_URL`：覆盖默认 API 基础地址（如设置为 `https://www.copymanga.tv`）。

## 运行测试

```bash
uv run python -m pytest -v
```

## License

MIT
