import { Modal, Typography, Divider } from 'antd';
import { BugOutlined, RocketOutlined, StarOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

const { Title, Text } = Typography;

export interface ReleaseNote {
  version: string;
  date: string;
  title: string;
  features: string[];
  fixes: string[];
  improvements: string[];
}

interface WhatsNewModalProps {
  open: boolean;
  notes: ReleaseNote[];
  onClose: () => void;
}

function VersionSection({ note, showHeader }: { note: ReleaseNote; showHeader: boolean }) {
  const { t } = useTranslation();

  return (
    <div>
      {showHeader && (
        <Title level={5} style={{ marginTop: 16, marginBottom: 4 }}>
          v{note.version}
        </Title>
      )}
      <Text type="secondary">{note.date} — {note.title}</Text>

      {note.features.length > 0 && (
        <>
          <Divider orientation="left" plain style={{ margin: '12px 0 8px' }}>
            <StarOutlined /> {t('whatsNew.features')}
          </Divider>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {note.features.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </>
      )}

      {note.fixes.length > 0 && (
        <>
          <Divider orientation="left" plain style={{ margin: '12px 0 8px' }}>
            <BugOutlined /> {t('whatsNew.fixes')}
          </Divider>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {note.fixes.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </>
      )}

      {note.improvements.length > 0 && (
        <>
          <Divider orientation="left" plain style={{ margin: '12px 0 8px' }}>
            <RocketOutlined /> {t('whatsNew.improvements')}
          </Divider>
          <ul style={{ paddingLeft: 20, margin: 0 }}>
            {note.improvements.map((imp, i) => <li key={i}>{imp}</li>)}
          </ul>
        </>
      )}
    </div>
  );
}

export default function WhatsNewModal({ open, notes, onClose }: WhatsNewModalProps) {
  const { t } = useTranslation();
  const isSingle = notes.length === 1;
  const modalTitle = isSingle
    ? t('whatsNew.titleSingle', { version: notes[0].version })
    : t('whatsNew.titleMultiple', { count: notes.length });

  return (
    <Modal
      open={open}
      title={<Title level={4} style={{ margin: 0 }}>{modalTitle}</Title>}
      onCancel={onClose}
      onOk={onClose}
      okText={t('common.ok')}
      cancelButtonProps={{ style: { display: 'none' } }}
      width={560}
    >
      <div style={{ maxHeight: '60vh', overflowY: 'auto', paddingRight: 4 }}>
        {notes.map((note, idx) => (
          <div key={note.version}>
            {idx > 0 && <Divider style={{ margin: '16px 0' }} />}
            <VersionSection note={note} showHeader={!isSingle} />
          </div>
        ))}
      </div>
    </Modal>
  );
}
