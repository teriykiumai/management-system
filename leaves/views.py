from django.shortcuts import render, redirect
from django.contrib.auth import login, get_user_model, logout
from django.conf import settings
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Count

from .models import LeaveBalance, Application
from .services.fiscal_year import get_current_fiscal_year


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