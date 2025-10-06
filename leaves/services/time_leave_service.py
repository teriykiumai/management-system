from datetime import datetime, time
from typing import List, Dict, Tuple
from django.core.exceptions import ValidationError

from leaves.models import Application, TimeLeaveSlot, User
from leaves.constants import MINUTES_PER_WORK_DAY
from .break_time_service import get_applicable_break_times

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

def _validate_slots_initial(time_slots_data: List[Dict[str, time]]):
    """
    時間帯リストの基本的なフォーマットと、スロット間の重複を検証する.
    """
    if not time_slots_data:
        raise ValidationError("時間休を申請する場合、少なくとも1つの時間帯を入力してください。")

    # 開始時間でソートして、重複チェックを容易にする
    sorted_slots = sorted(time_slots_data, key=lambda x: x['start_time'])

    for i, slot in enumerate(sorted_slots):
        start_time = slot['start_time']
        end_time = slot['end_time']

        if start_time >= end_time:
            raise ValidationError(f"終了時刻は開始時刻より後に設定してください ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})。")
        
        # 現在のスロットの開始時刻が、前のスロットの終了時刻より前なら重複している
        if i > 0 and start_time < sorted_slots[i-1]['end_time']:
            prev_slot = sorted_slots[i-1]
            raise ValidationError(
                f"時間帯が重複しています: "
                f"({prev_slot['start_time'].strftime('%H:%M')}-{prev_slot['end_time'].strftime('%H:%M')}) と "
                f"({start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')})"
            )
        
def _validate_total_minutes(total_minutes: int):
    """合計時間に対するバリデーションを行う."""
    if total_minutes >= MINUTES_PER_WORK_DAY:
        raise ValidationError(
            f"合計時間が{MINUTES_PER_WORK_DAY // 60}時間以上になります。"
            f"{MINUTES_PER_WORK_DAY // 60}時間以上の休暇は「有給休暇」として申請してください。"
        )

def _calculate_minutes_and_validate_duration(
    user: User, 
    time_slots_data: List[Dict[str, time]]
) -> Tuple[int, List[Dict]]:
    """各スロットの分数を計算し、計算後のバリデーションを行い、合計分数と処理済みスロットリストを返す."""
    applicable_breaks = get_applicable_break_times(user)
    processed_slots = []
    total_minutes = 0
    today = datetime.today().date()

    for slot in time_slots_data:
        slot_start_dt = datetime.combine(today, slot['start_time'])
        slot_end_dt = datetime.combine(today, slot['end_time'])
        slot_duration = (slot_end_dt - slot_start_dt).total_seconds() / 60
        
        deduction_minutes = 0
        for break_time in applicable_breaks:
            break_start_dt = datetime.combine(today, break_time.start_time)
            break_end_dt = datetime.combine(today, break_time.end_time)
            overlap_start = max(slot_start_dt, break_start_dt)
            overlap_end = min(slot_end_dt, break_end_dt)
            if overlap_start < overlap_end:
                deduction_minutes += (overlap_end - overlap_start).total_seconds() / 60
        
        calculated_minutes = max(0, int(slot_duration - deduction_minutes))

        # 休憩差引後の分数に対するバリデーション
        if calculated_minutes % 60 != 0:
            raise ValidationError(
                f"休憩時間を差し引いた後の実働時間が1時間単位になりません。"
                f"問題の時間帯: {slot['start_time'].strftime('%H:%M')}-{slot['end_time'].strftime('%H:%M')} "
                f"(実働 {calculated_minutes}分)"
            )
        
        processed_slots.append({**slot, 'calculated_minutes': calculated_minutes})
        total_minutes += calculated_minutes
        
    return total_minutes, processed_slots

def _save_slots_to_db(application: Application, processed_slots: List[Dict]):
    """処理済みスロットをDBに保存する."""
    for slot in processed_slots:
        TimeLeaveSlot.objects.create(application=application, **slot)


# --- 全体を統括する公開関数 ---
def process_time_leave_slots(application: Application, post_data: Dict) -> int:
    """
    POSTデータから時間休スロットを処理し、DBに保存して合計時間を返す.
    """
    time_slots_data = _parse_time_slots(post_data)
    _validate_slots_initial(time_slots_data) 
    
    total_minutes, processed_slots = _calculate_minutes_and_validate_duration(application.applicant, time_slots_data) 
    
    _validate_total_minutes(total_minutes)
    _save_slots_to_db(application, processed_slots)
    
    return total_minutes