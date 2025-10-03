from django import forms
from .models import Application

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

        # 半休または時間休の場合、終了日を開始日と同じにする
        if leave_type in [Application.LeaveType.AM_HALF, Application.LeaveType.PM_HALF, Application.LeaveType.TIME]:
            if start_date:
                cleaned_data['end_date'] = start_date
        
        return cleaned_data