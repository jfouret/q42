document.addEventListener('DOMContentLoaded', function () {
    const tables = document.querySelectorAll('table.table-sortable');
    tables.forEach(table => {
        new simpleDatatables.DataTable(table);
    });
});
