import { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Badge, Collapse, message,
} from 'antd';
import { CheckOutlined, CloseOutlined, FormOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { ColumnsType } from 'antd/es/table';
import api from '../api/client';

interface AdminProposal {
  id: number;
  pattern: string;
  match_field: string;
  layer_id: number;
  layer_name: string | null;
  status: string;
  created_at: string;
  user_id: number | null;
  user_username: string | null;
  user_first_name: string | null;
  user_last_name: string | null;
}

interface LayerOption {
  id: number;
  name: string;
}

export interface PendingProposalsPanelProps {
  layers: LayerOption[];
  onAction?: (approved: boolean) => void;
}

export default function PendingProposalsPanel({ layers, onAction }: PendingProposalsPanelProps) {
  const { t } = useTranslation();
  const [proposals, setProposals] = useState<AdminProposal[]>([]);
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [selectedProposal, setSelectedProposal] = useState<AdminProposal | null>(null);
  const [approveForm] = Form.useForm();
  const [rejectForm] = Form.useForm();

  const fetchProposals = useCallback(async () => {
    try {
      const resp = await api.get('/rules/proposals?status_filter=pending');
      setProposals(resp.data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchProposals(); }, [fetchProposals]);

  const handleApproveQuick = async (proposal: AdminProposal) => {
    try {
      await api.put(`/rules/proposals/${proposal.id}/approve`, {
        pattern: proposal.pattern,
        match_field: proposal.match_field,
        layer_id: proposal.layer_id,
        comment: null,
      });
      message.success(t('proposals.approved'));
      fetchProposals();
      onAction?.(true);
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    }
  };

  const handleApprove = (proposal: AdminProposal) => {
    setSelectedProposal(proposal);
    approveForm.resetFields();
    approveForm.setFieldsValue({
      pattern: proposal.pattern,
      match_field: proposal.match_field,
      layer_id: proposal.layer_id,
      comment: '',
    });
    setApproveModalOpen(true);
  };

  const handleApproveSubmit = async () => {
    try {
      const values = await approveForm.validateFields();
      if (!selectedProposal) return;
      await api.put(`/rules/proposals/${selectedProposal.id}/approve`, {
        pattern: values.pattern,
        match_field: values.match_field,
        layer_id: values.layer_id,
        comment: values.comment || null,
      });
      message.success(t('proposals.approved'));
      setApproveModalOpen(false);
      setSelectedProposal(null);
      fetchProposals();
      onAction?.(true);
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    }
  };

  const handleReject = (proposal: AdminProposal) => {
    setSelectedProposal(proposal);
    rejectForm.resetFields();
    setRejectModalOpen(true);
  };

  const handleRejectSubmit = async () => {
    try {
      const values = await rejectForm.validateFields();
      if (!selectedProposal) return;
      await api.put(`/rules/proposals/${selectedProposal.id}/reject`, {
        comment: values.comment || null,
      });
      message.success(t('proposals.rejected'));
      setRejectModalOpen(false);
      setSelectedProposal(null);
      fetchProposals();
      onAction?.(false);
    } catch (err: any) {
      if (err.response) message.error(err.response.data?.detail || t('common.error'));
    }
  };

  const proposalColumns: ColumnsType<AdminProposal> = [
    {
      title: t('common.user'), key: 'user', width: 160,
      render: (_: unknown, record: AdminProposal) => {
        if (record.user_first_name || record.user_last_name) {
          return `${record.user_first_name || ''} ${record.user_last_name || ''}`.trim();
        }
        return record.user_username || '—';
      },
    },
    {
      title: t('common.date'), dataIndex: 'created_at', key: 'created_at', width: 140,
      render: (val: string) => val ? new Date(val).toLocaleDateString() : '—',
      defaultSortOrder: 'descend' as const,
      sorter: (a: AdminProposal, b: AdminProposal) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    { title: t('modals.pattern'), dataIndex: 'pattern', key: 'pattern' },
    { title: t('modals.targetField'), dataIndex: 'match_field', key: 'match_field', width: 100 },
    {
      title: t('filters.categorization'), key: 'layer', width: 150,
      render: (_: unknown, record: AdminProposal) => record.layer_name || '—',
    },
    {
      title: t('common.actions'), key: 'actions', width: 260,
      render: (_: unknown, record: AdminProposal) => (
        <Space>
          <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => handleApproveQuick(record)}>
            {t('proposals.approve')}
          </Button>
          <Button size="small" icon={<FormOutlined />} onClick={() => handleApprove(record)}>
            {t('proposals.editAndApprove')}
          </Button>
          <Button size="small" danger icon={<CloseOutlined />} onClick={() => handleReject(record)}>
            {t('proposals.reject')}
          </Button>
        </Space>
      ),
    },
  ];

  if (proposals.length === 0) return null;

  return (
    <>
      <Collapse
        style={{ marginBottom: 16 }}
        defaultActiveKey={['proposals']}
        items={[{
          key: 'proposals',
          label: (
            <span>
              {t('proposals.pendingProposals')}{' '}
              <Badge count={proposals.length} style={{ marginLeft: 8 }} />
            </span>
          ),
          children: (
            <Table
              columns={proposalColumns}
              dataSource={proposals}
              rowKey="id"
              pagination={false}
              size="small"
            />
          ),
        }]}
      />

      {/* Approve proposal modal (edit & approve) */}
      <Modal
        title={t('proposals.editAndApprove')}
        open={approveModalOpen}
        onOk={handleApproveSubmit}
        onCancel={() => { setApproveModalOpen(false); setSelectedProposal(null); }}
        okText={t('proposals.approve')}
        cancelText={t('common.cancel')}
      >
        <Form form={approveForm} layout="vertical">
          <Form.Item name="pattern" label={t('modals.pattern')} rules={[{ required: true, message: t('admin.layer.patternRequired') }]}>
            <Input />
          </Form.Item>
          <Form.Item name="match_field" label={t('modals.targetField')} rules={[{ required: true }]}>
            <Select options={[
              { label: t('modals.fieldTitle'), value: 'title' },
              { label: t('modals.fieldCategory'), value: 'category' },
            ]} />
          </Form.Item>
          <Form.Item name="layer_id" label={t('filters.categorization')} rules={[{ required: true, message: t('admin.layer.categorizationRequired') }]}>
            <Select
              placeholder={t('modals.selectCategory')}
              options={layers.map((l) => ({ label: l.name, value: l.id }))}
            />
          </Form.Item>
          <Form.Item name="comment" label={t('proposals.comment')}>
            <Input.TextArea rows={2} placeholder={t('proposals.commentPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Reject proposal modal */}
      <Modal
        title={t('proposals.reject')}
        open={rejectModalOpen}
        onOk={handleRejectSubmit}
        onCancel={() => { setRejectModalOpen(false); setSelectedProposal(null); }}
        okText={t('proposals.reject')}
        cancelText={t('common.cancel')}
        okButtonProps={{ danger: true }}
      >
        <Form form={rejectForm} layout="vertical">
          <Form.Item name="comment" label={t('proposals.rejectReason')}>
            <Input.TextArea rows={3} placeholder={t('proposals.rejectReasonPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
