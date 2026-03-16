import { Row, Col, Card, Statistic, Tag } from 'antd';
import {
  BugOutlined,
  DesktopOutlined,
  WarningOutlined,
  BarChartOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

interface KPICardsProps {
  totalVulns: number;
  hostCount: number;
  criticalCount: number;
}

export default function KPICards({
  totalVulns,
  hostCount,
  criticalCount,
}: KPICardsProps) {
  const { t } = useTranslation();

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} sm={12} lg={6}>
        <Card size="small">
          <Statistic
            title={t('overview.totalVulns')}
            value={totalVulns}
            prefix={<BugOutlined />}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card size="small">
          <Statistic
            title={t('overview.hosts')}
            value={hostCount}
            prefix={<DesktopOutlined />}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card size="small">
          <Statistic
            title={t('overview.criticals')}
            value={criticalCount}
            prefix={<WarningOutlined />}
            styles={{ content: { color: criticalCount > 0 ? '#cf1322' : '#3f8600' } }}
          />
        </Card>
      </Col>
      <Col xs={24} sm={12} lg={6}>
        <Card size="small">
          <Statistic
            title={t('overview.avgPerHost')}
            value={hostCount > 0 ? (totalVulns / hostCount).toFixed(1) : 0}
            prefix={<BarChartOutlined />}
          />
        </Card>
      </Col>
    </Row>
  );
}
