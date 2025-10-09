from leaves.models import Application, LeaveBalance

class BalanceUpdateError(Exception):
    pass

def consume_balance(application: Application):
    """申請で消費される休暇残高を更新する."""
    if application.duration_minutes == 0:
        return # 消費する時間がない場合は何もしない

    try:
        # TODO: 年度またぎの申請に対応
        fiscal_year = application.start_date.year
        balance, _ = LeaveBalance.objects.get_or_create(
            user=application.applicant,
            year=fiscal_year,
            defaults={'carried_over_minutes': 0, 'granted_minutes': 0}
        )
        balance.used_minutes += application.duration_minutes
        balance.save()
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