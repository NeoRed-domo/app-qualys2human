import type { ColDef } from 'ag-grid-community';

function escapeCsv(value: unknown): string {
  if (value == null) return '';
  const str = String(value);
  if (str.includes('"') || str.includes(',') || str.includes('\n') || str.includes('\r')) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

function todayPrefix(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function exportToCsv<T>(colDefs: ColDef<T>[], rowData: T[], filename: string) {
  const dated = `${todayPrefix()}_${filename}`;
  const cols = colDefs.filter((c) => c.field);

  const headers = cols.map((c) => escapeCsv(c.headerName || c.field));

  const rows = rowData.map((row) =>
    cols.map((col) => {
      const raw = (row as Record<string, unknown>)[col.field as string];
      if (col.valueFormatter && typeof col.valueFormatter === 'function') {
        const formatted = col.valueFormatter({ value: raw, data: row } as any);
        return escapeCsv(formatted);
      }
      return escapeCsv(raw);
    }),
  );

  const bom = '\uFEFF';
  const csv = bom + [headers.join(','), ...rows.map((r) => r.join(','))].join('\r\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = dated;
  a.click();
  URL.revokeObjectURL(url);
}
