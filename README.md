# copy2mihon

将拷贝漫画（CopyManga）的书架订阅和阅读历史导出为 Mihon / Tachiyomi 兼容的 `.tachibk` 备份文件。

支持直接导出、合并已有备份、镜像站、自定义代理，以及本地 JSON 转换等功能。

## 功能

* 导出拷贝漫画书架和阅读历史，生成 `.tachibk` 备份文件。
* 将云端书架和阅读进度合并到手机已有的 `.tachibk` 备份中。
* 支持官方主站、镜像站和自定义 API 地址。
* 支持 HTTP / SOCKS5 代理。
* 对缺少 `path_word` 的数据使用确定性的 SHA-1 哈希作为备用标识，避免重复创建漫画。
* 自动处理部分 UTF-8 / Latin-1 / CP1252 乱码文本。
* 4xx 请求直接失败，5xx 和网络抖动自动重试。
* 支持指定书架分类，也可以禁用分类。
* 支持多分类标签映射。
* 支持从本地 JSON 转换为 `.tachibk`。
* 提供 `inspect` 命令查看备份中的漫画、图源和分类信息。

---

## 获取拷贝漫画 Token

拷贝漫画 API 使用 Token 进行身份验证。

### 1. 登录并进入个人书架

先登录拷贝漫画官网或镜像站，然后直接进入个人书架页面：

* 官方主站：`https://www.mangacopy.com/web/person/shujia`
* 官方镜像：`https://www.copy4000.com/web/person/shujia`
* 官方镜像：`https://2026copy.com/web/person/shujia`

> **注意**
>
> 拷贝漫画在首页和阅读页面对开发者工具做了限制。需要进入个人书架页面 `/web/person/shujia` 后，再打开开发者工具。

### 2. 在 Network 中找到书架请求

1. 在书架页面按 `F12`，或右键选择“检查”。
2. 打开 **Network（网络）**。
3. 在筛选框中输入 `collect/comics`。
4. 刷新页面，或者切换一次书架分类。
5. 找到类似 `comics?limit=...` 的请求。

![定位书架请求](docs/images/find_token_step1.png)

### 3. 复制 Authorization

点击对应请求，在右侧打开 **Headers（标头）**，找到 **Request Headers（请求标头）** 中的 `authorization`。

复制后面的 Token，例如：

```text
Token cd7e7ffa36cf...
```

也可以只复制 Token 本身：

```text
cd7e7ffa36cf...
```

![复制 Authorization Token](docs/images/find_token_step2.png)

程序会自动处理以下情况：

* `Token` 前缀
* `Bearer` 前缀
* 多余空格
* 外层引号

也可以通过环境变量设置 Token，这样就不需要每次在命令行中输入：

```bash
COPYMANGA_TOKEN=你的Token
```

---

## 快速开始

### 使用预编译程序

从 [Releases](../../releases) 下载对应平台的可执行文件，例如：

```text
copy2mihon-windows-amd64.exe
```

无需安装 Python，直接运行即可进入交互式向导。

### 使用 uv / Python

启动交互式向导：

```bash
uv run copy2mihon
```

---

## 命令行

### 合并到已有备份

推荐使用这种方式，将拷贝漫画的云端数据合并到手机已经导出的 `.tachibk` 文件中：

```bash
uv run copy2mihon merge \
  --token "<YOUR_TOKEN>" \
  -b backup.tachibk \
  -o merged.tachibk \
  -c "拷贝漫画"
```

指定镜像站：

```bash
uv run copy2mihon merge \
  --token "<YOUR_TOKEN>" \
  -b backup.tachibk \
  -u "https://www.copy4000.com"
```

合并时会尽量保留原备份中的书架、分类以及其它图源数据，只更新拷贝漫画对应的漫画和阅读进度。

### 导出完整备份

同时导出书架订阅和阅读历史：

```bash
uv run copy2mihon export \
  --token "<YOUR_TOKEN>" \
  -o backup.tachibk
```

### 只导出书架

不包含阅读历史：

```bash
uv run copy2mihon export \
  --token "<YOUR_TOKEN>" \
  --no-include-history \
  -o backup.tachibk
```

### 只导出阅读历史

```bash
uv run copy2mihon export \
  --token "<YOUR_TOKEN>" \
  --history-only \
  -o backup.tachibk
```

### 转换本地 JSON

将本地 JSON 数据转换为 `.tachibk`：

```bash
uv run copy2mihon convert input.json \
  -o output.tachibk \
  -c "拷贝漫画"
```

### 查看备份内容

```bash
uv run copy2mihon inspect backup.tachibk
```

可以查看备份中的漫画数量、图源以及分类等信息。

---

## 参数

### `export`

| 参数                      | 说明                                             | 默认值                                         |
| ----------------------- | ---------------------------------------------- | ------------------------------------------- |
| `-t, --token`           | 拷贝漫画 Token。未指定时使用环境变量 `COPYMANGA_TOKEN`，否则提示输入 | -                                           |
| `-o, --output`          | 输出文件路径                                         | `copymanga_backup_YYYY-MM-DD_HH-MM.tachibk` |
| `-b, --existing-backup` | 在现有备份基础上继续合并                                   | 无                                           |
| `-c, --category`        | 书架分类名称，使用 `none` 可禁用分类                         | `拷贝漫画`                                      |
| `-u, --base-url, --url` | 拷贝漫画 API 地址或镜像站                                | `https://www.mangacopy.com`                 |
| `--no-include-history`  | 不导出阅读历史                                        | `False`                                     |
| `--history-only`        | 只导出阅读历史                                        | `False`                                     |
| `-s, --source-id`       | 图源 ID                                          | `6696312508930833206`                       |
| `--source-name`         | 图源名称                                           | `拷贝漫画`                                      |
| `--proxy`               | HTTP / SOCKS5 代理地址                             | 无                                           |
| `--no-export-json`      | 不额外生成 JSON 文件                                  | `False`                                     |
| `--debug`               | 输出完整错误堆栈                                       | `False`                                     |

### `merge`

| 参数 | 说明 | 默认值 |
| ----------------------- | ---------------------------------------------- | --------------------------- |
| `-t, --token` | 拷贝漫画 Token。未指定时使用环境变量 `COPYMANGA_TOKEN`，否则提示输入 | - |
| `-b, --backup-file` | 现有 `.tachibk` 备份文件 | 必填 |
| `-o, --output` | 输出文件路径 | `<原文件名>_merged.tachibk` |
| `-c, --category` | 分类名称，使用 `none` 可禁用分类 | `拷贝漫画` |
| `-u, --base-url, --url` | 拷贝漫画 API 地址或镜像站 | `https://www.mangacopy.com` |
| `-s, --source-id` | 图源 ID | `6696312508930833206` |
| `--source-name` | 图源名称 | `拷贝漫画` |
| `--proxy` | HTTP / SOCKS5 代理地址 | 无 |
| `--debug` | 输出完整错误堆栈 | `False` |

---

## 环境变量

### `COPYMANGA_BASE_URL`

覆盖默认 API 地址，例如：

```bash
COPYMANGA_BASE_URL=https://www.copy4000.com
```

### `COPYMANGA_TOKEN`

保存拷贝漫画 Token，避免在命令行中直接输入：

```bash
COPYMANGA_TOKEN=你的Token
```

### `COPYMANGA_DEBUG`

设置为 `1` 后启用调试模式，相当于使用 `--debug`：

```bash
COPYMANGA_DEBUG=1
```

---

## 关于数据匹配

拷贝漫画部分数据可能缺少 `path_word`。这种情况下，程序会根据已有信息生成确定性的 SHA-1 标识。

这样做可以保证同一本漫画在多次导出或合并时使用相同的标识，从而避免因为字段缺失导致重复建书。

---

## 网络请求

程序对常见网络异常做了基本处理：

* `4xx`：直接返回错误，不重复请求。
* `5xx`：自动重试。
* 网络连接中断、超时等临时错误：自动重试。

也可以通过 `--proxy` 指定代理，例如：

```bash
uv run copy2mihon export \
  --token "<YOUR_TOKEN>" \
  --proxy "http://127.0.0.1:7890"
```

或：

```bash
uv run copy2mihon export \
  --token "<YOUR_TOKEN>" \
  --proxy "socks5://127.0.0.1:1080"
```

---

## 测试

运行测试：

```bash
uv run python -m pytest -v
```

---

## 打包

使用 PyInstaller 打包单文件可执行程序：

```bash
uv run python -m PyInstaller \
  --onefile \
  --name copy2mihon \
  --clean \
  main.py
```

生成的文件位于：

```text
dist/copy2mihon.exe
```

打包后的程序不需要额外安装 Python 环境。

---

## License

MIT
