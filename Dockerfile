# 基于微信云托管官方 Django 模板（wxcloudrun-django）改造
# 选择构建用基础镜像（选择原则：在包含所有用到的依赖前提下尽可能体积小）。
FROM alpine:3.13

# 容器默认时区为 UTC。Django 设的是 Asia/Shanghai 且 USE_TZ=False，
# 若容器仍是 UTC，账单日期与 create_time 会按 UTC 计算，与实际差 8 小时，所以这里必须设上。
RUN apk add --no-cache tzdata ca-certificates \
    && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 选用国内镜像源以提高下载速度
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.tencent.com/g' /etc/apk/repositories \
    && apk add --update --no-cache python3 py3-pip \
    && rm -rf /var/cache/apk/*

# 拷贝当前项目到 /app 目录下（.dockerignore 中文件除外）
COPY . /app

WORKDIR /app

# 安装依赖。这里不用模板的 --user：那样 gunicorn 会落在 /root/.local/bin，
# 不一定在 PATH 上，直接用系统目录更稳。
RUN pip config set global.index-url http://mirrors.cloud.tencent.com/pypi/simple \
    && pip config set global.trusted-host mirrors.cloud.tencent.com \
    && pip install --upgrade pip \
    && pip install -r requirements.txt

RUN chmod +x start.sh

# 暴露端口（需与云托管「服务设置」里填的端口一致）
EXPOSE 80

# 启动：ensure_db（建库）→ migrate（建表）→ gunicorn
CMD ["./start.sh"]
