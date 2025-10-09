from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms import ValidationError

from leaves.models import Application, Assignment, ApprovalHistory, User, LeaveBalance
from leaves.constants import MINUTES_PER_WORK_DAY
from leaves.services.fiscal_year import get_fiscal_year_for_date
from .approval_route_service import generate_approval_route
from .time_leave_service import process_time_leave_slots
from .workday_service import count_workdays


User = get_user_model()

class AssignmentError(Exception):
    """所属情報が見つからない場合のエラー"""
    pass

@transaction.atomic
def create_application(applicant: User, form_data: dict, post_data: dict) -> Application: # type: ignore
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
        leave_start_date = form_data.get('start_date')
        if not leave_start_date:
            raise ValidationError("開始日が指定されていません。")

        leave_fiscal_year = get_fiscal_year_for_date(leave_start_date)
        
        LeaveBalance.objects.get(user=applicant, year=leave_fiscal_year)
    except LeaveBalance.DoesNotExist:
        raise ValidationError(
            f"{leave_fiscal_year}年度の休暇残高レコードが存在しません。"
            "管理者が年度更新処理を行うまで、この年度の休暇は申請できません。"
        )

    try:
        primary_assignment = Assignment.objects.get(user=applicant, is_primary=True)
    except Assignment.DoesNotExist:
        raise AssignmentError('ユーザーの主務の所属情報が見つかりません。')

    # 1. 承認ルートを生成する
    approval_route_users = generate_approval_route(primary_assignment)
    if not approval_route_users:
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

    # 時間休なら、時間帯データを処理する
    leave_type = application.leave_type
    half_leaves = [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF]
    total_minutes = 0
    if leave_type == Application.LeaveType.TIME:
        total_minutes = process_time_leave_slots(application, post_data)
    elif leave_type in half_leaves:
        # 仕様書通り、半休は一律4時間(240分)として計算
        total_minutes = MINUTES_PER_WORK_DAY // 2
    elif leave_type == Application.LeaveType.PAID:
        # 終日の有給休暇は、労働日数 × 1日の労働時間（分）
        workdays = count_workdays(application.start_date, application.end_date)
        total_minutes = workdays * MINUTES_PER_WORK_DAY

    application.duration_minutes = total_minutes
    application.save(update_fields=['duration_minutes'])

    # 3. 最初の承認履歴（本人の申請アクション）を記録
    ApprovalHistory.objects.create(
        application=application,
        approver=applicant,
        action=ApprovalHistory.Action.APPLY,
        comment="新規申請"
    )
    
    return application

def create_cancellation_request(user: User, target_application: Application) -> Application:
    """承認済みの休暇申請に対する取消申請を作成する.
    Args:
        applicant (User): 申請者.
        target_application (Application): 取り消ししたい申請オブジェクト.
    Returns:
        Application: 作成された取り消し申請オブジェクト.
    Raises:
        PermissionError: ユーザに紐づかない申請を取り消ししようとした場合.
        ValueError: ステータスが承認済みでない場合
    """
    if target_application.applicant != user:
        raise PermissionError("自分の申請しか取り消せません。")
    if target_application.status != Application.Status.APPROVED:
        raise ValueError("承認済みの申請しか取り消せません。")
    
    # 既に同じ申請に対する未完了の取消申請があればエラー
    if Application.objects.filter(
        application_type=Application.ApplicationType.CANCEL,
        cancellation_target=target_application,
        status__in=[Application.Status.APPLYING, Application.Status.REMANDED]
    ).exists():
        raise ValueError("この休暇に対する取消申請は既に提出されています。")

    approval_route_ids = target_application.approval_route
    current_approver_id = approval_route_ids[0] if approval_route_ids else None

    cancellation_app = Application.objects.create(
        applicant=user,
        applicant_assignment=target_application.applicant_assignment,
        application_type=Application.ApplicationType.CANCEL,
        cancellation_target=target_application,
        leave_type=target_application.leave_type,
        start_date=target_application.start_date,
        end_date=target_application.end_date,
        reason=f"【取消申請】\n{target_application.reason}",
        duration_minutes=target_application.duration_minutes,
        approval_route=approval_route_ids,
        current_approver_id=current_approver_id,
    )

    ApprovalHistory.objects.create(
        application=cancellation_app,
        approver=user,
        action=ApprovalHistory.Action.APPLY,
        comment="取消申請"
    )

    return cancellation_app