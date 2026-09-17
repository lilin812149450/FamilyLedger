# FamilyLedger/wxcloudrun/models.py
# 云托管 MySQL 表结构：families / users / bills
from django.db import models


class Family(models.Model):
    """家庭"""

    name = models.CharField(max_length=64, default='我的家庭')
    invite_code = models.CharField(max_length=16, unique=True)
    owner_openid = models.CharField(max_length=64, db_index=True)
    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'families'

    def __str__(self):
        return self.name


class User(models.Model):
    """用户：openid 由云托管网关通过 X-WX-OPENID 请求头注入，客户端无法伪造"""

    openid = models.CharField(max_length=64, unique=True)
    unionid = models.CharField(max_length=64, blank=True, default='')
    nick_name = models.CharField(max_length=64, blank=True, default='')
    avatar_url = models.CharField(max_length=512, blank=True, default='')

    # 成员关系直接落在外键上，不再用 JSON 数组存 members，
    # 多人同时加入/退出不会互相覆盖
    family = models.ForeignKey(
        Family,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='members',
    )

    create_time = models.DateTimeField(auto_now_add=True)
    update_time = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.nick_name or self.openid


class Bill(models.Model):
    """账单明细"""

    class Type(models.TextChoices):
        EXPENSE = 'expense', '支出'
        INCOME = 'income', '收入'

    user_openid = models.CharField(max_length=64, db_index=True)
    family = models.ForeignKey(
        Family,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='bills',
    )

    # 冗余记录当时的昵称/头像，避免成员退出后历史账单显示为空
    nick_name = models.CharField(max_length=64, blank=True, default='')
    avatar_url = models.CharField(max_length=512, blank=True, default='')

    type = models.CharField(max_length=10, choices=Type.choices, default=Type.EXPENSE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    category = models.CharField(max_length=32, blank=True, default='其他')
    remark = models.CharField(max_length=64, blank=True, default='')
    date = models.DateField(db_index=True)
    month = models.CharField(max_length=7, db_index=True)
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'bills'
        indexes = [
            models.Index(fields=['user_openid', 'date']),
            models.Index(fields=['family', 'date']),
        ]

    def __str__(self):
        return '%s %s' % (self.date, self.amount)
