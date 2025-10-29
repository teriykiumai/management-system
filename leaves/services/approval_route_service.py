from typing import List
from datetime import date

from django.db.models import Q

from leaves.models import Assignment, Role, User
from .user_service import is_user_on_leave


def _find_approver_in_organization(assignment: Assignment, approval_order: int) -> User | None:
    """
    指定された組織階層と承認順序に基づいて承認者を探すヘルパー関数.
    申請者のチーム内で、承認順序1番(チームリーダーの人を探すなど.
    Args:
        assignment (Assignment): 申請者の所属情報.
        approval_order (int): 探したい承認者の順序 (1, 2, 3...).
    Returns:
        User | None: 見つかった承認者. 見つからなければNone.
    """
    target_role = Role.objects.filter(approval_order=approval_order).first()
    if not target_role:
        return None

    # 承認順序に応じて検索範囲（チーム/グループ/部署）を決定
    query = Q(role=target_role)
    if approval_order == 1: # 1次承認者 -> チーム
        if not assignment.team: return None
        query &= Q(team=assignment.team)
    elif approval_order == 2: # 2次承認者 -> グループ
        if not assignment.group: return None
        query &= Q(group=assignment.group)
    elif approval_order == 3: # 3次承認者 -> 部署
        if not assignment.department: return None
        query &= Q(department=assignment.department)
    else:
        return None
    
    return Assignment.objects.filter(query).first()

def _find_delegate(original_approver_assignment: Assignment) -> Assignment | None:
    """    
    本来の承認者の代理を探す.
    代理役職を持ち、同じ組織単位に属するユーザーを返す.
    Args:
        original_approver_assignment (Assignment): 元の承認者
    Returns:
        Assignment | None: 元の承認者が不在なら代理承認者を返す
    """
    original_role = original_approver_assignment.role
    deputy_role = original_role.deputy_role
    if not deputy_role:
        return None

    # 承認者の階層に応じて、代理を探す範囲（チーム/グループ/部署）を決定
    query = Q(role=deputy_role)
    if original_role.approval_order == 1: # チームリーダーの代理
        query &= Q(team=original_approver_assignment.team)
    elif original_role.approval_order == 2: # グループ長の代理
        query &= Q(group=original_approver_assignment.group)
    elif original_role.approval_order == 3: # 部長の代理
        query &= Q(department=original_approver_assignment.department)
    else:
        return None
    
    return Assignment.objects.filter(query).first()

def _find_final_approvers() -> List[User]:
    """固定の最終承認者（業務部・勤怠管理担当）を探す."""
    # 仕様書に基づき、特定の役職を持つユーザーを最終承認者とする
    # is_approval_endpoint=Trueかつ、最も階層レベルが高い役職などを基準に探す
    try:
        # この役職名はマスターデータに存在する必要があります
        final_approver_role = Role.objects.get(role_name="業務部・勤怠管理担当")
        assignments = Assignment.objects.filter(role=final_approver_role)
        return [assignment.user for assignment in assignments]
    except Role.DoesNotExist:
        return []
    

def generate_approval_route(applicant_assignment: Assignment, check_date: date) -> List[User]:
    """
    申請者の所属情報と指定日に基づいて、承認ルートを動的に生成する.
    承認者が休暇中の場合は代理承認者を設定する.
    Args:
        applicant_assignment (Assignment): 申請者の主務の所属情報.
        check_date (date): 承認者が休暇中かチェックするための日付（申請日）
    Returns:
        List[User]: 承認者のリスト.
    """
    unique_approvers = {}
    applicant_role_level = applicant_assignment.role.role_level

    # 1. 組織階層に基づく承認者を取得 (1次 -> 2次 -> 3次)
    for order in [1, 2, 3]:
        approver_assignment = _find_approver_in_organization(applicant_assignment, order)
        
        if approver_assignment:
            actual_approver = approver_assignment.user
            
            # 1a. 本来の承認者が休暇中かチェック
            if is_user_on_leave(actual_approver, check_date):
                # 1b. 休暇中なら代理を探す
                delegate_assignment = _find_delegate(approver_assignment)
                if delegate_assignment:
                    delegate_user = delegate_assignment.user
                    # 1c. 代理も休暇中でないかチェック
                    if not is_user_on_leave(delegate_user, check_date):
                        actual_approver = delegate_user # 承認者を代理に差し替え
                    else:
                        actual_approver = None # 代理も不在ならスキップ
                else:
                    actual_approver = None # 代理が見つからなければスキップ
            
            # 最終的に決まった承認者を追加
            if actual_approver and actual_approver != applicant_assignment.user and actual_approver.is_active:
                if approver_assignment.role.role_level > applicant_role_level:
                    unique_approvers.setdefault(actual_approver.pk, actual_approver)
                
                if approver_assignment.role.is_approval_endpoint:
                    break
    
    # 2. Assignmentに指定された直属の上長(manager)を追加
    if applicant_assignment.manager:
        manager = applicant_assignment.manager
        
        if manager and manager != applicant_assignment.user and manager.is_active:
            unique_approvers.setdefault(manager.pk, manager)

    # 3. 固定の最終承認者を追加
    for final_approver in _find_final_approvers():
        if final_approver and final_approver != applicant_assignment.user and final_approver.is_active:
            unique_approvers.setdefault(final_approver.pk, final_approver)

    return list(unique_approvers.values())