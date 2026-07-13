document.getElementById('instrument-search').addEventListener('input', function(e) {
    const input = e.target;
    const list = document.getElementById('instruments-list');
    const hiddenInput = document.getElementById('instrument-id-hidden');
    const options = list.options;
    
    const detailsBox = document.getElementById('instrument-details-box');
    
    // Сброс скрытого поля и скрытие блока деталей при редактировании текста
    hiddenInput.value = ""; 
    detailsBox.classList.add('d-none');
    
    for (let i = 0; i < options.length; i++) {
        if (options[i].value === input.value) {
            const opt = options[i];
            
            // Записываем UID в скрытый инпут формы для отправки в Django Views
            hiddenInput.value = opt.getAttribute('data-id');
            
            // Извлекаем все data-аттрибуты из опции datalist
            document.getElementById('info-name').textContent = opt.getAttribute('data-name');
            document.getElementById('info-ticker').textContent = opt.getAttribute('data-ticker');
            document.getElementById('info-class-code').textContent = `(${opt.getAttribute('data-class-code')})`;
            document.getElementById('info-lot').textContent = opt.getAttribute('data-lot');
            document.getElementById('info-currency').textContent = opt.getAttribute('data-currency');
            document.getElementById('info-min-price').textContent = opt.getAttribute('data-min-price');
            document.getElementById('info-uid').textContent = opt.getAttribute('data-id');
            
            // Красивый вывод флага шорта (True/False в "Разрешен/Запрещен")
            const shortEnabled = opt.getAttribute('data-short') === 'True';
            const shortCell = document.getElementById('info-short');
            shortCell.textContent = shortEnabled ? 'Разрешен' : 'Запрещен';
            shortCell.style.color = shortEnabled ? '#28a745' : '#dc3545';

            // Показываем блок с данными
            detailsBox.classList.remove('d-none');
            break;
        }
    }
});