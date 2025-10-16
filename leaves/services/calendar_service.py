from django.db.models import QuerySet
from leaves.models import Application, Assignment, User, Role

def get_visible_applications_for_user(
    user: User, 
    only_me: bool = False,
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
# ユーザーの権限に基づき、閲覧が「許可」されているユーザーのIDリストを取得する.
    allowed_user_ids = {user.pk}
    if not only_me:
        try:
            primary_assignment = Assignment.objects.get(user=user, is_primary=True)
            view_scope = primary_assignment.role.view_scope

            if view_scope == Role.ViewScope.ALL:
                allowed_user_ids.update(User.objects.filter(is_active=True).values_list('pk', flat=True))
            elif view_scope == Role.ViewScope.DEPARTMENT and primary_assignment.department:
                allowed_user_ids.update(Assignment.objects.filter(department=primary_assignment.department).values_list('user__pk', flat=True))
            elif view_scope == Role.ViewScope.GROUP and primary_assignment.group:
                allowed_user_ids.update(Assignment.objects.filter(group=primary_assignment.group).values_list('user__pk', flat=True))
            elif view_scope == Role.ViewScope.TEAM and primary_assignment.team:
                allowed_user_ids.update(Assignment.objects.filter(team=primary_assignment.team).values_list('user__pk', flat=True))
        except Assignment.DoesNotExist:
            pass # 所属情報がない場合は自分の予定のみ

    # ユーザーが選択した「フィルタ」に合致するユーザーのIDリストを取得する.
    filtered_assignments = Assignment.objects.all()
    if department_id:
        filtered_assignments = filtered_assignments.filter(department_id=department_id)
    if group_id:
        filtered_assignments = filtered_assignments.filter(group_id=group_id)
    if team_id:
        filtered_assignments = filtered_assignments.filter(team_id=team_id)

    # もし部署・グループ・チームのいずれかのフィルタが指定されていれば、その結果のユーザーIDリストを使用する.
    # 何も指定されていなければ、全ユーザーが対象となる.
    if department_id or group_id or team_id:
        filtered_user_ids = set(filtered_assignments.values_list('user_id', flat=True))
    else:
        filtered_user_ids = set(User.objects.filter(is_active=True).values_list('pk', flat=True))

    # ステップ3: 「許可されたユーザー」と「フィルタされたユーザー」の共通集合（AND）を取る.
    final_user_ids = list(allowed_user_ids & filtered_user_ids)

    # ステップ4: 最終的なユーザーIDリストと休暇種別で申請を絞り込む.
    final_query = Application.objects.filter(
        status=Application.Status.APPROVED,
        applicant_id__in=final_user_ids
    ).exclude(
        application_type=Application.ApplicationType.CANCEL
    ).select_related('applicant')

    if leave_type:
        final_query = final_query.filter(leave_type=leave_type)
        
    return final_query.distinct()