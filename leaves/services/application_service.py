from django.contrib.auth import get_user_model
from leaves.models import Application, Assignment, ApprovalHistory

User = get_user_model()

class AssignmentError(Exception):
    """所属情報が見つからない場合のエラー"""
    pass

def create_application(applicant: User, form_data: dict) -> Application:
    """
    ユーザーとフォームデータから休暇申請を作成する.
    Args:
        applicant (User): 申請者.
        form_data (dict): 検証済みのフォームデータ.
    Returns:
        Application: 作成された休暇申請オブジェクト.
    Raises:
        AssignmentError: ユーザーの主務の所属が見つからない場合.
    """
    # 1. 申請者の主務の所属情報を取得
    try:
        primary_assignment = Assignment.objects.get(user=applicant, is_primary=True)
    except Assignment.DoesNotExist:
        raise AssignmentError('ユーザーの主務の所属情報が見つかりません。')

    # 2. 申請オブジェクトを作成
    application = Application.objects.create(
        applicant=applicant,
        applicant_assignment=primary_assignment,
        **form_data
    )

    # 3. 最初の承認履歴（本人の申請アクション）を記録
    ApprovalHistory.objects.create(
        application=application,
        approver=applicant,
        action=ApprovalHistory.Action.APPLY,
        comment="新規申請"
    )
    
    # TODO: ここで承認ルート生成ロジックを呼び出す

    return application