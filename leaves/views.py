from django.shortcuts import render, redirect
from django.contrib.auth import login, get_user_model
from django.conf import settings
from django.http import Http404

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
            # ログイン後のリダイレクト先 (今は仮に'/'にしておく)
            return redirect("/") 
        except User.DoesNotExist:
            pass # エラーハンドリングは後で

    # スーパーユーザー以外の全ユーザーをリストアップ
    users = User.objects.filter(is_superuser=False).order_by('employee_id')

    return render(request, 'leaves/dev_login.html', {'users': users})