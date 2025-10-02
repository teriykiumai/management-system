from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings 

from .constants import MINUTES_PER_WORK_DAY


# -----------------------------------------------------------------------------
# ユーザーモデル
# -----------------------------------------------------------------------------
class CustomUserManager(BaseUserManager):
    """employee_id を使ってユーザーを作成するためのマネージャー"""
    def create_user(self, employee_id, password=None, **extra_fields):
        """通常ユーザーを作成する"""
        if not employee_id:
            raise ValueError('The Employee ID must be set')
        
        # extra_fields から email を取得して正規化
        email = self.normalize_email(extra_fields.pop('email', None))
        
        # Userモデルのインスタンスを作成
        user = self.model(employee_id=employee_id, email=email, **extra_fields)
        
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_id, password=None, **extra_fields):
        """スーパーユーザーを作成する"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(employee_id, password, **extra_fields)

class User(AbstractUser):
    """カスタムユーザーモデル"""
    # usernameフィールドを無効化
    username = None
    
    employee_id = models.CharField(
        max_length=50, unique=True, verbose_name="社員ID番号"
    )
    hire_date = models.DateField(verbose_name="入社日", null=True, blank=True)

    # employee_idをログインに使用する
    objects = CustomUserManager()
    USERNAME_FIELD = 'employee_id'
    REQUIRED_FIELDS = ['email', 'last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.employee_id})"

    class Meta:
        verbose_name = "ユーザー"
        verbose_name_plural = "ユーザー"

class PreApprovedUser(models.Model):
    """事前承認済みユーザーリスト"""
    employee_id = models.CharField(max_length=50, unique=True, verbose_name="社員ID番号")
    is_registered = models.BooleanField(default=False, verbose_name="登録完了フラグ")

    def __str__(self):
        return self.employee_id
    
    class Meta:
        verbose_name = "事前承認ユーザー"
        verbose_name_plural = "事前承認ユーザー"

# -----------------------------------------------------------------------------
# 組織構造モデル
# -----------------------------------------------------------------------------

class Department(models.Model):
    """部署マスター"""
    department_id = models.AutoField(primary_key=True, verbose_name="部署ID")
    department_name = models.CharField(max_length=100, unique=True, verbose_name="部署名")

    def __str__(self):
        return self.department_name
        
    class Meta:
        verbose_name = "部署"
        verbose_name_plural = "部署"

class Group(models.Model):
    """グループマスター"""
    group_id = models.AutoField(primary_key=True, verbose_name="グループID")
    group_name = models.CharField(max_length=100, verbose_name="グループ名")
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="groups", verbose_name="所属部署"
    )

    def __str__(self):
        return f"{self.department.department_name} - {self.group_name}"

    class Meta:
        verbose_name = "グループ"
        verbose_name_plural = "グループ"

class Team(models.Model):
    """チームマスター"""
    team_id = models.AutoField(primary_key=True, verbose_name="チームID")
    team_name = models.CharField(max_length=100, verbose_name="チーム名")
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="teams", verbose_name="所属グループ"
    )

    def __str__(self):
        return f"{self.group.group_name} - {self.team_name}"

    class Meta:
        verbose_name = "チーム"
        verbose_name_plural = "チーム"

# -----------------------------------------------------------------------------
# 役職・所属モデル
# -----------------------------------------------------------------------------

class Role(models.Model):
    """役職マスター"""
    class ViewScope(models.TextChoices):
        TEAM = 'TEAM', 'チーム'
        GROUP = 'GROUP', 'グループ'
        DEPARTMENT = 'DEPARTMENT', '部署'
        ALL = 'ALL', '全社'

    role_id = models.AutoField(primary_key=True, verbose_name="役職ID")
    role_name = models.CharField(max_length=100, unique=True, verbose_name="役職名")
    role_level = models.IntegerField(verbose_name="階層レベル", help_text="承認ルート決定に使用。数値が小さいほど下位。")
    
    deputy_role = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="代理役職", help_text="この役職の代理承認を行う役職"
    )
    
    view_scope = models.CharField(
        max_length=20, choices=ViewScope.choices, default=ViewScope.TEAM,
        verbose_name="カレンダー表示範囲"
    )
    is_approval_endpoint = models.BooleanField(
        default=False, verbose_name="承認ルート終点フラグ",
        help_text="この役職が部署等の承認ルートの終点となる場合にTrue"
    )

    approval_order = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name="承認順序", help_text="1次承認、2次承認など。数値が小さい順に承認される。"
    )


    def __str__(self):
        return self.role_name
        
    class Meta:
        verbose_name = "役職"
        verbose_name_plural = "役職"

class Assignment(models.Model):
    """所属情報（ユーザーと組織・役職の関連付け）"""
    assignment_id = models.AutoField(primary_key=True, verbose_name="所属ID")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assignments", verbose_name="ユーザー")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, verbose_name="部署")
    # 部長など、グループやチームに所属しない場合を考慮してnullを許可
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True, verbose_name="グループ")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, null=True, blank=True, verbose_name="チーム")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, verbose_name="役職") # 役職は保護
    is_primary = models.BooleanField(default=True, verbose_name="主務フラグ")
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subordinates", verbose_name="上長"
    )

    def __str__(self):
        return f"{self.user} - {self.role} @ {self.department}"
        
    class Meta:
        verbose_name = "所属情報"
        verbose_name_plural = "所属情報"

# -----------------------------------------------------------------------------
# 休暇残高モデル
# -----------------------------------------------------------------------------

class LeaveBalance(models.Model):
    """年度ごとの休暇残高"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_balances", verbose_name="ユーザー"
    )
    year = models.PositiveIntegerField(verbose_name="年度")
    
    # 残高はすべて「分」単位で管理
    carried_over_minutes = models.PositiveIntegerField(default=0, verbose_name="前年繰越（分）")
    granted_minutes = models.PositiveIntegerField(default=0, verbose_name="今年度付与（分）")
    used_minutes = models.PositiveIntegerField(default=0, verbose_name="合計利用実績（分）")
    
    # 半休・時間休の利用実績
    half_leave_used_count = models.PositiveSmallIntegerField(default=0, verbose_name="半休利用回数")
    time_leave_used_minutes = models.PositiveIntegerField(default=0, verbose_name="時間休利用実績（分）")

    @property
    def total_balance_minutes(self) -> int:
        """残高の合計時間（分）を計算して返す"""
        return (self.carried_over_minutes + self.granted_minutes) - self.used_minutes

    @property
    def remaining_days(self) -> int:
        """残りの合計日数"""
        return self.total_balance_minutes // MINUTES_PER_WORK_DAY

    @property
    def remaining_minutes_part(self) -> int:
        """日数で換算した後の、残りの分数"""
        return self.total_balance_minutes % MINUTES_PER_WORK_DAY

    # --- 各項目の日数/分換算 ---
    @property
    def carried_over_days(self) -> int:
        return self.carried_over_minutes // MINUTES_PER_WORK_DAY

    @property
    def carried_over_minutes_part(self) -> int:
        return self.carried_over_minutes % MINUTES_PER_WORK_DAY

    @property
    def granted_days(self) -> int:
        return self.granted_minutes // MINUTES_PER_WORK_DAY

    @property
    def granted_minutes_part(self) -> int:
        return self.granted_minutes % MINUTES_PER_WORK_DAY

    @property
    def used_days(self) -> int:
        return self.used_minutes // MINUTES_PER_WORK_DAY

    @property
    def used_minutes_part(self) -> int:
        return self.used_minutes % MINUTES_PER_WORK_DAY
    
    def __str__(self):
        return f"{self.user} - {self.year}年度"

    class Meta:
        verbose_name = "休暇残高"
        verbose_name_plural = "休暇残高"
        # ユーザーと年度の組み合わせでユニークにする（複合主キーの代わり）
        constraints = [
            models.UniqueConstraint(fields=['user', 'year'], name='unique_user_year_balance')
        ]

# -----------------------------------------------------------------------------
# 申請関連モデル
# -----------------------------------------------------------------------------

class Application(models.Model):
    """休暇申請モデル"""
    class ApplicationType(models.TextChoices):
        """申請種別"""
        NEW = 'NEW', '新規申請'
        CANCEL = 'CANCEL', '取消申請'

    class LeaveType(models.TextChoices):
        """休暇種別"""
        PAID = 'PAID', '有給休暇'
        AM_HALF = 'AM_HALF', '午前半休'
        PM_HALF = 'PM_HALF', '午後半休'
        TIME = 'TIME', '時間休'
        SPECIAL = 'SPECIAL', '慶弔休暇'
        CHILDCARE = 'CHILDCARE', '育児休暇'
        NURSING = 'NURSING', '介護休暇'
        SICK = 'SICK', '病欠'
        ABSENCE = 'ABSENCE', '欠勤'
        OTHER = 'OTHER', 'その他休暇'

    class Status(models.TextChoices):
        """申請ステータス"""
        APPLYING = 'APPLYING', '申請中'
        APPROVED = 'APPROVED', '承認済'
        REJECTED = 'REJECTED', '却下'
        REMANDED = 'REMANDED', '差し戻し'
        CANCELLED = 'CANCELLED', '取り消し済'

    app_id = models.AutoField(primary_key=True, verbose_name="申請ID")
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="applications", verbose_name="申請者"
    )
    applicant_assignment = models.ForeignKey(
        Assignment, on_delete=models.PROTECT, verbose_name="申請時所属"
    )
    
    application_type = models.CharField(
        max_length=10, choices=ApplicationType.choices, default=ApplicationType.NEW, verbose_name="申請種別"
    )
    # 取消申請の場合、どの申請を対象とするかを記録
    cancellation_target = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="cancellation_applications", verbose_name="取消対象申請"
    )
    # 申請フォームの構成要素
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices, verbose_name="休暇種別")
    start_date = models.DateField(verbose_name="開始日")
    end_date = models.DateField(verbose_name="終了日")
    reason = models.TextField(max_length=200, blank=True, verbose_name="申請理由")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.APPLYING, verbose_name="ステータス")
    current_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approval_tasks", verbose_name="現在の承認者"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    # 一斉取得日から作成された申請の場合、どの日付マスターに紐づくかを記録
    company_leave_day = models.ForeignKey(
        'CompanyLeaveDay', on_delete=models.SET_NULL, null=True, blank=True,
        related_name="applications", verbose_name="関連一斉取得日"
    )
    approval_route = models.JSONField(verbose_name="承認ルート", null=True, blank=True)

    def __str__(self):
        return f"ID:{self.app_id} {self.applicant} ({self.get_leave_type_display()})"

    class Meta:
        verbose_name = "休暇申請"
        verbose_name_plural = "休暇申請"

class TimeLeaveSlot(models.Model):
    """時間休の時間帯"""
    slot_id = models.AutoField(primary_key=True, verbose_name="スロットID")
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="time_leave_slots", verbose_name="関連申請"
    )
    start_time = models.TimeField(verbose_name="開始時刻")
    end_time = models.TimeField(verbose_name="終了時刻")
    calculated_minutes = models.PositiveIntegerField(verbose_name="計算後の取得時間(分)")

    def __str__(self):
        return f"AppID:{self.application.app_id} ({self.start_time} - {self.end_time})"

    class Meta:
        verbose_name = "時間休スロット"
        verbose_name_plural = "時間休スロット"

class ApprovalHistory(models.Model):
    """承認履歴"""
    class Action(models.TextChoices):
        APPLY = 'APPLY', '申請'
        APPROVE = 'APPROVE', '承認'
        REJECT = 'REJECT', '却下'
        REMAND = 'REMAND', '差し戻し'
        CANCEL = 'CANCEL', '取り消し'

    history_id = models.AutoField(primary_key=True, verbose_name="履歴ID")
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="approval_histories", verbose_name="関連申請"
    )
    # 実際に処理した人
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="processed_histories", verbose_name="処理者"
    )
    # 代理承認の場合、本来の承認者を記録
    original_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="original_histories", verbose_name="本来の承認者"
    )
    
    action = models.CharField(max_length=10, choices=Action.choices, verbose_name="アクション")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="処理日時")
    comment = models.TextField(max_length=200, blank=True, verbose_name="コメント")

    def __str__(self):
        return f"AppID:{self.application.app_id} by {self.approver} ({self.get_action_display()})"

    class Meta:
        verbose_name = "承認履歴"
        verbose_name_plural = "承認履歴"

# -----------------------------------------------------------------------------
# マスターデータ・設定モデル
# -----------------------------------------------------------------------------
class SystemSetting(models.Model):
    """年度ごとのシステム設定 (年次時間休の上限時間設定)"""
    year = models.PositiveIntegerField(primary_key=True, verbose_name="年度")
    time_leave_limit_minutes = models.PositiveIntegerField(default=480, verbose_name="時間休上限（分）") # 8時間 = 480分

    def __str__(self):
        return f"{self.year}年度設定"

    class Meta:
        verbose_name = "システム設定"
        verbose_name_plural = "システム設定"

class CompanyLeaveDay(models.Model):
    """全社一斉有給取得日マスター"""
    day_id = models.AutoField(primary_key=True, verbose_name="ID")
    leave_date = models.DateField(unique=True, verbose_name="日付")
    fiscal_year = models.PositiveIntegerField(verbose_name="対象年度")
    description = models.CharField(max_length=100, verbose_name="摘要")
    is_active = models.BooleanField(default=True, verbose_name="有効フラグ")

    def __str__(self):
        return f"{self.leave_date} ({self.description})"

    class Meta:
        verbose_name = "一斉有給取得日"
        verbose_name_plural = "一斉有給取得日"

class Holiday(models.Model):
    """祝日マスター"""
    holiday_date = models.DateField(primary_key=True, verbose_name="日付")
    description = models.CharField(max_length=100, verbose_name="祝日名")

    def __str__(self):
        return f"{self.holiday_date} ({self.description})"

    class Meta:
        verbose_name = "祝日"
        verbose_name_plural = "祝日"

class BreakTime(models.Model):
    """休憩時間マスター"""
    break_time_id = models.AutoField(primary_key=True, verbose_name="ID")
    # userとdepartmentが両方NULLの場合は全社共通ルール
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name="break_times", verbose_name="対象ユーザー"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, null=True, blank=True,
        related_name="break_times", verbose_name="対象部署"
    )
    start_time = models.TimeField(verbose_name="開始時刻")
    end_time = models.TimeField(verbose_name="終了時刻")
    description = models.CharField(max_length=100, verbose_name="摘要")


    def __str__(self):
        target = "全社共通"
        if self.user:
            target = str(self.user)
        elif self.department:
            target = str(self.department)
        return f"{target}: {self.start_time}-{self.end_time}"

    class Meta:
        verbose_name = "休憩時間"
        verbose_name_plural = "休憩時間"