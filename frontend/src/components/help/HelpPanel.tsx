import { Drawer, Typography, Divider } from 'antd';
import { useTranslation } from 'react-i18next';

const { Title, Paragraph, Text } = Typography;

export type HelpTopic =
  | 'overview'
  | 'vuln-detail'
  | 'host-detail'
  | 'full-detail'
  | 'trends'
  | 'admin-imports'
  | 'admin-users'
  | 'admin-rules'
  | 'admin-layers'
  | 'admin-branding'
  | 'admin-ldap'
  | 'admin-upgrade'
  | 'monitoring'
  | 'investigation'
  | 'proposals'
  | 'orphans'
  | 'filters';

/** Maps each HelpTopic to its i18n key and ordered section keys */
const TOPIC_SECTIONS: Record<HelpTopic, string[]> = {
  overview: ['kpi', 'distributions', 'widgets', 'export'],
  'vuln-detail': ['technical', 'categorization', 'descriptions', 'servers', 'export'],
  'host-detail': ['charts', 'table', 'export'],
  'full-detail': ['technical', 'servers'],
  trends: ['widgets', 'controls', 'export'],
  'admin-imports': ['methods', 'watcher'],
  'admin-users': ['profiles', 'session', 'lockout'],
  'admin-rules': ['filters', 'freshness'],
  'admin-layers': ['layers', 'rules', 'reclassify', 'orphans'],
  'admin-branding': ['logo', 'footer', 'banner'],
  'admin-ldap': ['connection', 'mapping', 'test'],
  'admin-upgrade': ['upload', 'validation', 'schedule', 'history'],
  monitoring: ['services', 'refresh'],
  investigation: ['vulnSearch', 'hostSearch', 'results'],
  proposals: ['overview', 'propose', 'review', 'status'],
  orphans: ['filters', 'propose', 'admin', 'reclassify'],
  filters: ['dimensions', 'actions', 'persistence'],
};

interface HelpPanelProps {
  topic: HelpTopic | null;
  open: boolean;
  onClose: () => void;
}

export default function HelpPanel({ topic, open, onClose }: HelpPanelProps) {
  const { t } = useTranslation();

  const renderContent = (tp: HelpTopic) => {
    const sections = TOPIC_SECTIONS[tp];
    return (
      <>
        <Paragraph>{t(`help.${tp}.intro`)}</Paragraph>
        {sections.map((sectionKey) => (
          <div key={sectionKey}>
            <Title level={5}>
              {t(`help.${tp}.sections.${sectionKey}.title`)}
            </Title>
            <Paragraph>
              {(
                t(`help.${tp}.sections.${sectionKey}.items`, {
                  returnObjects: true,
                }) as string[]
              ).map((item, idx) => (
                <span key={idx}>
                  {idx > 0 && <br />}
                  <Text>{item}</Text>
                </span>
              ))}
            </Paragraph>
          </div>
        ))}
      </>
    );
  };

  return (
    <Drawer
      title={topic ? t(`help.${topic}.title`) : t('help.drawerTitle')}
      placement="right"
      size="large"
      open={open}
      onClose={onClose}
    >
      {topic ? (
        <Typography>{renderContent(topic)}</Typography>
      ) : (
        <Paragraph>{t('help.selectSection')}</Paragraph>
      )}
      <Divider />
      <Paragraph type="secondary" style={{ fontSize: 12 }}>
        Qualys2Human — NeoRed
      </Paragraph>
    </Drawer>
  );
}
