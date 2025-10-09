from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.db.models import Count
from django.core.exceptions import ValidationError

from .forms import ApplicationForm
from .models import LeaveBalance, Application
from .services.fiscal_year_service import get_current_fiscal_year
from .services.application_service import create_application, create_cancellation_request, AssignmentError
from .services.approval_service import process_approval_action, InvalidActionError


User = get_user_model()

def dev_login_view(request):
    """開発用のモックログインビュー"""
    if not settings.DEBUG:
        raise Http404

    if request.method == "POST":
        user_id = request.POST.get("user_id")
        try:
            user = User.objects.get(pk=user_id)
            # パスワード検証なしで強制的にログインさせる
            login(request, user)
            # 今は仮置きに'/'
            return redirect("leaves:dashboard") 
        except User.DoesNotExist:
            pass # 後で作る

    # 全ユーザーをリストアップ
    users = User.objects.order_by('employee_id')
    return render(request, 'leaves/dev_login.html', {'users': users})


@login_required
def dashboard_view(request):
    """ダッシュボード（ホーム画面）ビュー"""
    user = request.user
    current_fiscal_year = get_current_fiscal_year() 

    # 1. 休暇残高の取得
    balance = LeaveBalance.objects.filter(user=user, year=current_fiscal_year).first()

    # 2. 自身の申請状況サマリー
    application_summary = (
        user.applications.filter(start_date__year=current_fiscal_year)
        .values('status')
        .annotate(count=Count('status'))
    )
    summary_counts = {item['status']: item['count'] for item in application_summary}
    
    # テンプレートで直接ループできるリストを作成
    summary_list = []
    for status_value, status_display in Application.Status.choices:
        summary_list.append({
            'display': status_display,
            'count': summary_counts.get(status_value, 0)
        })

    # 3. 承認待ちタスクの件数
    pending_approvals_count = Application.objects.filter(
        current_approver=user, 
        status=Application.Status.APPLYING
    ).count()

    context = {
        'balance': balance,
        'summary_list': summary_list,
        'pending_approvals_count': pending_approvals_count,
    }
    return render(request, 'leaves/dashboard.html', context)

def logout_view(request):
    """ログアウト処理ビュー"""
    logout(request)
    return redirect('dev_login') # ログアウト後は開発用ログイン画面に遷移

@login_required
def application_create_view(request):
    """休暇申請の作成ビュー"""
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            try:
                # ビジネスロジックをサービス関数に委譲
                create_application(
                    applicant=request.user, 
                    form_data=form.cleaned_data, 
                    post_data=request.POST
                )
                messages.success(request, '休暇申請を送信しました。')
                return redirect('leaves:dashboard')
            except AssignmentError as e:
                # サービスから返されたエラーをユーザーに表示
                messages.error(request, str(e))
            except ValidationError as e:
                # サービスのバリデーションエラーをフォームのエラーとして表示
                # e.messageは単一の文字列、e.messagesはリスト
                messages.error(request, e.message if hasattr(e, 'message') else e.messages[0])
    else:
        form = ApplicationForm()

    return render(request, 'leaves/application_form.html', {'form': form})

@login_required
def approval_task_list_view(request):
    """承認待ちタスクの一覧ビュー"""
    pending_applications = Application.objects.filter(
        current_approver=request.user,
        status=Application.Status.APPLYING
    ).order_by('created_at')
    
    context = {
        'pending_applications': pending_applications,
    }
    return render(request, 'leaves/approval_task_list.html', context)

@login_required
def application_detail_view(request, pk: int):
    """申請詳細ビュー"""
    application = get_object_or_404(Application, pk=pk)
    histories = application.approval_histories.all().order_by('timestamp')

    if request.method == 'POST':
        action = request.POST.get("action")
        comment = request.POST.get("comment", "")

        # 差し戻し・却下の場合はコメントが必須
        if action in ['remand', 'reject'] and not comment:
            messages.error(request, "差し戻し、または却下する場合はコメントが必須です。")
        else:
            try:
                process_approval_action(application, request.user, action, comment)
                messages.success(request, f"申請ID:{application.pk}を{action}しました。")
                return redirect('leaves:approval_list')
            except InvalidActionError as e:
                messages.error(request, str(e))

    context = {
        'application': application,
        'histories': histories,
        'is_current_approver': application.current_approver == request.user,
    }
    return render(request, 'leaves/application_detail.html', context)

@login_required
def request_cancellation_view(request, pk: int):
    """取消申請を処理するビュー (画面なし)"""
    if request.method != 'POST':
        return redirect('leaves:dashboard') 

    target_application = get_object_or_404(Application, pk=pk)
    try:
        # サービスを呼び出して取消申請を作成
        create_cancellation_request(user=request.user, target_application=target_application)
        messages.success(request, f"申請ID:{pk}の取消申請を送信しました。")
    except (PermissionError, ValueError) as e:
        messages.error(request, str(e))
    
    # 処理後は、元の申請詳細画面に戻る
    return redirect('leaves:application_detail', pk=pk)

@login_required
def application_history_view(request):
    """申請履歴一覧ビュー"""
    # ユーザー自身の申請を、新しいものから順に取得
    applications = Application.objects.filter(
        applicant=request.user
    ).order_by('-created_at')

    context = {
        'applications': applications,
    }
    return render(request, 'leaves/application_history.html', context)