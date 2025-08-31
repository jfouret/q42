document.addEventListener('DOMContentLoaded', function () {
    const filterField = document.getElementById('filter-field');
    const filterValue = document.getElementById('filter-value');
    const exactMatch = document.getElementById('exact-match');
    const exactMatchLabel = document.getElementById('exact-match-label');
    const table = document.getElementById('questions-table');
    const tableBody = table.getElementsByTagName('tbody')[0];
    const rows = tableBody.getElementsByTagName('tr');

    function toggleExactMatch() {
        if (filterField.value === "0") {
            exactMatch.style.display = 'inline-block';
            exactMatchLabel.style.display = 'inline-block';
        } else {
            exactMatch.style.display = 'none';
            exactMatchLabel.style.display = 'none';
        }
    }

    function filterTable() {
        const fieldIndex = parseInt(filterField.value, 10);
        const value = filterValue.value.toLowerCase();
        const isExactMatch = exactMatch.checked;

        for (let i = 0; i < rows.length; i++) {
            const cell = rows[i].getElementsByTagName('td')[fieldIndex];
            if (cell) {
                const cellText = (cell.textContent || cell.innerText).toLowerCase();
                let isMatch = false;

                if (fieldIndex === 0 && isExactMatch) {
                    isMatch = cellText === value;
                } else {
                    isMatch = cellText.indexOf(value) > -1;
                }

                if (isMatch) {
                    rows[i].style.display = "";
                } else {
                    rows[i].style.display = "none";
                }
            }
        }
    }

    filterField.addEventListener('change', function() {
        toggleExactMatch();
        filterTable();
    });
    filterValue.addEventListener('keyup', filterTable);
    exactMatch.addEventListener('change', filterTable);

    toggleExactMatch();
});
