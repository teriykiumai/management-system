document.addEventListener('DOMContentLoaded', function() {

    const leaveTypeSelect = document.getElementById('id_leave_type');
    const startDateInput = document.getElementById('id_start_date');
    const endDateField = document.getElementById('endDateField');
    const endDateInput = document.getElementById('id_end_date');
    const timeLeaveSlotsDiv = document.getElementById('timeLeaveSlots');
    const addTimeSlotButton = document.getElementById('addTimeSlot');
    const timeSlotsContainer = document.getElementById('timeSlotsContainer');

    /**
     * HH:MM形式の30分刻みの時間選択<select>要素を生成する
     * @param {string} name - select要素のname属性
     * @returns {HTMLSelectElement}
     */
    function createTimeSelect(name) {
        const select = document.createElement('select');
        select.name = name;
        select.required = true;

        for (let h = 0; h < 24; h++) {
            for (let m = 0; m < 60; m += 30) {
                const hour = String(h).padStart(2, '0');
                const minute = String(m).padStart(2, '0');
                const timeValue = `${hour}:${minute}`;
                
                const option = document.createElement('option');
                option.value = timeValue;
                option.textContent = timeValue;
                select.appendChild(option);
            }
        }
        return select;
    }
    
    /** 時間帯入力欄（開始・終了）を1行追加する */
    function addTimeSlot() {
        const slotCount = timeSlotsContainer.children.length;
        const newSlot = document.createElement('div');
        newSlot.classList.add('time-slot-row');
        
        const startTimeSelect = createTimeSelect(`start_time_${slotCount}`);
        const endTimeSelect = createTimeSelect(`end_time_${slotCount}`);
        
        const separator = document.createElement('span');
        separator.textContent = '～';

        const removeButton = document.createElement('button');
        removeButton.type = 'button';
        removeButton.textContent = '削除';
        removeButton.classList.add('remove-slot-btn');

        newSlot.appendChild(startTimeSelect);
        newSlot.appendChild(separator);
        newSlot.appendChild(endTimeSelect);
        newSlot.appendChild(removeButton);
        
        timeSlotsContainer.appendChild(newSlot);
    }
    
    /** フォームの表示/非表示を切り替える */
    function toggleFormFields() {
        const selectedType = leaveTypeSelect.value;

        if (['AM_HALF', 'PM_HALF', 'TIME'].includes(selectedType)) {
            endDateField.style.display = 'none';
            endDateInput.required = false;
            // 念のため、見えないフィールドの値も開始日と同期させておく
            endDateInput.value = startDateInput.value;
        } else {
            endDateField.style.display = 'block';
            endDateInput.required = true;
        }

        if (selectedType === 'TIME') {
            timeLeaveSlotsDiv.style.display = 'block';
            // 時間休み選択時に一つ表示させておく
            if (timeSlotsContainer.children.length === 0) {
                addTimeSlot();
            }
        } else {
            timeLeaveSlotsDiv.style.display = 'none';
        }
    }
    
    // --- イベントリスナー設定 ---
    leaveTypeSelect.addEventListener('change', toggleFormFields);
    addTimeSlotButton.addEventListener('click', addTimeSlot);

    // 開始日が変更されたら、非表示の終了日の値も更新
    startDateInput.addEventListener('change', function() {
        if (!endDateField.offsetParent) { // is visible
            endDateInput.value = startDateInput.value;
        }
    });

    // 「削除」ボタンのイベント処理（イベント委譲）
    timeSlotsContainer.addEventListener('click', function(e) {
        if (e.target && e.target.classList.contains('remove-slot-btn')) {
            e.target.parentElement.remove();
        }
    });

    // 初期表示
    toggleFormFields();
});