from leaves.models import BreakTime, User, Assignment

def get_applicable_break_times(user: User) -> list[BreakTime]:
    """
    指定されたユーザーに適用される休憩時間のリストを優先度順に取得する.
    優先度: 1. 個人設定 -> 2. 部署設定 -> 3. 全社共通設定
    """
    # 1. 個人設定を探す
    personal_breaks = BreakTime.objects.filter(user=user)
    if personal_breaks.exists():
        return list(personal_breaks)

    # 2. 部署設定を探す (ユーザーの主務の所属部署)
    primary_assignment = Assignment.objects.filter(user=user, is_primary=True).first()
    if primary_assignment and primary_assignment.department:
        department_breaks = BreakTime.objects.filter(department=primary_assignment.department)
        if department_breaks.exists():
            return list(department_breaks)

    # 3. 全社共通設定を探す
    company_breaks = BreakTime.objects.filter(user__isnull=True, department__isnull=True)
    return list(company_breaks)