import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import html2canvas from 'html2canvas';

// A4 portrait dimensions (mm)
const PAGE_W = 210;
const PAGE_H = 297;
const MARGIN = 15;
const CONTENT_W = PAGE_W - 2 * MARGIN;
const HEADER_COLOR: [number, number, number] = [0, 21, 41]; // #001529
const ALT_ROW: [number, number, number] = [245, 245, 245]; // #f5f5f5

function formatNow(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function todayPrefix(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export class PdfReport {
  private doc: jsPDF;
  private y: number;
  private title: string;
  private logoDataUrl: string | null;
  private dateStr: string;

  constructor(title: string, logoDataUrl: string | null = null) {
    this.doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    this.title = title;
    this.logoDataUrl = logoDataUrl;
    this.dateStr = formatNow();
    this.y = MARGIN;
    this.drawHeader();
  }

  /** Space left before bottom margin */
  private spaceLeft(): number {
    return PAGE_H - MARGIN - this.y;
  }

  /** Add a new page and redraw header */
  private newPage(): void {
    this.doc.addPage();
    this.y = MARGIN;
    this.drawHeader();
  }

  /** Ensure enough vertical space; if not, add a new page */
  private ensureSpace(needed: number): void {
    if (this.spaceLeft() < needed) {
      this.newPage();
    }
  }

  /** Draw page header: logo | title | date + horizontal rule */
  private drawHeader(): void {
    const startY = this.y;

    // Logo (left)
    if (this.logoDataUrl) {
      try {
        this.doc.addImage(this.logoDataUrl, 'PNG', MARGIN, startY, 40, 14);
      } catch {
        // ignore logo errors
      }
    }

    // Title (center)
    this.doc.setFontSize(14);
    this.doc.setFont('helvetica', 'bold');
    this.doc.text(this.title, PAGE_W / 2, startY + 8, { align: 'center' });

    // Date (right)
    this.doc.setFontSize(9);
    this.doc.setFont('helvetica', 'normal');
    this.doc.text(this.dateStr, PAGE_W - MARGIN, startY + 8, { align: 'right' });

    // Horizontal rule
    this.y = startY + 16;
    this.doc.setDrawColor(0, 21, 41);
    this.doc.setLineWidth(0.5);
    this.doc.line(MARGIN, this.y, PAGE_W - MARGIN, this.y);
    this.y += 6;
  }

  /** Add filter summary line (italic, smaller font) */
  addFilterSummary(text: string): void {
    this.ensureSpace(10);
    this.doc.setFontSize(9);
    this.doc.setFont('helvetica', 'italic');
    this.doc.setTextColor(100, 100, 100);
    const lines = this.doc.splitTextToSize(`Filtres appliqués : ${text}`, CONTENT_W);
    this.doc.text(lines, MARGIN, this.y);
    this.y += lines.length * 4 + 4;
    this.doc.setTextColor(0, 0, 0);
  }

  /** Add KPI banner: grey boxes side by side */
  addKpis(items: { label: string; value: string | number }[]): void {
    const boxH = 18;
    this.ensureSpace(boxH + 6);
    const count = items.length;
    const gap = 3;
    const boxW = (CONTENT_W - (count - 1) * gap) / count;

    items.forEach((item, i) => {
      const x = MARGIN + i * (boxW + gap);
      this.doc.setFillColor(240, 240, 240);
      this.doc.roundedRect(x, this.y, boxW, boxH, 2, 2, 'F');

      this.doc.setFontSize(8);
      this.doc.setFont('helvetica', 'normal');
      this.doc.setTextColor(100, 100, 100);
      this.doc.text(item.label, x + boxW / 2, this.y + 6, { align: 'center' });

      this.doc.setFontSize(12);
      this.doc.setFont('helvetica', 'bold');
      this.doc.setTextColor(0, 0, 0);
      this.doc.text(String(item.value), x + boxW / 2, this.y + 14, { align: 'center' });
    });

    this.y += boxH + 6;
  }

  /** Add a section title (reserves space for title + some content below) */
  addSectionTitle(title: string): void {
    this.ensureSpace(40); // title + at least a few rows below
    this.doc.setFontSize(11);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setTextColor(0, 21, 41);
    this.doc.text(title, MARGIN, this.y);
    this.y += 7;
    this.doc.setTextColor(0, 0, 0);
  }

  /** Capture a DOM element (chart) as image and add it full-width */
  async addChartCapture(element: HTMLElement | null): Promise<void> {
    if (!element) return;
    const canvas = await html2canvas(element, {
      scale: 2,
      backgroundColor: '#ffffff',
      logging: false,
      useCORS: true,
    });
    const imgData = canvas.toDataURL('image/png');
    const ratio = canvas.height / canvas.width;
    const imgW = CONTENT_W;
    const imgH = imgW * ratio;

    this.ensureSpace(imgH);
    this.doc.addImage(imgData, 'PNG', MARGIN, this.y, imgW, imgH);
    this.y += imgH + 4;
  }

  /** Capture two DOM elements side by side (e.g. two donuts) */
  async addChartPair(left: HTMLElement | null, right: HTMLElement | null): Promise<void> {
    const hasLeft = !!left;
    const hasRight = !!right;

    // If only one chart, render it full-width instead of half
    if (hasLeft && !hasRight) {
      return this.addChartCapture(left);
    }
    if (!hasLeft && hasRight) {
      return this.addChartCapture(right);
    }
    if (!hasLeft && !hasRight) return;

    const halfW = (CONTENT_W - 6) / 2;
    const captures: { imgData: string; ratio: number }[] = [];

    for (const el of [left!, right!]) {
      const canvas = await html2canvas(el, {
        scale: 2,
        backgroundColor: '#ffffff',
        logging: false,
        useCORS: true,
      });
      captures.push({
        imgData: canvas.toDataURL('image/png'),
        ratio: canvas.height / canvas.width,
      });
    }

    const maxH = Math.max(
      halfW * captures[0].ratio,
      halfW * captures[1].ratio,
    );
    this.ensureSpace(maxH);

    this.doc.addImage(captures[0].imgData, 'PNG', MARGIN, this.y, halfW, halfW * captures[0].ratio);
    this.doc.addImage(captures[1].imgData, 'PNG', MARGIN + halfW + 6, this.y, halfW, halfW * captures[1].ratio);

    this.y += maxH + 4;
  }

  /** Add a programmatic table via jspdf-autotable */
  addTable(columns: { header: string; dataKey: string }[], rows: Record<string, unknown>[]): void {
    // Estimate table height: header (~10mm) + rows (~8mm each)
    const estimatedH = 10 + rows.length * 8;
    const usablePageH = PAGE_H - 2 * MARGIN - 22; // minus header area

    // If the table fits on one page but not in remaining space → new page
    if (estimatedH <= usablePageH && this.spaceLeft() < estimatedH) {
      this.newPage();
    } else {
      this.ensureSpace(30);
    }

    autoTable(this.doc, {
      startY: this.y,
      head: [columns.map((c) => c.header)],
      body: rows.map((row) => columns.map((c) => {
        const val = row[c.dataKey];
        return val != null ? String(val) : '—';
      })),
      margin: { left: MARGIN, right: MARGIN, top: MARGIN + 22, bottom: MARGIN + 10 },
      headStyles: {
        fillColor: HEADER_COLOR,
        textColor: [255, 255, 255],
        fontStyle: 'bold',
        fontSize: 8,
      },
      bodyStyles: { fontSize: 7.5 },
      alternateRowStyles: { fillColor: ALT_ROW },
      styles: { cellPadding: 2, overflow: 'linebreak' },
      didDrawPage: (data) => {
        // Redraw header on new pages created by autotable
        if (data.pageNumber > 1) {
          const prevY = this.y;
          this.y = MARGIN;
          this.drawHeader();
          this.y = prevY;
        }
      },
    });

    // Update Y position after table
    this.y = (this.doc as any).lastAutoTable?.finalY ?? this.y;
    this.y += 6;
  }

  /** Add key-value description grid (3 columns) */
  addDescriptions(items: { label: string; value: string }[]): void {
    const cols = 3;
    const colW = CONTENT_W / cols;
    const rowH = 10;
    const rowsNeeded = Math.ceil(items.length / cols);

    this.ensureSpace(rowsNeeded * rowH + 4);

    items.forEach((item, i) => {
      const col = i % cols;
      const row = Math.floor(i / cols);
      const x = MARGIN + col * colW;
      const itemY = this.y + row * rowH;

      // Check if we need a new page mid-description
      if (itemY + rowH > PAGE_H - MARGIN) {
        this.newPage();
        return; // items will be cut off — but descriptions are typically short
      }

      this.doc.setFontSize(7.5);
      this.doc.setFont('helvetica', 'bold');
      this.doc.setTextColor(100, 100, 100);
      this.doc.text(item.label, x, itemY);

      this.doc.setFont('helvetica', 'normal');
      this.doc.setTextColor(0, 0, 0);
      this.doc.setFontSize(8.5);
      const valueText = item.value || '—';
      const truncated = valueText.length > 50 ? valueText.slice(0, 47) + '...' : valueText;
      this.doc.text(truncated, x, itemY + 4);
    });

    this.y += rowsNeeded * rowH + 4;
  }

  /** Add a block of text with title (handles page breaks) */
  addTextBlock(title: string, content: string | null): void {
    if (!content) return;
    this.ensureSpace(20);

    // Title
    this.doc.setFontSize(10);
    this.doc.setFont('helvetica', 'bold');
    this.doc.setTextColor(0, 21, 41);
    this.doc.text(title, MARGIN, this.y);
    this.y += 5;

    // Content
    this.doc.setFontSize(8);
    this.doc.setFont('helvetica', 'normal');
    this.doc.setTextColor(50, 50, 50);
    const lines: string[] = this.doc.splitTextToSize(content, CONTENT_W);

    for (const line of lines) {
      if (this.y + 4 > PAGE_H - MARGIN) {
        this.newPage();
      }
      this.doc.text(line, MARGIN, this.y);
      this.y += 3.5;
    }

    this.y += 4;
    this.doc.setTextColor(0, 0, 0);
  }

  /** Add footers to all pages and trigger download */
  save(filename: string): void {
    const totalPages = this.doc.getNumberOfPages();
    for (let i = 1; i <= totalPages; i++) {
      this.doc.setPage(i);
      this.doc.setFontSize(8);
      this.doc.setFont('helvetica', 'normal');
      this.doc.setTextColor(130, 130, 130);
      this.doc.text(
        `Page ${i}/${totalPages} — Qualys2Human — ${this.dateStr}`,
        PAGE_W / 2,
        PAGE_H - 8,
        { align: 'center' },
      );
    }

    this.doc.save(`${todayPrefix()}_${filename}`);
  }
}
