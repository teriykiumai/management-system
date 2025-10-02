from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, PreApprovedUser, Department, Group, Team, Role, Assignment,
    LeaveBalance, Application, TimeLeaveSlot, ApprovalHistory,
    SystemSetting, CompanyLeaveDay, Holiday, BreakTime
)

# -----------------------------------------------------------------------------
# Adminクラスの定義
# -----------------------------------------------------------------------------

class CustomUserAdmin(UserAdmin):
    """Userモデルの管理者画面設定"""
    # ユーザー編集画面で表示するフィールド
    fieldsets = (
        (None, {'fields': ('employee_id', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'hire_date')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    # ユーザー作成画面で表示するフィールド
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('employee_id', 'last_name', 'first_name', 'email', 'hire_date', 'password'),
        }),
    )
    # 一覧画面に表示するフィールド
    list_display = ('employee_id', 'last_name', 'first_name', 'email', 'is_staff')
    # 検索対象のフィールド
    search_fields = ('employee_id', 'last_name', 'first_name')
    # 絞り込みに使うフィールド
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')
    # ログインIDとしてemployee_idを使うためorderingを上書き
    ordering = ('employee_id',)

class DepartmentAdmin(admin.ModelAdmin):
    search_fields = ('department_name',)

class GroupAdmin(admin.ModelAdmin):
    search_fields = ('group_name',)
    autocomplete_fields = ('department',) # Group追加時にDepartmentを検索できるように

class TeamAdmin(admin.ModelAdmin):
    search_fields = ('team_name',)
    autocomplete_fields = ('group',) # Team追加時にGroupを検索できるように

class RoleAdmin(admin.ModelAdmin):
    search_fields = ('role_name',)

class AssignmentAdmin(admin.ModelAdmin):
    """Assignmentモデルの管理者画面設定"""
    list_display = ('user', 'department', 'group', 'team', 'role', 'is_primary')
    list_filter = ('department', 'role', 'is_primary')
    search_fields = ('user__employee_id', 'user__last_name', 'user__first_name')
    autocomplete_fields = ('user', 'department', 'group', 'team', 'role')

class ApplicationAdmin(admin.ModelAdmin):
    """Applicationモデルの管理者画面設定"""
    list_display = ('app_id', 'applicant', 'leave_type', 'status', 'start_date', 'end_date', 'current_approver')
    list_filter = ('status', 'leave_type', 'start_date')
    search_fields = ('applicant__employee_id', 'applicant__last_name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('applicant', 'applicant_assignment', 'cancellation_target', 'current_approver')

class LeaveBalanceAdmin(admin.ModelAdmin):
    """LeaveBalanceモデルの管理者画面設定"""
    list_display = ('user', 'year', 'carried_over_minutes', 'granted_minutes', 'used_minutes')
    search_fields = ('user__employee_id', 'user__last_name')
    autocomplete_fields = ('user',)



# -----------------------------------------------------------------------------
# モデルの登録
# -----------------------------------------------------------------------------

# 上記でカスタマイズしたAdminクラス
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(Role, RoleAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Assignment, AssignmentAdmin)
admin.site.register(Application, ApplicationAdmin)
admin.site.register(LeaveBalance, LeaveBalanceAdmin)


# デフォルトの定義モデルでの登録
admin.site.register(PreApprovedUser)
admin.site.register(TimeLeaveSlot)
admin.site.register(ApprovalHistory)
admin.site.register(SystemSetting)
admin.site.register(CompanyLeaveDay)
admin.site.register(Holiday)
admin.site.register(BreakTime)