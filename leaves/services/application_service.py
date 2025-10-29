from datetime import date

from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from typing import Dict, Any, Tuple

from leaves.models import Application, Assignment, ApprovalHistory, LeaveBalance
from leaves.constants import MINUTES_PER_WORK_DAY, MINUTES_PER_WORK_HALF_DAY

from .approval_route_service import generate_approval_route
from .time_leave_service import (
    validate_time_leave_request, 
    calculate_time_leave_minutes, 
    save_time_leave_slots,
    parse_time_slots,
)
from .fiscal_year_service import get_fiscal_year_for_date
from .workday_service import count_workdays
from .balance_service import validate_sufficient_balance

User = get_user_model()

class AssignmentError(Exception):
    pass

def _prepare_application_data(applicant: User, form_data: Dict, post_data: Dict) -> Dict[str, Any]: # type: ignore
    """DBに保存する前の、申請に関連する全てのデータを準備・計算する.
    Args:
        applicant (User): 申請者.
        form_data (Dict): フォームの入力情報の辞書, 開始期間や終了期間、休暇種類をとる.
        post_data (Dict): 消費時間や承認ルートの情報を含めたオブジェクト.
    Raises:
        AssignmentError: _description_
        AssignmentError: _description_
    Returns:
        Dict[str, Any]: 承認者、承認ルート、総消費時間のデータ
    """
    
    # 1. 基本情報を準備
    leave_type = form_data.get('leave_type')
    start_date = form_data.get('start_date')
    end_date = form_data.get('end_date')

    # 2. 所属情報と承認ルートを準備
    try:
        primary_assignment = Assignment.objects.get(user=applicant, is_primary=True)
    except Assignment.DoesNotExist:
        raise AssignmentError('ユーザーの主務の所属情報が見つかりません。')

    approval_route_users = generate_approval_route(primary_assignment, date.today())
    if not approval_route_users:
        raise AssignmentError('承認ルートを生成できませんでした。管理者に連絡してください。')
    
    # 消費時間(分)を計算
    duration_minutes = 0
    processed_slots = [] # 時間休の場合の計算済みスロット

    if leave_type == Application.LeaveType.TIME:
        time_slots_data = parse_time_slots(post_data) # time_leave_serviceのヘルパーを一時的に借用
        duration_minutes, processed_slots = calculate_time_leave_minutes(applicant, time_slots_data)
    elif leave_type in [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF]:
        duration_minutes = MINUTES_PER_WORK_HALF_DAY
    elif leave_type == Application.LeaveType.PAID:
        workdays = count_workdays(start_date, end_date)
        duration_minutes = workdays * MINUTES_PER_WORK_DAY

    return {
        "applicant": applicant,
        "applicant_assignment": primary_assignment,
        "approval_route": [user.pk for user in approval_route_users],
        "current_approver": approval_route_users[0],
        "duration_minutes": duration_minutes,
        "processed_slots": processed_slots, # 計算済みスロットも渡す
        **form_data
    }

def _validate_application_request(applicant: User, prepared_data: Dict, post_data: Dict): # type: ignore
    """
    準備されたデータを用いて、申請前の全てのバリデーションを実行する.
    """
    # 1. 残高レコードの存在チェック
    try:
        leave_fiscal_year = get_fiscal_year_for_date(prepared_data['start_date'])
        LeaveBalance.objects.get(user=applicant, year=leave_fiscal_year)
    except LeaveBalance.DoesNotExist:
        raise ValidationError(
            f"{leave_fiscal_year}年度の休暇残高レコードが存在しません。"
            "管理者が年度更新処理を行うまで、この年度の休暇は申請できません。"
        )

    # 2. 時間休固有のバリデーション (専用関数を呼び出す)
    if prepared_data['leave_type'] == Application.LeaveType.TIME:
        validate_time_leave_request(applicant, post_data)

    # 3. 残高不足チェック
    validate_sufficient_balance(applicant, prepared_data['duration_minutes'])


@transaction.atomic
def create_application(applicant: User, form_data: dict, post_data: dict) -> Application: # type: ignore
    """ユーザーとフォームデータから休暇申請を作成する (司令塔)."""
    # 申請に必要なデータを全て準備・計算する
    prepared_data = _prepare_application_data(applicant, form_data, post_data)

    # 準備したデータを使って、全てのバリデーションを実行する
    _validate_application_request(applicant, prepared_data, post_data)

    # バリデーションを全て通過したら、DBに保存する
    processed_slots = prepared_data.pop('processed_slots') # 後で使うので取り出す
    application = Application.objects.create(**prepared_data)
    
    # 時間休の場合はスロットも保存
    if application.leave_type == Application.LeaveType.TIME:
        save_time_leave_slots(application, processed_slots)
    
    ApprovalHistory.objects.create(
        application=application,
        approver=applicant,
        action=ApprovalHistory.Action.APPLY,
        comment="新規申請"
    )
    return application


def create_cancellation_request(user: User, target_application: Application) -> Application: # pyright: ignore[reportInvalidTypeForm]
    """
    承認済みの休暇申請に対する取消申請を作成する.
    Args:
        user (User): 取消を申請するユーザー.
        target_application (Application): 取り消しの対象となる、承認済みの申請.
    Returns:
        Application: 新しく作成された取消申請オブジェクト.
    Raises:
        PermissionError: 申請者本人でないユーザーが取消を試みた場合.
        ValueError: 承認済みでない申請を取り消そうとした場合や、既に取消申請中の場合.
    """
    if target_application.applicant != user:
        raise PermissionError("自分の申請しか取り消せません。")
    if target_application.status != Application.Status.APPROVED:
        raise ValueError("承認済みの申請しか取り消せません。")
    if target_application.application_type == Application.ApplicationType.CANCEL:
        raise ValueError("取消申請をさらに取り消すことはできません。")
    
    # 既に同じ申請に対する未完了の取消申請があればエラー
    if Application.objects.filter(
        application_type=Application.ApplicationType.CANCEL,
        cancellation_target=target_application,
        status__in=[Application.Status.APPLYING, Application.Status.REMANDED]
    ).exists():
        raise ValueError("この休暇に対する取消申請は既に提出されています。")

    # 元の申請の承認ルートと最初の承認者をコピー
    approval_route_ids = target_application.approval_route
    current_approver_id = approval_route_ids[0] if approval_route_ids else None

    cancellation_app = Application.objects.create(
        applicant=user,
        applicant_assignment=target_application.applicant_assignment,
        application_type=Application.ApplicationType.CANCEL,
        cancellation_target=target_application,
        # 取消申請の内容は元の申請をコピー
        leave_type=target_application.leave_type,
        start_date=target_application.start_date,
        end_date=target_application.end_date,
        reason=f"【取消申請】\n{target_application.reason}",
        duration_minutes=target_application.duration_minutes,
        # 承認ルートも元の申請と同じものを設定
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


@transaction.atomic
def resubmit_remanded_application(application: Application, form_data: dict, post_data: dict) -> Application:
    """
    差し戻された申請を編集し、再提出する.

    Args:
        application (Application): 差し戻された申請オブジェクト.
        form_data (dict): 検証済みのフォームデータ.
        post_data (dict): 時間休を含む生のPOSTデータ.
    """
    # 1. 差し戻しを行った承認者を探す
    last_remand = ApprovalHistory.objects.filter(
        application=application, action=ApprovalHistory.Action.REMAND
    ).latest('timestamp')
    remanding_approver = last_remand.approver

    # 2. 申請内容を更新
    application.leave_type = form_data['leave_type']
    application.start_date = form_data['start_date']
    application.end_date = form_data['end_date']
    application.reason = form_data['reason']

    # 3. 消費時間(分)を再計算
    duration_minutes = 0
    leave_type = application.leave_type

    if leave_type == Application.LeaveType.TIME:
        # 既存の時間休スロットを一度全て削除
        application.time_leave_slots.all().delete()
        
        # 時間休のバリデーションを実行
        validate_time_leave_request(application.applicant, post_data)
        
        # 時間を計算
        time_slots_data = parse_time_slots(post_data)
        total_minutes, processed_slots = calculate_time_leave_minutes(application.applicant, time_slots_data)
        duration_minutes = total_minutes
        
        # スロットを保存
        save_time_leave_slots(application, processed_slots)
    # 半休
    elif leave_type in [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF]:
        duration_minutes = MINUTES_PER_WORK_HALF_DAY
    # 全休
    elif leave_type == Application.LeaveType.PAID:
        workdays = count_workdays(application.start_date, application.end_date)
        duration_minutes = workdays * MINUTES_PER_WORK_DAY
    
    # ステータスと次の承認者を設定
    application.status = Application.Status.APPLYING
    application.current_approver = remanding_approver
    application.save()

    # 再申請の履歴を記録
    ApprovalHistory.objects.create(
        application=application,
        approver=application.applicant,
        action=ApprovalHistory.Action.RESUBMIT,
        comment="編集して再申請"
    )
    # 総消費時間を登録
    application.duration_minutes = duration_minutes

    return application

def cancel_remanded_application(user: User, application: Application): # pyright: ignore[reportInvalidTypeForm]
    """
    差し戻された申請を、申請者本人が取り消す.
    """
    if application.applicant != user:
        raise PermissionError("自分の申請しか取り消せません。")
    if application.status != Application.Status.REMANDED:
        raise ValueError("差し戻された申請しか取り消せません。")

    application.status = Application.Status.CANCELLED
    application.save()

    ApprovalHistory.objects.create(
        application=application,
        approver=user,
        action=ApprovalHistory.Action.CANCEL,
        comment="差し戻し後に申請者が取り消し"
    )
