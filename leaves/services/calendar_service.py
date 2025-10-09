from django.db.models import QuerySet
from leaves.models import Application, Assignment, User, Role

def get_visible_applications_for_user(
    user: User, 
    department_id: str = None, 
    group_id: str = None, 
    team_id: str = None,
    leave_type: str = None
) -> QuerySet[Application]:
    """
    指定されたユーザーの閲覧範囲(view_scope)に基づいて、
    カレンダーに表示すべき休暇申請のクエリセットを返す.
    Args:
        user (User): ログイン中のユーザー.
        department_id (Department): ユーザの所属部署.
        group_id (Group): ユーザの所属部署.
        team_id (Team): ユーザの所属部署.
        leave_type (str): 休暇種類.
    Returns:
        QuerySet[Application]: 表示が許可された休暇申請のクエリセット.
    """
    try:
        primary_assignment = Assignment.objects.get(user=user, is_primary=True)
        view_scope = primary_assignment.role.view_scope
    except Assignment.DoesNotExist:
        # 所属情報がない場合は、自分の申請のみ表示
        view_scope = None

    visible_user_ids = {user.pk} # 少なくとも自分自身は表示

    if view_scope == Role.ViewScope.ALL:
        # 全社のユーザーIDを取得
        visible_user_ids.update(User.objects.filter(is_active=True).values_list('pk', flat=True))
    
    elif view_scope == Role.ViewScope.DEPARTMENT and primary_assignment.department:
        # ログインユーザーと同じ部署のユーザーIDを取得
        visible_user_ids.update(
            Assignment.objects.filter(department=primary_assignment.department)
            .values_list('user__pk', flat=True)
        )

    elif view_scope == Role.ViewScope.GROUP and primary_assignment.group:
        # ログインユーザーと同じグループのユーザーIDを取得
        visible_user_ids.update(
            Assignment.objects.filter(group=primary_assignment.group)
            .values_list('user__pk', flat=True)
        )

    elif view_scope == Role.ViewScope.TEAM and primary_assignment.team:
        # ログインユーザーと同じチームのユーザーIDを取得
        visible_user_ids.update(
            Assignment.objects.filter(team=primary_assignment.team)
            .values_list('user__pk', flat=True)
        )

    # 承認済みで、まだ取り消されていない、かつ表示範囲内のユーザーの申請を取得
    base_query = Application.objects.filter(
        status=Application.Status.APPROVED,
        applicant_id__in=list(visible_user_ids)
    ).exclude(
        application_type=Application.ApplicationType.CANCEL
    ).select_related('applicant')

    if department_id:
        base_query = base_query.filter(applicant__assignments__department_id=department_id)
    if group_id:
        base_query = base_query.filter(applicant__assignments__group_id=group_id)
    if team_id:
        base_query = base_query.filter(applicant__assignments__team_id=team_id)
    if leave_type:
        base_query = base_query.filter(leave_type=leave_type)
        
    return base_query.distinct() # 複数の所属があるユーザーを考慮して重複を除外