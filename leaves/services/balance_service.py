from django.forms import ValidationError

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
    

def get_active_balance(user: User) -> LeaveBalance | None:
    """
    ユーザーの現在有効な残高レコードを取得する.
    今年度のレコードがあればそれを返し、なければ前年度のものを探す.
    """
    current_fiscal_year = get_current_fiscal_year()
    
    # 1. 今年度の残高レコードを探す
    balance = LeaveBalance.objects.filter(user=user, year=current_fiscal_year).first()
    if balance:
        return balance
        
    # 2. なければ、前年度の残高レコードを探す
    previous_fiscal_year = current_fiscal_year - 1
    balance = LeaveBalance.objects.filter(user=user, year=previous_fiscal_year).first()
    return balance

def validate_sufficient_balance(user: User, required_minutes: int):
    """休暇残高が足りているか検証する."""
    if required_minutes <= 0:
        return # 消費がなければチェック不要

    balance = get_active_balance(user)

    if not balance or balance.total_balance_minutes < required_minutes:
        available_minutes = balance.total_balance_minutes if balance else 0
        raise ValidationError(
            f"休暇残高が不足しています。"
            f"申請時間: {required_minutes}分, "
            f"現在の残高: {available_minutes}分"
        )