from datetime import date

def get_current_fiscal_year(today: date = None) -> int:
    """
    現在の日付に対応する会計年度を返す.
    会計年度は前年の12月16日から当年の12月15日までとする.
    Args:
        today (date, optional): 基準日. Defaults to date.today().
    Returns:
        int: 会計年度 (例: 2024).
    """
    if today is None:
        today = date.today()

    # 12/16以降は翌年度扱い
    if today.month == 12 and today.day >= 16:
        return today.year + 1
    else:
        # それ以前は、前年の12/16から始まる年度なので、
        # 年度名は今年の西暦と同じになる
        # 例: 2025/10/07 -> 2025年度 (2024/12/16開始)、2025/12/20 -> 2026年度(2025/12/16開始)
        return today.year
    
def get_fiscal_year_for_date(target_date: date) -> int:
    """
    指定された日付が属する会計年度を返す.
    ロジックは get_current_fiscal_year と同じ.
    """
    if target_date.month == 12 and target_date.day >= 16:
        return target_date.year + 1
    else:
        return target_date.year