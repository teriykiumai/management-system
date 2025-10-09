document.addEventListener('DOMContentLoaded', function() {
    const calendarEl = document.getElementById('calendar');

    // フィルタ要素が存在しない場合も安全に値を取得するヘルパー関数
    function getFilterValue(id) {
        const element = document.getElementById(id);
        return element ? element.value : '';
    }

    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        locale: 'ja',
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
        events: function(fetchInfo, successCallback, failureCallback) {
            // ヘルパー関数を使って安全に値を取得
            const params = new URLSearchParams({
                department: getFilterValue('departmentFilter'),
                group: getFilterValue('groupFilter'),
                team: getFilterValue('teamFilter'),
                leave_type: getFilterValue('leaveTypeFilter'),
            });
            
            fetch(`/leaves/api/events/?${params.toString()}`)
                .then(response => response.json())
                .then(data => successCallback(data))
                .catch(error => failureCallback(error));
        }
    });

    calendar.render();
    
    // 存在するフィルタにのみイベントリスナーを設定
    const filterIds = ['departmentFilter', 'groupFilter', 'teamFilter', 'leaveTypeFilter'];
    filterIds.forEach(id => {
        const filterElement = document.getElementById(id);
        if (filterElement) { // 要素が存在する場合のみリスナーを追加
            filterElement.addEventListener('change', function() {
                calendar.refetchEvents();
            });
        }
    });
});