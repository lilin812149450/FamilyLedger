# FamilyLedger 后端部署与配置清单

基于微信云托管官方 Django 模板（`wxcloudrun-django`）改造，保留单 app `wxcloudrun/` 的目录结构。

前后端调用链：

```
小程序 wx.cloud.callContainer
  → 云托管网关（注入 X-WX-OPENID，客户端无法伪造）
  → 容器 POST /api/login | /api/family | /api/bill
  → MySQL(families / users / bills)
```

前端 `web/utils/config.js` 已把目标写死为：云开发环境 `prod-d0gohy87nf547a4f1`、云托管服务 **`familyledger`**、路径前缀 `/api`。
**服务名和环境必须一致**，否则前端调不通。

---

## 0. 本地开发（端口 80）

```bash
cd FamilyLedger
python manage.py runserver 127.0.0.1:80 --noreload
```

本地也走 **80 端口**，与容器一致（`Dockerfile` 的 `EXPOSE 80`、`start.sh` 的 gunicorn `--bind 0.0.0.0:80`）。

对应前端 `utils/config.js`：`API_MODE = 'local'`、`LOCAL_BASE_URL = 'http://127.0.0.1:80'`。

Windows 不限制 1024 以下端口，普通权限即可绑 80；换端口时**前端 `LOCAL_BASE_URL` 要一起改**。

## 1. 部署

> ⚠️ **构建目录是仓库根目录（即 `FamilyLedger/`）**，Dockerfile 就在根上。
> 不要部署 `web/server/`——那是早期的另一套实现，已弃用，接口路径和目录结构都不一样。

- 镜像：`Dockerfile`（alpine + python3 + gunicorn，监听 80）
- 启动：`start.sh` → `ensure_db`（建库）→ `migrate --fake-initial`（建表）→ gunicorn
- 迁移文件 `wxcloudrun/migrations/0001_initial.py` 已随仓库提交，容器启动不再现生成迁移
- `.dockerignore` 已排除 `.env`，**本地数据库密码不会被打进镜像**
- 容器时区已设为 `Asia/Shanghai`（Django 是 `USE_TZ=False`，容器若为 UTC 会导致账单日期差 8 小时）

### `--fake-initial` 是干什么的

首次接管一个"表已存在但没有本 app 迁移记录"的库时（比如从早期代码结构迁过来），Django 会把它标记为已应用而不是重复建表。全新库上是空操作。**注意它只比对表是否存在、不比对列**——如果表结构有差异（比如多一列），它会静默接受。

## 2. 环境变量清单

配置位置：云托管控制台 → 服务设置 → 环境变量。

| 变量 | 必填 | 填什么 | 不填的后果 |
|---|---|---|---|
| `MYSQL_URL` 或 `MYSQL_*` | ✅ | 见下方「二选一」 | 容器启动连不上库，**拒绝启动** |
| `DJANGO_SECRET_KEY` | 建议 | 一串随机长字符串 | 会退回代码里的默认值 |
| `DJANGO_DEBUG` | 否 | 默认 `false`，别设 true | 设 true 会把完整堆栈暴露到线上 |

### 数据库变量：二选一

**A. 这个实例就是云托管里绑定的 MySQL**（控制台 → 服务设置 → MySQL 能看到）
→ 平台自动注入 `MYSQL_ADDRESS` / `MYSQL_USERNAME` / `MYSQL_PASSWORD` / `MYSQL_DATABASE`，**不用手填**。只要确认库名是 `ledger`。

**B. 自建 / 外部实例**（host 形如 `*.sql.tencentcdb.com`）
→ 手动加一条（地址、端口、密码填你自己的）：

```
MYSQL_URL=mysql://<用户名>:<密码>@<数据库地址>:<端口>/ledger
```

`MYSQL_URL` 优先级**高于**自动注入的 `MYSQL_*`，两边都配时以 `MYSQL_URL` 为准。

## 3. 手机号：已不再使用

前端已移除手机号（登录页也删了），身份完全由 openid 决定，**不需要任何微信手机号相关配置**（不用「开放接口服务」，也不用 `WX_APPID` / `WX_APP_SECRET`）。

## 4. 云开发存储（头像）

`web/pages/mine/mine.js` 用 `wx.cloud.uploadFile` 把头像传到 `avatars/`，存回的 `cloud://` 地址写进 `users.avatar_url`。
这依赖云开发环境的**存储**能力，和云托管是两套东西，需单独确认该环境已开通存储。

## 5. 部署后自测

```bash
curl -s https://<云托管服务域名>/
# 期望：{"code":0,"message":"ok","data":{"service":"family-ledger","time":...}}
```

看容器日志（控制台 → 日志），确认出现：

```
数据库 `ledger` 已就绪
Applying wxcloudrun.0001_initial... OK      # 首次库则 OK，接管已有库则 FAKED
```

最后在微信开发者工具里走一遍真实链路：进入首页 → 记一笔 → 首页和「我的」都能看到 → 家庭页能创建/加入。

## 6. 已知取舍

`requirements.txt` 里 Django 锁在 **4.1.13**，因为生产库是 MySQL **5.7**，而 Django 4.2 起要求 MySQL 8.0.11+。
Django 4.1 自 2023-12 起已停止支持、不再有安全更新。要升 Django 必须**先**把数据库实例升到 MySQL 8.0，两件事绑定。

模板原始依赖里的 `powerline-status` / `pytz` / `asgiref` / `sqlparse` 已移除：前两个是模板遗留且无用，后两个由 Django 自动拉取。
