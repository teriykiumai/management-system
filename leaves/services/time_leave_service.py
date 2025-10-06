from datetime import datetime, time
from typing import List, Dict
from leaves.models import Application, TimeLeaveSlot

def _parse_time_slots(post_data: Dict) -> List[Dict[str, time]]:
    """
    POSTデータから 'start_time_X', 'end_time_X' をパースして時間帯のリストを返す.
    """
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

def _calculate_slot_duration(start_time: time, end_time: time) -> int:
    """
    開始時刻と終了時刻から重複する休憩時間を除いた実働時間（分）を計算する.
    """
    #       重複時間を差し引くロジックを実装する.
    
    # 現時点では単純な差分を計算
    start_dt = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)
    duration = (end_dt - start_dt).total_seconds() / 60
    
    # マイナスの場合は0を返す
    return max(0, int(duration))

def process_time_leave_slots(application: Application, post_data: Dict) -> int:
    """
    POSTデータから時間休スロットを処理し、DBに保存して合計時間を返す.

    Args:
        application (Application): 紐付ける先の申請オブジェクト.
        post_data (Dict): request.POSTデータ.

    Returns:
        int: 計算後の合計取得時間（分）.
    """
    time_slots_data = _parse_time_slots(post_data)
    total_minutes = 0

    for slot_data in time_slots_data:
        calculated_minutes = _calculate_slot_duration(
            slot_data['start_time'],
            slot_data['end_time']
        )
        
        # 計算結果とともにTimeLeaveSlotをDBに保存
        TimeLeaveSlot.objects.create(
            application=application,
            start_time=slot_data['start_time'],
            end_time=slot_data['end_time'],
            calculated_minutes=calculated_minutes
        )
        total_minutes += calculated_minutes
    
    return total_minutes