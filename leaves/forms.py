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