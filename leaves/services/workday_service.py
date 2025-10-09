from datetime import date, timedelta
from leaves.models import Holiday

def count_workdays(start_date: date, end_date: date) -> int:
    """
    指定された期間内の労働日数（土日・祝日を除く）をカウントする.
    Args:
        start_date (date): 開始日.
        end_date (date): 終了日.
    Returns:
        int: 労働日数.
    """
    if start_date > end_date:
        return 0

    # 期間内の祝日を一度に取得してセットに格納（高速なルックアップのため）
    holidays = set(
        Holiday.objects.filter(holiday_date__range=(start_date, end_date))
        .values_list('holiday_date', flat=True)
    )

    workday_count = 0
    current_date = start_date
    while current_date <= end_date:
        # 月曜日=0, 日曜日=6
        # 曜日が土日(5, 6)でなく、かつ祝日でない場合
        if current_date.weekday() < 5 and current_date not in holidays:
            workday_count += 1
        current_date += timedelta(days=1)
        
    return workday_count