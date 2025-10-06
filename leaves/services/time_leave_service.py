from datetime import datetime, time
from typing import List, Dict
from django.core.exceptions import ValidationError
from leaves.models import Application, TimeLeaveSlot

def _parse_time_slots(post_data: Dict) -> List[Dict[str, time]]:
    """POSTデータから 'start_time_X', 'end_time_X' をパースして時間帯のリストを返す."""
    slots = []
    i = 0
    while True:
        start_key = f'start_time_{i}'
        end_key = f'end_time_{i}'
        if start_key in post_data and end_key in post_data:
            start_time = datetime.strptime(post_data[start_key], '%H:%M').time()
            end_time = datetime.strptime(post_data[end_key], '%H:%M').time()
            slots.append({'start_time': start_time, 'end_time': end_time})
            i += 1
        else:
            break
    return slots

def _validate_time_slots(time_slots_data: List[Dict[str, time]]):
    """
    パースされた時間帯リストのバリデーションを行う.
    ルール違反があればValidationErrorを送出する.
    """
    if not time_slots_data:
        raise ValidationError("時間休を申請する場合、少なくとも1つの時間帯を入力してください。")

    for slot in time_slots_data:
        start_time = slot['start_time']
        end_time = slot['end_time']
        
        # この時点では休憩時間を考慮しない単純な分数でチェック
        duration = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time)).total_seconds() / 60

        if duration <= 0:
            raise ValidationError(f"終了時刻は開始時刻より後に設定してください ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})。")
        
        if duration % 60 != 0:
            raise ValidationError(
                f"各時間帯は1時間（60分）単位で申請してください。"
                f"問題のあった時間帯: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({int(duration)}分)"
            )

def _calculate_and_save_slots(application: Application, time_slots_data: List[Dict[str, time]]) -> int:
    """休憩時間を考慮して分数を計算し、DBに保存する."""
    total_minutes = 0
    for slot in time_slots_data:
        # TODO: 休憩時間を考慮した計算ロジックをここに実装
        start_dt = datetime.combine(datetime.today(), slot['start_time'])
        end_dt = datetime.combine(datetime.today(), slot['end_time'])
        calculated_minutes = int((end_dt - start_dt).total_seconds() / 60)

        TimeLeaveSlot.objects.create(
            application=application,
            start_time=slot['start_time'],
            end_time=slot['end_time'],
            calculated_minutes=calculated_minutes
        )
        total_minutes += calculated_minutes
    return total_minutes

# --- 全体を統括する公開関数 ---
def process_time_leave_slots(application: Application, post_data: Dict) -> int:
    """
    POSTデータから時間休スロットを処理し、DBに保存して合計時間を返す.
    """
    time_slots_data = _parse_time_slots(post_data)
    
    _validate_time_slots(time_slots_data)
    
    total_minutes = _calculate_and_save_slots(application, time_slots_data)
    
    return total_minutes