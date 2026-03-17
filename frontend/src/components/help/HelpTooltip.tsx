import { useState } from 'react';
import { Button, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import HelpPanel, { type HelpTopic } from './HelpPanel';

interface HelpTooltipProps {
  topic: HelpTopic;
  style?: React.CSSProperties;
}

export default function HelpTooltip({ topic, style }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Tooltip title="Aide">
        <Button
          type="text"
          size="small"
          icon={<QuestionCircleOutlined />}
          onClick={() => setOpen(true)}
          style={{ color: '#8c8c8c', ...style }}
        />
      </Tooltip>
      <HelpPanel topic={topic} open={open} onClose={() => setOpen(false)} />
    </>
  );
}
