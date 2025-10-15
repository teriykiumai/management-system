from datetime import timedelta, date

from django import forms

from .models import Application, Holiday

class ApplicationForm(forms.ModelForm):
    """休暇申請を作成するためのフォーム"""
    
    class Meta:
        model = Application
        fields = ['leave_type', 'start_date', 'end_date', 'reason']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) # viewから渡ってきたuser
        super().__init__(*args, **kwargs)
        self.fields['leave_type'].label = "休暇種別"
        self.fields['start_date'].label = "開始日"
        self.fields['end_date'].label = "終了日"
        self.fields['reason'].label = "申請理由"

    def clean(self):
        """フォーム全体のバリデーション"""
        cleaned_data = super().clean()
        leave_type = cleaned_data.get('leave_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        # 1. 開始日と終了日の順序チェック
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("終了日は開始日より後の日付を選択してください。")

        # 期間内の祝日を一度だけ取得
        holidays = set(
            Holiday.objects.filter(holiday_date__range=(start_date, end_date))
            .values_list('holiday_date', flat=True)
        )
        
        # 2. 休暇申請日に所定休日が含まれるかの確認
        if leave_type == Application.LeaveType.PAID:
            # 有給休暇の場合：開始日と終了日のみチェック
            if start_date.weekday() >= 5 or start_date in holidays:
                raise forms.ValidationError(f"有給休暇の開始日({start_date.strftime('%Y-%m-%d')})を休日または祝日に設定することはできません。")
            if end_date.weekday() >= 5 or end_date in holidays:
                raise forms.ValidationError(f"有給休暇の終了日({end_date.strftime('%Y-%m-%d')})を休日または祝日に設定することはできません。")
        else:
            # 有給休暇以外の場合：期間内の全日程をチェック
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() >= 5 or current_date in holidays:
                    leave_type_display_dict = dict(self.fields['leave_type'].choices)
                    leave_type_display = leave_type_display_dict.get(leave_type, '')
                    raise forms.ValidationError(
                        f"{current_date.strftime('%Y-%m-%d')}は休日または祝日のため、「{leave_type_display}」は申請できません。"
                    )
                current_date += timedelta(days=1)

        # 3. すでに承認済み or ほかの申請で同じ日程で申請しようとしていないか確認, (終日休暇が存在しているか)
        if self.user:
            conflicting_statuses = [Application.Status.APPLYING, Application.Status.APPROVED]
            
            # 申請期間が重複する既存の申請を取得
            overlapping_apps = Application.objects.filter(
                applicant=self.user,
                status__in=conflicting_statuses,
                start_date__lte=end_date,
                end_date__gte=start_date
            )

            if overlapping_apps.exists():
                is_new_app_full_day = (leave_type == Application.LeaveType.PAID)
                
                # 既存の申請に一つでも終日の有給休暇が含まれているか
                has_existing_full_day_app = overlapping_apps.filter(leave_type=Application.LeaveType.PAID).exists()

                # バリデーション1: 今回の申請か、既存の申請のどちらかが終日有給の場合 -> 即エラー
                if is_new_app_full_day or has_existing_full_day_app:
                    raise forms.ValidationError(
                        "指定された期間には、他の休暇（または終日の有給休暇）が既に存在します。"
                    )
                
                # 新規申請が半休の場合のみ
                if leave_type in [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF]:
                    # 重複している既存申請の中に、同じ種類の半休がないかチェック
                    if overlapping_apps.filter(leave_type=leave_type).exists():
                        leave_type_display = dict(self.fields['leave_type'].choices).get(leave_type)
                        raise forms.ValidationError(
                            f"指定された日には、既に同じ「{leave_type_display}」が申請されています。"
                        )
                
        
        # 終日休暇でない場合は開始と終了は同じになるはず
        if leave_type in [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF, Application.LeaveType.TIME]:
            cleaned_data['end_date'] = start_date
        
        return cleaned_data