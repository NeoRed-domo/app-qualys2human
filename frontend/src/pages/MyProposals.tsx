import { useEffect, useState, useCallback } from 'react';
import { Typography, Spin, Alert, Tag, Button, Modal, Empty, message } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { AgGridReact } from 'ag-grid-react';
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef } from 'ag-grid-community';
import api from '../api/client';
import { useTheme } from '../contexts/ThemeContext';

ModuleRegistry.registerModules([AllCommunityModule]);

const { Title } = Typography;

interface Proposal {
  id: number;
  pattern: string;
  match_field: string;
  layer_id: number;
  layer_name: string | null;
  status: string;
  admin_comment: string | null;
  created_at: string;
  reviewed_at: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: 'orange',
  approved: 'green',
  rejected: 'red',
};

export default function MyProposals() {
  const { t } = useTranslation();
  const { tokens } = useTheme();
  const [rows, setRows] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get('/rules/proposals/mine');
      setRows(resp.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.error'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleDelete = useCallback((proposal: Proposal) => {
    Modal.confirm({
      title: t('proposals.deleteConfirmTitle'),
      content: t('proposals.deleteConfirmContent'),
      okText: t('common.delete'),
      okType: 'danger',
      cancelText: t('common.cancel'),
      onOk: async () => {
        try {
          await api.delete(`/rules/proposals/${proposal.id}`);
          message.success(t('proposals.deleted'));
          setRows((prev) => prev.filter((r) => r.id !== proposal.id));
        } catch (err: any) {
          message.error(err.response?.data?.detail || t('common.error'));
        }
      },
    });
  }, [t]);

  const MATCH_FIELD_LABELS: Record<string, string> = {
    title: t('modals.fieldTitle'),
    category: t('modals.fieldCategory'),
  };

  const columns: ColDef<Proposal>[] = [
    {
      field: 'pattern',
      headerName: t('modals.pattern'),
      flex: 2,
      minWidth: 200,
      filter: 'agTextColumnFilter',
      sortable: true,
    },
    {
      field: 'match_field',
      headerName: t('modals.targetField'),
      width: 130,
      sortable: true,
      valueFormatter: (p) => MATCH_FIELD_LABELS[p.value] || p.value,
    },
    {
      field: 'layer_name',
      headerName: t('filters.categorization'),
      flex: 1,
      minWidth: 150,
      sortable: true,
    },
    {
      field: 'created_at',
      headerName: t('proposals.createdAt'),
      width: 150,
      sortable: true,
      sort: 'desc',
      valueFormatter: (p) => {
        if (!p.value) return '';
        return new Date(p.value).toLocaleDateString();
      },
    },
    {
      field: 'status',
      headerName: t('proposals.status'),
      width: 130,
      sortable: true,
      cellRenderer: (p: any) => {
        const status = p.value as string;
        return (
          <Tag color={STATUS_COLORS[status] || 'default'}>
            {t(`proposals.status_${status}`)}
          </Tag>
        );
      },
    },
    {
      field: 'admin_comment',
      headerName: t('proposals.adminComment'),
      flex: 1,
      minWidth: 150,
    },
    {
      headerName: t('common.actions'),
      width: 100,
      cellRenderer: (p: any) => {
        const row = p.data as Proposal;
        if (!row || row.status !== 'pending') return null;
        return (
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(row)}
          />
        );
      },
    },
  ];

  if (error) {
    return <Alert message={t('common.error')} description={error} type="error" showIcon />;
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>
        {t('proposals.pageTitle')}
      </Title>

      <Spin spinning={loading}>
        {rows.length === 0 && !loading ? (
          <Empty description={t('proposals.emptyState')} />
        ) : (
          <div style={{ height: 'calc(100vh - 260px)' }}>
            <AgGridReact<Proposal>
              theme={themeQuartz.withParams({ colorScheme: tokens.agGridColorScheme })}
              rowData={rows}
              columnDefs={columns}
              domLayout="normal"
              rowHeight={42}
              headerHeight={38}
              getRowId={(p) => String(p.data.id)}
            />
          </div>
        )}
      </Spin>
    </div>
  );
}
