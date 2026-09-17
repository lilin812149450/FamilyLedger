import pymysql

# PyMySQL 报告的 version_info 是 (1, 1, 1)，而 Django 的 MySQL 后端要求 mysqlclient 1.4.3+，
# 不伪装就会以 ImproperlyConfigured 拒绝启动。这里冒充一个满足要求的版本号，
# 好处是纯 Python 驱动，容器里不用编译 C 扩展。
pymysql.version_info = (1, 4, 6, 'final', 0)
pymysql.install_as_MySQLdb()
