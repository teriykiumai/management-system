from datetime import timedelta

from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, get_user_model, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse
from django.db.models import Count, Q
from django.core.exceptions import ValidationError

from .forms import ApplicationForm
from .models import LeaveBalance, Application, Assignment, Department, Group, Team, Role
from .services.fiscal_year_service import get_current_fiscal_year
from .services.application_service import create_application, create_cancellation_request, AssignmentError, resubmit_remanded_application, cancel_remanded_application
from .services.approval_service import process_approval_action, InvalidActionError
from .services.calendar_service import get_visible_applications_for_user


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
        form = ApplicationForm(request.POST, user=request.user)
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
        form = ApplicationForm(user=request.user)

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
    ).exclude( # 取り消し申請の取り消しはできないようにするため
        application_type=Application.ApplicationType.CANCEL
    ).order_by('-created_at')

    leave_type = request.GET.get('leave_type') or None
    status = request.GET.get('status') or None
    year = request.GET.get('year') or None
    month = request.GET.get('month') or None

    # フィルタ
    if leave_type:
        applications = applications.filter(leave_type=leave_type)
    if status:
        applications = applications.filter(status=status)
    if year:
        applications = applications.filter(start_date__year=year)
    if month:
        applications = applications.filter(start_date__month=month)

    # フィルタを適用した結果を最終的に並び替える
    applications = applications.order_by('-created_at')

# テンプレートに渡すためのフィルタ項目
    context = {
        'applications': applications,
        'leave_types': Application.LeaveType.choices,
        'statuses': Application.Status.choices,
        # 過去10年分をフィルタ候補として渡す
        'years': range(timezone.now().year, timezone.now().year - 10, -1),
        'months': range(1, 13),
        # 現在選択されているフィルタ値をテンプレートに戻す
        'current_filters': {
            'leave_type': leave_type,
            'status': status,
            'year': int(year) if year else None,
            'month': int(month) if month else None,
        }
    }
    return render(request, 'leaves/application_history.html', context)

@login_required
def calendar_view(request):
    """カレンダー表示ページのビュー"""
    try:
        primary_assignment = Assignment.objects.get(user=request.user, is_primary=True)
        view_scope = primary_assignment.role.view_scope
    except Assignment.DoesNotExist:
        primary_assignment = None
        view_scope = Role.ViewScope.TEAM # 所属がなければTEAM相当

    # フィルタの選択肢を権限に応じて絞り込むロジック
    departments = Department.objects.none()
    groups = Group.objects.none()
    teams = Team.objects.none()

    if view_scope == Role.ViewScope.ALL:
        departments = Department.objects.all()
        groups = Group.objects.all()
        teams = Team.objects.all()
    elif view_scope == Role.ViewScope.DEPARTMENT and primary_assignment:
        groups = Group.objects.filter(department=primary_assignment.department)
        teams = Team.objects.filter(group__department=primary_assignment.department)
    elif view_scope == Role.ViewScope.GROUP and primary_assignment:
        teams = Team.objects.filter(group=primary_assignment.group)
    
    context = {
        'departments': departments,
        'groups': groups,
        'teams': teams,
        'leave_types': Application.LeaveType.choices,
        'view_scope': view_scope,
    }
    return render(request, 'leaves/calendar.html', context)

@login_required
def leave_events_api(request):
    """カレンダー用の休暇イベントデータを返すAPIビュー"""
    department_id = request.GET.get('department')
    group_id = request.GET.get('group')
    team_id = request.GET.get('team')
    leave_type = request.GET.get('leave_type')
    only_me = request.GET.get('only_me') == 'true'

    # サービスにパラメータを渡す
    applications = get_visible_applications_for_user(
        request.user, only_me, department_id, group_id, team_id, leave_type
    ).prefetch_related('time_leave_slots')

    # 色分け用のカラーマップを定義
    color_map = {
        Application.LeaveType.PAID: '#58D68D',      # 有給休暇 
        Application.LeaveType.AM_HALF: '#5DADE2',   # 午前半休 
        Application.LeaveType.PM_HALF: "#ED963A",   # 午後休 
        Application.LeaveType.TIME: "#9158F9",      # 時間休 
        Application.LeaveType.SPECIAL: '#333333',   # 無給休暇
    }

    events = []
    for app in applications:
        color = color_map.get(app.leave_type, '#a0a0a0')
        
        if app.leave_type == Application.LeaveType.TIME:
                # --- 1. 時間休の場合 ---
                # 申請された各時間帯を、個別のイベントとして追加
            for slot in app.time_leave_slots.all():
                events.append({
                    'title': f"{app.applicant.last_name} (時間休)",
                    'start': f"{app.start_date.isoformat()}T{slot.start_time.isoformat()}",
                    'end': f"{app.end_date.isoformat()}T{slot.end_time.isoformat()}",
                    'backgroundColor': color,
                    'borderColor': color,
                })

        elif app.leave_type == Application.LeaveType.AM_HALF:
            # --- 2. 午前休の場合 ---
            events.append({
                'title': f"{app.applicant.last_name} (午前休)",
                'start': f"{app.start_date.isoformat()}T08:30:00", 
                'end': f"{app.start_date.isoformat()}T12:00:00",   
                'backgroundColor': color,
                'borderColor': color,
            })
        elif app.leave_type == Application.LeaveType.PM_HALF:
            # --- 3. 午後休の場合 ---
            events.append({
                'title': f"{app.applicant.last_name} (午後休)",
                'start': f"{app.start_date.isoformat()}T13:00:00",
                'end': f"{app.start_date.isoformat()}T17:30:00",   
                'backgroundColor': color,
                'borderColor': color,
            })
        else:
            # --- 4. それ以外（有給休暇など）の場合 ---
            events.append({
                'title': f"{app.applicant.last_name} ({app.get_leave_type_display()})",
                'start': app.start_date,
                'end': app.end_date + timedelta(days=1),
                'backgroundColor': color,
                'borderColor': color,
                'allDay': True
            })
            
    return JsonResponse(events, safe=False)

@login_required
def application_edit_view(request, pk: int):
    """差し戻された申請の編集・再提出ビュー"""
    application = get_object_or_404(Application, pk=pk, applicant=request.user, status=Application.Status.REMANDED)
    
    if request.method == 'POST':
        form = ApplicationForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                # 再提出サービスを呼び出し
                resubmit_remanded_application(application, form.cleaned_data, request.POST)
                messages.success(request, f"申請ID:{pk}を再提出しました。")
                return redirect('leaves:application_history')
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        # 既存の申請内容をフォームにセット
        form = ApplicationForm(instance=application, user=request.user)

    context = {
        'form': form,
        'is_edit_mode': True, # テンプレートに編集モードであることを伝える
    }
    return render(request, 'leaves/application_form.html', context)

@login_required
def cancel_remanded_view(request, pk: int):
    """差し戻された申請の取り消し処理ビュー"""
    if request.method != 'POST':
        return redirect('leaves:application_history')

    application = get_object_or_404(Application, pk=pk)
    try:
        cancel_remanded_application(request.user, application)
        messages.success(request, f"申請ID:{pk}を取り消しました。")
    except (PermissionError, ValueError) as e:
        messages.error(request, str(e))
    
    return redirect('leaves:application_history')