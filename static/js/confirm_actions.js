document.addEventListener('DOMContentLoaded', function() {
    // data-confirm属性を持つフォーム内の、type="submit"のボタン全てを対象にする
    document.querySelectorAll('form[data-confirm] button[type="submit"]').forEach(button => {
        
        button.addEventListener('click', function(event) {
            // ボタンがクリックされた時点では、まだフォームを送信しない
            event.preventDefault();

            const form = event.target.closest('form');
            const message = form.dataset.confirm;
            const confirmButtonText = form.dataset.confirmButton || 'はい';
            const cancelButtonText = form.dataset.cancelButton || 'いいえ';

            // クリックされたボタンのnameとvalueを取得
            const actionName = event.target.name;
            const actionValue = event.target.value;

            Swal.fire({
                title: '確認',
                text: message,
                icon: 'question',
                showCancelButton: true,
                confirmButtonColor: '#3085d6',
                cancelButtonColor: '#d33',
                confirmButtonText: confirmButtonText,
                cancelButtonText: cancelButtonText
            }).then((result) => {
                if (result.isConfirmed) {
                    // 「はい」が押されたら、押されたボタンの情報を隠しフィールドとしてフォームに追加
                    if (actionName && actionValue) {
                        const hiddenInput = document.createElement('input');
                        hiddenInput.type = 'hidden';
                        hiddenInput.name = actionName;
                        hiddenInput.value = actionValue;
                        form.appendChild(hiddenInput);
                    }
                    // その後、フォームを送信
                    form.submit();
                }
            });
        });
    });
});