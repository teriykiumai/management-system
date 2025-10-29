document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');
    
    // --- フィルタ要素の取得 ---
    const departmentFilter = document.getElementById('departmentFilter');
    const groupFilter = document.getElementById('groupFilter');
    const teamFilter = document.getElementById('teamFilter');
    const leaveTypeFilter = document.getElementById('leaveTypeFilter');
    const onlyMeFilter = document.getElementById('onlyMeFilter');

    /**
     * フィルタ要素が存在しない場合も安全に値を取得するヘルパー関数
     * @param {string} id - HTML要素のID
     * @returns {string} 要素の値、または空文字
     */
    function getFilterValue(id) {
        const element = document.getElementById(id);
        return element ? element.value : '';
    }

    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'ja',
        // --- ヘッダーとボタンの定義 ---
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,listYear'
        },
        buttonText: {
            today: '今日',
            month: '月',
            week: '週',
            listYear: '年間リスト',
        },

        // 週表示の時間範囲を 06:00 - 21:00 に限定
        slotMinTime: '06:00:00',
        slotMaxTime: '21:00:00',

        // 月表示でイベントが収まらない場合に「+n more」リンクを表示
        dayMaxEvents: true,

        // --- イベントデータの取得 ---
        events: function(fetchInfo, successCallback, failureCallback) {
            const params = new URLSearchParams({
                department: getFilterValue('departmentFilter'),
                group: getFilterValue('groupFilter'),
                team: getFilterValue('teamFilter'),
                leave_type: getFilterValue('leaveTypeFilter'),
                only_me: onlyMeFilter ? onlyMeFilter.checked : 'false',
            });
            
            fetch(`/leaves/api/events/?${params.toString()}`)
                .then(response => response.json())
                .then(data => successCallback(data))
                .catch(error => failureCallback(error));
        }
    });

    calendar.render();
    
    // --- フィルタ連動ロジック ---
    function updateGroupOptions() {
        if (!departmentFilter || !groupFilter) return; // 必要な要素がなければ何もしない

        const selectedDepId = departmentFilter.value;
        groupFilter.value = ""; // グループの選択をリセット

        for (const option of groupFilter.options) {
            if (option.value === "") continue;
            option.style.display = (!selectedDepId || option.dataset.departmentId === selectedDepId) ? '' : 'none';
        }
        updateTeamOptions(); // チームの選択肢も更新
    }

    function updateTeamOptions() {
        if (!groupFilter || !teamFilter) return; // 必要な要素がなければ何もしない

        const selectedGroupId = groupFilter.value;
        teamFilter.value = ""; // チームの選択をリセット

        for (const option of teamFilter.options) {
            if (option.value === "") continue;
            option.style.display = (!selectedGroupId || option.dataset.groupId === selectedGroupId) ? '' : 'none';
        }
    }
    
    // --- イベントリスナー設定 ---
    // 存在するフィルタ要素にのみイベントリスナーを設定
    const allFilters = [departmentFilter, groupFilter, teamFilter, leaveTypeFilter, onlyMeFilter];
    allFilters.forEach(filter => {
        if (filter) {
            filter.addEventListener('change', function() {
                if (filter.id === 'departmentFilter') {
                    updateGroupOptions();
                }
                if (filter.id === 'groupFilter') {
                    updateTeamOptions();
                }
                calendar.refetchEvents(); // カレンダーのイベントを再取得
            });
        }
    });

    // --- 初期表示時のフィルタ状態を更新 ---
    updateGroupOptions();
});