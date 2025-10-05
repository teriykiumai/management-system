from django.contrib.auth import get_user_model

from leaves.models import Application, Assignment, ApprovalHistory, User
from .approval_route_service import generate_approval_route
from .time_leave_service import process_time_leave_slots

User = get_user_model()

class AssignmentError(Exception):
    """所属情報が見つからない場合のエラー"""
    pass

def create_application(applicant: User, form_data: dict, post_data: dict) -> Application:
    """
    ユーザーとフォームデータから休暇申請を作成する.
    Args:
        applicant (User): 申請者.
        form_data (dict): 検証済みのフォームデータ.
        post_data (dict): 時間休データを含む生のPOSTデータ.
    Returns:
        Application: 作成された休暇申請オブジェクト.
    Raises:
        AssignmentError: ユーザーの主務の所属が見つからない場合.
    """
    try:
        primary_assignment = Assignment.objects.get(user=applicant, is_primary=True)
    except Assignment.DoesNotExist:
        raise AssignmentError('ユーザーの主務の所属情報が見つかりません。')

    # 1. 承認ルートを生成する
    approval_route_users = generate_approval_route(primary_assignment)
    if not approval_route_users:
        # 承認ルートが見つからない場合もエラーハンドリングが必要
        raise AssignmentError('承認ルートを生成できませんでした。管理者に連絡してください。')
    
    # 承認ルートをユーザーIDのリストとして保存
    approval_route_ids = [user.pk for user in approval_route_users]
    # 最初の承認者を現在の承認者として設定
    current_approver = approval_route_users[0]

    # 2. 申請オブジェクトを作成
    application = Application.objects.create(
        applicant=applicant,
        applicant_assignment=primary_assignment,
        approval_route=approval_route_ids,   # 生成した承認ルートを保存
        current_approver=current_approver, # 最初の承認者をセット
        **form_data
    )

    # もし時間休なら、時間帯データを処理する
    if application.leave_type == Application.LeaveType.TIME:
        total_minutes = process_time_leave_slots(application, post_data)
        application.duration_minutes = total_minutes
        application.save()
    else:
        # TODO: 時間休以外の合計時間も計算するロジック (例: 1日 = 480分)
        pass

    # 3. 最初の承認履歴（本人の申請アクション）を記録
    ApprovalHistory.objects.create(
        application=application,
        approver=applicant,
        action=ApprovalHistory.Action.APPLY,
        comment="新規申請"
    )
    
    # TODO: ここで承認ルート生成ロジックを呼び出す

    return application