from datetime import datetime, time
from typing import List, Dict, Tuple
from django.core.exceptions import ValidationError
from leaves.models import Application, TimeLeaveSlot, User
from leaves.constants import MINUTES_PER_WORK_DAY
from .break_time_service import get_applicable_break_times

# --- 時間スロットの入力値をdate型に変換するヘルパー関数 ---
def parse_time_slots(post_data: Dict) -> List[Dict[str, time]]:
    """POSTデータから 'start_time_X', 'end_time_X' をパースして時間帯リストを返す."""
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

# --- 公開サービス関数 ---
def calculate_time_leave_minutes(user: User, time_slots_data: List[Dict[str, time]]) -> Tuple[int, List[Dict]]:
    """
    時間帯リストから休憩時間を除いた実働時間(分)を計算する.
    Args:
        user (User): 休憩時間の計算対象となるユーザー.
        time_slots_data (List[Dict[str, time]]): パース済みの時間帯リスト.
    Returns:
        Tuple[int, List[Dict]]: 計算後の合計時間(分)と、計算済み時間を含むスロット情報のリスト.
    """
    applicable_breaks = get_applicable_break_times(user)
    processed_slots = []
    total_minutes = 0
    today = datetime.today().date()

    for slot in time_slots_data:
        slot_start_dt = datetime.combine(today, slot['start_time'])
        slot_end_dt = datetime.combine(today, slot['end_time'])
        slot_duration = (slot_end_dt - slot_start_dt).total_seconds() / 60 # to minute
        
        deduction_minutes = 0
        for break_time in applicable_breaks:
            break_start_dt = datetime.combine(today, break_time.start_time)
            break_end_dt = datetime.combine(today, break_time.end_time)
            overlap_start = max(slot_start_dt, break_start_dt)
            overlap_end = min(slot_end_dt, break_end_dt)
            if overlap_start < overlap_end:
                deduction_minutes += (overlap_end - overlap_start).total_seconds() / 60 # to minute
        
        calculated_minutes = max(0, int(slot_duration - deduction_minutes))
        processed_slots.append({**slot, 'calculated_minutes': calculated_minutes})
        total_minutes += calculated_minutes
        
    return total_minutes, processed_slots

def validate_time_leave_request(user: User, post_data: Dict):
    """
    時間休申請に関連する全てのバリデーションを実行する.

    Args:
        user (User): 申請者.
        post_data (Dict): request.POSTデータ.

    Raises:
        ValidationError: 検証ルールに違反した場合.
    """
    # 1. パース
    time_slots_data = parse_time_slots(post_data)

    # 2. 初期バリデーション (フォーマット, 重複)
    if not time_slots_data:
        raise ValidationError("時間休を申請する場合、少なくとも1つの時間帯を入力してください。")
    sorted_slots = sorted(time_slots_data, key=lambda x: x['start_time'])
    for i, slot in enumerate(sorted_slots):
        if slot['start_time'] >= slot['end_time']:
            raise ValidationError(f"終了時刻は開始時刻より後に設定してください。")
        if i > 0 and slot['start_time'] < sorted_slots[i-1]['end_time']:
            raise ValidationError(f"時間帯が重複しています。")

    # 3. 計算とバリデーション
    total_minutes, processed_slots = calculate_time_leave_minutes(user, time_slots_data)
    
    for slot in processed_slots:
        if slot['calculated_minutes'] % 60 != 0:
            raise ValidationError(f"休憩時間を引いた後の実働時間が1時間単位になりません。")

    if total_minutes >= MINUTES_PER_WORK_DAY:
        raise ValidationError(f"合計時間が{MINUTES_PER_WORK_DAY // 60}時間以上になります。")

def save_time_leave_slots(application: Application, processed_slots: List[Dict]):
    """
    計算済みの時間帯スロット情報をデータベースに保存する.
    Args:
        application (Application): 紐付ける先の申請オブジェクト.
        processed_slots (List[Dict]): 計算済み時間を含むスロット情報のリスト.
    """
    for slot in processed_slots:
        TimeLeaveSlot.objects.create(
            application=application,
            start_time=slot['start_time'],
            end_time=slot['end_time'],
            calculated_minutes=slot['calculated_minutes']
        )