from django.core.mail import send_mail
from django.conf import settings
from leaves.models import Application, User

def send_notification_email(subject: str, message: str, recipient: User):
    """
    指定されたユーザーに通知メールを送信する.
    Args:
        subject (str): メールの件名.
        message (str): メールの本文.
        recipient (User): 受信者のユーザーオブジェクト.
    """
    if not recipient.email:
        # メールアドレスが設定されていない場合は何もしない
        return

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient.email],
            fail_silently=False,
        )
    except Exception as e:
        # TODO: ログ出力などのエラーハンドリング
        print(f"メール送信に失敗しました: {e}")

def notify_next_approver(application: Application):
    """次の承認者に承認依頼の通知を送る."""
    if application.current_approver:
        subject = f"【休暇申請システム】承認依頼のお知らせ (申請ID: {application.pk})"
        message = (
            f"{application.current_approver.last_name} 様\n\n"
            f"{application.applicant.last_name}さんから休暇申請が提出されました。\n"
            "システムにログインして内容をご確認の上、承認処理をお願いいたします。\n\n"
            "※このメッセージはシステムから自動で送信されているため返信できません\n"
        )
        send_notification_email(subject, message, application.current_approver)

def notify_applicant_of_final_decision(application: Application):
    """申請の結果を申請者本人に通知する."""
    status_display = application.get_status_display()
    subject = f"【休暇申請システム】申請結果のお知らせ (申請ID: {application.pk})"
    message = (
        f"{application.applicant.last_name} さん"
        f"提出された休暇申請が「{status_display}」となりましたので、お知らせいたします。\n"
        "詳細はシステムにログインしてご確認ください。\n\n"
        "※このメッセージはシステムから自動で送信されているため返信できません\n"
    )
    send_notification_email(subject, message, application.applicant)