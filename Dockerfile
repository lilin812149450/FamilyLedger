# 基于微信云托管官方 Django 模板（wxcloudrun-django）改造
#
# 基础镜像用 python:3.11-alpine，而不是模板的 `alpine:3.13 + apk add python3`：
#   那套拿到的是 Python 3.8，而 Django 4.1 在 Python < 3.9 上会依赖 backports.zoneinfo，
#   该包需要 gcc 现场编译，alpine 里没有编译器，构建会直接失败
#   （报 Failed building wheel for backports.zoneinfo / command 'gcc' failed）。
#   Python 3.9 起 zoneinfo 已进标准库，不再需要这个包。
FROM python:3.11-alpine

# 容器默认时区为 UTC。Django 设的是 Asia/Shanghai 且 USE_TZ=False，
# 若容器仍是 UTC，账单日期与 create_time 会按 UTC 计算，与实际差 8 小时，所以这里必须设上。
RUN apk add --no-cache tzdata ca-certificates \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

WORKDIR /app

# 先装依赖再拷代码，改代码时能复用依赖层。都是纯 Python 包，不需要编译器。
COPY requirements.txt ./
RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple \
    && pip config set global.trusted-host mirrors.cloud.tencent.com \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

# 暴露端口（需与云托管「服务设置」里填的端口一致）
EXPOSE 80

# 启动：ensure_db（建库）→ migrate（建表）→ gunicorn
CMD ["./start.sh"]
