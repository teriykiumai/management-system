from django.utils import timezone

from leaves.models import Application, ApprovalHistory, User, LeaveBalance


class InvalidActionError(Exception):
    pass

def process_approval_action(application: Application, approver: User, action: str, comment: str = ""):
    """
    承認アクションを処理し、申請のステータスや次の承認者を更新する.

    Args:
        application (Application): 対象の申請.
        approver (User): アクションを実行した承認者.
        action (str): 'approve', 'remand', 'reject' のいずれか.
        comment (str, optional): 差し戻し・却下時のコメント.
    """
    # 1. 承認アクションの履歴を作成
    history_action_map = {
        'approve': ApprovalHistory.Action.APPROVE,
        'remand': ApprovalHistory.Action.REMAND,
        'reject': ApprovalHistory.Action.REJECT,
    }
    if action not in history_action_map:
        raise InvalidActionError("無効なアクションです。")

    ApprovalHistory.objects.create(
        application=application,
        approver=approver,
        action=history_action_map[action],
        comment=comment
    )

    # 2. アクションに応じて申請ステータスを更新
    if action == 'approve':
        # 次の承認者を探す
        current_approver_index = application.approval_route.index(approver.pk)
        if current_approver_index < len(application.approval_route) - 1:
            # 次の承認者がいる場合
            next_approver_id = application.approval_route[current_approver_index + 1]
            application.current_approver_id = next_approver_id
        else:
            # 自分が最終承認者の場合
            application.current_approver = None
            application.status = Application.Status.APPROVED
            # 残高消費ロジック
            try:
                fiscal_year = application.start_date.year
                balance, created = LeaveBalance.objects.get_or_create(
                    user=application.applicant,
                    year=fiscal_year,
                )
                # 使用分を加算
                balance.used_minutes += application.duration_minutes
                balance.save()
            except Exception as e:
                raise InvalidActionError(f"残高の更新に失敗しました: {e}")
    
    elif action == 'remand':
        application.status = Application.Status.REMANDED
        application.current_approver = None # 差し戻し後は承認者がいない状態に
    
    elif action == 'reject':
        application.status = Application.Status.REJECTED
        application.current_approver = None

    application.save()