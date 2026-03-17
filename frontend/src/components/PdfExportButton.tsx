import { useState } from 'react';
import { Button, message } from 'antd';
import { FilePdfOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

interface PdfExportButtonProps {
  onExport: () => Promise<void>;
}

export default function PdfExportButton({ onExport }: PdfExportButtonProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  const handleClick = async () => {
    setLoading(true);
    try {
      await onExport();
      message.success(t('pdf.success'));
    } catch (err: any) {
      console.error('PDF export error:', err);
      message.error(t('pdf.error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button icon={<FilePdfOutlined />} size="small" loading={loading} onClick={handleClick}>
      PDF
    </Button>
  );
}
