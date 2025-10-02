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

    # 今年の年度開始日 (例: 2025-12-16)
    fiscal_year_start_for_this_year = date(today.year, 12, 16)

    if today >= fiscal_year_start_for_this_year:
        # 今年の12/16以降なら、来年度の扱い
        return today.year + 1
    else:
        # 今年の12/15以前なら、今年の年度の扱い
        return today.year