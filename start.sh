#!/bin/sh
set -e

# 迁移文件已随仓库提交（wxcloudrun/migrations/0001_initial.py），这里只执行 migrate。
# 不在启动时 makemigrations：多副本会同时生成迁移并互相覆盖，建表结果不确定。
#
# --fake-initial：首次接管一个"表已存在但没有本 app 迁移记录"的库时（例如从另一套
# 代码结构迁移过来），Django 会把初始迁移标记为已应用而不是重复建表。全新库上它是空操作。
#
# ensure_db 先建库（migrate 只建表不建库）；云托管绑定 MySQL 后库已自动存在，
# 且注入的账号可能没有 CREATE 权限，所以建库失败不阻断启动，交给 migrate 决断。
i=1
migrated=0
while [ "$i" -le 5 ]; do
  python3 manage.py ensure_db || echo "建库未成功（库已存在或无建库权限），继续尝试迁移"
  if python3 manage.py migrate --fake-initial --noinput; then
    migrated=1
    break
  fi
  echo "数据库迁移失败，5 秒后重试（$i/5）"
  i=$((i + 1))
  sleep 5
done

# 迁移没成功就别起服务：否则接口会在缺表状态下对外返回 500，比启动失败更难排查。
if [ "$migrated" -ne 1 ]; then
  echo "数据库迁移连续 5 次失败，拒绝启动"
  exit 1
fi

exec gunicorn wxcloudrun.wsgi:application \
  --bind 0.0.0.0:80 \
  --workers 2 \
  --threads 4 \
  --timeout 30 \
  --access-logfile - \
  --error-logfile -
