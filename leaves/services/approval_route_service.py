from typing import List
from django.db.models import Q

from leaves.models import Assignment, Role, User


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

def generate_approval_route(applicant_assignment: Assignment) -> List[User]:
    """
    申請者の所属情報に基づいて、承認ルートを動的に生成する.
    Args:
        applicant_assignment (Assignment): 申請者の主務の所属情報.
    Returns:
        List[User]: 承認者のリスト.
    """
    unique_approvers = {} # 兼務対応: 同じ承認者が複数回登場しないようにdictで管理

    # 1. 組織階層に基づく承認者を取得 (1次 -> 2次 -> 3次)
    for order in [1, 2, 3]:
        approver_assignment = _find_approver_in_organization(applicant_assignment, order)
        if approver_assignment:
            approver = approver_assignment.user
            approver_role = approver_assignment.role

            # 申請者自身が承認者になるケースは除外
            if approver and approver != applicant_assignment.user:
                unique_approvers[approver.pk] = approver
                # 承認ルートの終点フラグを持つ役職に到達したら探索を終了
                if approver_role and approver_role.is_approval_endpoint:
                    break

    # 2. 固定の最終承認者を追加
    for final_approver in _find_final_approvers():
        if final_approver and final_approver != applicant_assignment.user:
            unique_approvers[final_approver.pk] = final_approver


    return list(unique_approvers.values())