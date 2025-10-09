from datetime import date, timedelta

from django.forms import ValidationError
from dateutil.relativedelta import relativedelta

from leaves.constants import MINUTES_PER_WORK_DAY
from leaves.models import Application, LeaveBalance, User
from .fiscal_year import get_current_fiscal_year

class BalanceUpdateError(Exception):
    pass

def consume_balance(application: Application):
    """申請で消費される休暇残高を更新する."""
    if application.duration_minutes == 0:
        return # 消費する時間がない場合は何もしない

    try:
        fiscal_year = application.start_date.year
        balance, _ = LeaveBalance.objects.get_or_create(
            user=application.applicant,
            year=fiscal_year,
        )
        # 休暇タイプにより更新フィールドを分ける
        balance.used_minutes += application.duration_minutes
        if application.leave_type in [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF]:
            balance.half_leave_used_count += 1
        elif application.leave_type == Application.LeaveType.TIME:
            balance.time_leave_used_minutes += application.duration_minutes

    except Exception as e:
        raise BalanceUpdateError(f"残高の消費処理に失敗しました: {e}")

def refund_balance(application: Application):
    """取り消された申請の休暇残高を返還する."""
    if application.duration_minutes == 0:
        return # 返還する時間がない場合は何もしない

    try:
        fiscal_year = application.start_date.year
        balance = LeaveBalance.objects.get(
            user=application.applicant,
            year=fiscal_year
        )
        balance.used_minutes -= application.duration_minutes
        balance.save()
    except LeaveBalance.DoesNotExist:
        raise BalanceUpdateError("返還対象の残高レコードが見つかりません。")
    except Exception as e:
        raise BalanceUpdateError(f"残高の返還処理に失敗しました: {e}")
    

def calculate_newly_granted_minutes(user: User, fiscal_year: int) -> int:
    """
    勤続年数に基づいて、指定された年度の新規付与時間（分）を計算する.
    管理コマンド'process_fiscal_year_update'で使うロジック
    Args:
        user (User): ユーザオブジェクト
        fiscal_year (int): 計算する年度
    Returns:
        int: 新たに給付する年間休暇時間
    """
    # 年度開始日時点での勤続年数を計算
    fiscal_year_start_date = date(fiscal_year - 1, 12, 16)
    if not user.hire_date:
        return 0
        
    r = relativedelta(fiscal_year_start_date, user.hire_date)
    years_of_service = r.years

    # 仕様書 年間付与 のロジック
    if years_of_service < 1:
        days = 0 # 1年未満はバッチでの付与なし (初年度付与ルールで別途対応)
    elif years_of_service == 1:
        days = 10
    elif years_of_service == 2:
        days = 11
    else:
        # 3年以上: 10日 + 2日 * (勤続年数 - 2)
        days = 10 + 2 * (years_of_service - 2)

    # 上限20日を適用
    granted_days = min(days, 20)
    
    return granted_days * MINUTES_PER_WORK_DAY