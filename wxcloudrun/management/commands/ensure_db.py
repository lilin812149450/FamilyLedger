# FamilyLedger/wxcloudrun/management/commands/ensure_db.py
# Django 的 migrate 只建表、不建库，库不存在时 migrate 会直接报错。
# 这里在 migrate 之前先把库建出来（幂等），供 start.sh 串联调用。
import pymysql
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = '目标数据库不存在时自动创建（utf8mb4）'

    def handle(self, *args, **options):
        cfg = settings.DATABASES['default']
        name = str(cfg.get('NAME') or '').strip()
        if not name:
            self.stdout.write('未配置库名，跳过建库')
            return

        # 库名来自部署配置而非请求参数，仍净化一次，避免拼接进 SQL 时出问题
        safe_name = name.replace('`', '')

        conn = pymysql.connect(
            host=cfg.get('HOST') or '127.0.0.1',
            port=int(cfg.get('PORT') or 3306),
            user=cfg.get('USER') or '',
            password=cfg.get('PASSWORD') or '',
            charset='utf8mb4',
            connect_timeout=10,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'CREATE DATABASE IF NOT EXISTS `%s` '
                    'DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci' % safe_name
                )
            conn.commit()
        finally:
            conn.close()

        self.stdout.write('数据库 `%s` 已就绪' % safe_name)
