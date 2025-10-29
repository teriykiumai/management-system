from datetime import date
from leaves.models import Application, User

def is_user_on_leave(user: User, check_date: date) -> bool:
    """
    指定されたユーザが指定された日に承認済みの休暇を取得しているか判定する
    Args:
        user (User): チェック対象のユーザ
        check_date (date): 対象の日付
    Returns:
        bool: 休暇中であればTrue
    """

    # 承認済みかつ取り消されていな申請
    is_on_leave = Application.objects.filter(
        applicant=user,
        status=Application.Status.APPROVED,
        start_date__lte=check_date,
        end_date__gte=check_date,
    ).exclude(
        application_type=Application.ApplicationType.CANCEL
    ).exists()

    return is_on_leave