# FamilyLedger/wxcloudrun/views.py
# 小程序后端接口：POST /api/login、/api/family、/api/bill
# 用户身份从请求头 X-WX-OPENID 取（云托管网关注入，客户端无法伪造）
import json
import math
import random
import time
from datetime import datetime, timedelta

from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Bill, Family, User

INVITE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
MAX_LIST = 3000


# ============ 通用工具 ============

def json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return {}


def ok(data=None):
    return JsonResponse({'code': 0, 'message': 'ok', 'data': data})


def fail(message):
    return JsonResponse({'code': 1, 'message': message})


def current_openid(request):
    """云托管网关注入的用户身份，公网直连调用没有这个头"""
    return request.headers.get('X-WX-OPENID', '')


def round2(value):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0
    # 与 JS 的 Math.round 保持一致，避免 Python 的银行家舍入
    sign = 1 if number >= 0 else -1
    return sign * math.floor(abs(number) * 100 + 0.5) / 100


def to_date_str(value):
    if not value:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    return str(value)[:10]


def parse_date(value):
    """解析 YYYY-MM-DD，非法返回 None"""
    text = to_date_str(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, '%Y-%m-%d').date()
    except ValueError:
        return None


def build_date_list(start, end):
    """生成 [start, end] 之间的所有日期，用于补齐折线图空缺"""
    days = []
    if start > end:
        return days
    current = start
    while current <= end:
        days.append(current.strftime('%Y-%m-%d'))
        current += timedelta(days=1)
    return days


# ============ 家庭组装 ============

def create_invite_code():
    """生成不重复的 6 位邀请码"""
    for _ in range(10):
        code = ''.join(random.choice(INVITE_CHARS) for _ in range(6))
        if not Family.objects.filter(invite_code=code).exists():
            return code
    return ''


def format_family(family):
    """家庭成员直接从 users 表实时读取，昵称/头像永远是最新的"""
    if family is None:
        return None

    members = []
    for member in User.objects.filter(family=family).order_by('id'):
        is_owner = member.openid == family.owner_openid
        members.append({
            'openid': member.openid,
            'nickName': member.nick_name or '微信用户',
            'avatarUrl': member.avatar_url or '',
            'role': 'owner' if is_owner else 'member',
            'isOwner': is_owner,
        })
    members.sort(key=lambda item: 0 if item['isOwner'] else 1)

    return {
        '_id': family.id,
        'name': family.name,
        'inviteCode': family.invite_code,
        'ownerOpenid': family.owner_openid,
        'members': members,
    }


# ============ 健康检查 ============

def index(request):
    """根路径，用于部署后自测服务是否存活"""
    return ok({'service': 'family-ledger', 'time': int(time.time())})


# ============ /api/login ============

@require_POST
def login(request):
    body = json_body(request)
    openid = current_openid(request)
    unionid = request.headers.get('X-WX-UNIONID', '')

    if not openid:
        return JsonResponse({'code': 1, 'message': '获取用户身份失败，请重新进入小程序'})

    user = User.objects.filter(openid=openid).first()
    if user is None:
        user = User.objects.create(
            openid=openid,
            unionid=unionid or '',
            nick_name=body.get('nickName') or '',
            avatar_url=body.get('avatarUrl') or '',
        )
    else:
        if unionid and not user.unionid:
            user.unionid = unionid
        if body.get('nickName'):
            user.nick_name = body['nickName']
        if body.get('avatarUrl'):
            user.avatar_url = body['avatarUrl']
        user.save()

    # 家庭已被解散时自动解绑
    family = None
    if user.family_id:
        family = Family.objects.filter(id=user.family_id).first()
        if family is None:
            user.family = None
            user.save(update_fields=['family'])

    return JsonResponse({
        'code': 0,
        'openid': openid,
        'user': {
            '_id': user.id,
            'nickName': user.nick_name or '',
            'avatarUrl': user.avatar_url or '',
            'familyId': user.family_id or '',
        },
        'family': format_family(family),
    })


# ============ /api/family ============

@require_POST
def family_api(request):
    body = json_body(request)
    openid = current_openid(request)
    action = body.get('action')

    if not openid:
        return fail('获取用户身份失败')

    user = User.objects.filter(openid=openid).first()
    if user is None:
        return fail('用户不存在，请重新进入小程序')

    family = Family.objects.filter(id=user.family_id).first() if user.family_id else None

    if action == 'create':
        if family:
            return fail('你已在一个家庭中，请先退出')
        name = str(body.get('name') or '').strip() or '我的家庭'
        family = Family.objects.create(
            name=name,
            owner_openid=openid,
            invite_code=create_invite_code(),
        )
        user.family = family
        user.save(update_fields=['family'])
        return ok({'family': format_family(family)})

    if action == 'join':
        if family:
            return fail('你已在一个家庭中，请先退出')
        invite_code = str(body.get('inviteCode') or '').strip().upper()
        if not invite_code:
            return fail('请输入家庭邀请码')
        target = Family.objects.filter(invite_code=invite_code).first()
        if target is None:
            return fail('邀请码不存在，请确认后重试')
        # 单条 UPDATE，多人同时加入不会互相覆盖
        user.family = target
        user.save(update_fields=['family'])
        return ok({'family': format_family(target)})

    if action == 'detail':
        if family is None:
            return ok({'family': None})
        return ok({'family': format_family(family)})

    if action == 'rename':
        if family is None:
            return fail('你还没有加入家庭')
        if family.owner_openid != openid:
            return fail('只有家庭创建者可以修改名称')
        name = str(body.get('name') or '').strip()
        if not name:
            return fail('请输入家庭名称')
        family.name = name
        family.save(update_fields=['name', 'update_time'])
        return ok({'family': format_family(family)})

    if action == 'leave':
        if family is None:
            return fail('你还没有加入家庭')
        if family.owner_openid == openid:
            if User.objects.filter(family=family).count() > 1:
                return fail('你是家庭创建者，请先移除其他成员')
            user.family = None
            user.save(update_fields=['family'])
            family.delete()
        else:
            user.family = None
            user.save(update_fields=['family'])
        return ok({'family': None})

    if action == 'removeMember':
        if family is None:
            return fail('你还没有加入家庭')
        if family.owner_openid != openid:
            return fail('只有家庭创建者可以移除成员')
        target_openid = body.get('openid')
        if not target_openid or target_openid == openid:
            return fail('参数错误，无法移除该成员')
        User.objects.filter(openid=target_openid, family=family).update(family=None)
        return ok({'family': format_family(family)})

    return fail('未知操作：%s' % action)


# ============ /api/bill ============

@require_POST
def bill_api(request):
    body = json_body(request)
    openid = current_openid(request)
    action = body.get('action')

    if not openid:
        return fail('获取用户身份失败')

    user = User.objects.filter(openid=openid).first()
    if user is None:
        return fail('用户不存在，请重新进入小程序')

    if action == 'add':
        bill_type = 'income' if body.get('type') == 'income' else 'expense'
        amount = round2(body.get('amount'))
        if amount <= 0:
            return fail('请输入正确的金额')
        day = parse_date(body.get('date')) or datetime.now().date()
        bill = Bill.objects.create(
            user_openid=openid,
            family_id=user.family_id,
            nick_name=user.nick_name or '微信用户',
            avatar_url=user.avatar_url or '',
            type=bill_type,
            amount=amount,
            category=str(body.get('category') or '其他')[:10],
            remark=str(body.get('remark') or '')[:50],
            date=day,
            month=day.strftime('%Y-%m'),
        )
        return ok({'_id': bill.id})

    if action == 'remove':
        bill_id = body.get('id')
        if not bill_id:
            return fail('参数错误')
        try:
            bill = Bill.objects.filter(id=int(bill_id)).first()
        except (TypeError, ValueError):
            bill = None
        if bill is None:
            return fail('账单不存在或已被删除')
        if bill.user_openid != openid:
            return fail('只能删除自己记录的账单')
        bill.delete()
        return ok({'_id': bill_id})

    if action == 'overview':
        return _overview(body, user)

    if action == 'total':
        agg = Bill.objects.filter(user_openid=openid).aggregate(
            expense=Sum('amount', filter=Q(type='expense')),
            income=Sum('amount', filter=Q(type='income')),
            count=Count('id'),
        )
        return ok({
            'expense': round2(agg['expense']),
            'income': round2(agg['income']),
            'count': agg['count'],
        })

    return fail('未知操作：%s' % action)


def _overview(body, user):
    scope = 'mine' if body.get('scope') == 'mine' else 'family'
    start = parse_date(body.get('startDate'))
    end = parse_date(body.get('endDate'))
    if start is None or end is None:
        return fail('缺少日期范围')

    base = {
        'scope': scope,
        'hasFamily': bool(user.family_id),
        'familyId': user.family_id or '',
        'summary': {'expense': 0, 'income': 0, 'balance': 0, 'count': 0},
        'daily': [],
        'categories': [],
        'bills': [],
    }

    # 家庭视图但未加入家庭时，直接返回空数据
    if scope == 'family' and not user.family_id:
        return ok(base)

    queryset = Bill.objects.filter(date__gte=start, date__lte=end)
    if scope == 'mine':
        queryset = queryset.filter(user_openid=user.openid)
    else:
        queryset = queryset.filter(family_id=user.family_id)

    # 汇总走数据库聚合，不再受单次拉取条数上限影响
    totals = queryset.aggregate(
        expense=Sum('amount', filter=Q(type='expense')),
        income=Sum('amount', filter=Q(type='income')),
        count=Count('id'),
    )
    total_expense = round2(totals['expense'])
    total_income = round2(totals['income'])

    # 每日趋势
    daily_map = {}
    for row in (queryset.values('date')
                .annotate(
                    expense=Sum('amount', filter=Q(type='expense')),
                    income=Sum('amount', filter=Q(type='income')),
                )
                .order_by('date')):
        daily_map[str(row['date'])] = {
            'expense': round2(row['expense']),
            'income': round2(row['income']),
        }

    daily = []
    for day in build_date_list(start, end):
        item = daily_map.get(day) or {'expense': 0, 'income': 0}
        daily.append({
            'date': day,
            'label': str(int(day[8:10])),
            'expense': round2(item['expense']),
            'income': round2(item['income']),
        })

    # 分类占比（只统计支出，取前 6）
    categories = []
    for row in (queryset.filter(type='expense')
                .values('category')
                .annotate(amount=Sum('amount'))
                .order_by('-amount')[:6]):
        amount = round2(row['amount'])
        categories.append({
            'name': row['category'],
            'amount': amount,
            'percent': int(math.floor(amount / total_expense * 100 + 0.5)) if total_expense > 0 else 0,
        })

    # 明细列表
    bills = []
    for bill in queryset.order_by('-date', '-id')[:MAX_LIST]:
        bills.append({
            '_id': bill.id,
            'userOpenid': bill.user_openid,
            'nickName': bill.nick_name or '微信用户',
            'avatarUrl': bill.avatar_url or '',
            'type': bill.type,
            'amount': round2(bill.amount),
            'category': bill.category,
            'remark': bill.remark,
            'date': str(bill.date),
            'createTimeMs': int(bill.create_time.timestamp() * 1000),
        })

    base['summary'] = {
        'expense': total_expense,
        'income': total_income,
        'balance': round2(total_income - total_expense),
        'count': totals['count'],
    }
    base['daily'] = daily
    base['categories'] = categories
    base['bills'] = bills
    return ok(base)
