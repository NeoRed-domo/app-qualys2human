import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Tag, Button, Space, Modal, Form, Input, Select, Switch, InputNumber, message,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, UnlockOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { ColumnsType } from 'antd/es/table';
import api from '../../api/client';

interface UserRow {
  id: number;
  username: string;
  first_name: string | null;
  last_name: string | null;
  auth_type: string;
  profile_name: string;
  profile_id: number;
  ad_domain: string | null;
  is_active: boolean;
  must_change_password: boolean;
  last_login: string | null;
  is_locked: boolean;
  failed_login_attempts: number;
}

interface Profile {
  id: number;
  name: string;
  type: string;
}

interface SessionSettings {
  timeout_minutes: number;
  warning_minutes: number;
}

export default function UserManagement() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<UserRow | null>(null);
  const [form] = Form.useForm();

  // Session settings
  const [sessionSettings, setSessionSettings] = useState<SessionSettings>({
    timeout_minutes: 120,
    warning_minutes: 5,
  });
  const [sessionForm] = Form.useForm();
  const [savingSession, setSavingSession] = useState(false);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await api.get(`/users?page=${page}&page_size=20`);
      setUsers(resp.data.items);
      setTotal(resp.data.total);
    } catch {
      message.error(t('admin.user.loadError'));
    } finally {
      setLoading(false);
    }
  }, [page, t]);

  const fetchProfiles = useCallback(async () => {
    try {
      const resp = await api.get('/users/profiles');
      setProfiles(resp.data);
    } catch {
      /* ignore */
    }
  }, []);

  const fetchSessionSettings = useCallback(async () => {
    try {
      const resp = await api.get('/settings/session');
      setSessionSettings(resp.data);
      sessionForm.setFieldsValue(resp.data);
    } catch {
      /* use defaults */
    }
  }, [sessionForm]);

  useEffect(() => {
    fetchUsers();
    fetchProfiles();
    fetchSessionSettings();
  }, [fetchUsers, fetchProfiles, fetchSessionSettings]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (user: UserRow) => {
    setEditing(user);
    form.setFieldsValue({
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      profile_id: user.profile_id,
      is_active: user.is_active,
      must_change_password: user.must_change_password,
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        const payload: Record<string, any> = {};
        if (values.password) payload.password = values.password;
        if (values.first_name !== editing.first_name) payload.first_name = values.first_name ?? null;
        if (values.last_name !== editing.last_name) payload.last_name = values.last_name ?? null;
        if (values.profile_id !== editing.profile_id) payload.profile_id = values.profile_id;
        if (values.is_active !== editing.is_active) payload.is_active = values.is_active;
        if (values.must_change_password !== editing.must_change_password)
          payload.must_change_password = values.must_change_password;

        await api.put(`/users/${editing.id}`, payload);
        message.success(t('admin.user.updated'));
      } else {
        await api.post('/users', {
          username: values.username,
          password: values.password,
          first_name: values.first_name || null,
          last_name: values.last_name || null,
          profile_id: values.profile_id,
        });
        message.success(t('admin.user.created'));
      }
      setModalOpen(false);
      fetchUsers();
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    }
  };

  const handleDelete = (user: UserRow) => {
    Modal.confirm({
      title: t('admin.user.deleteConfirm', { username: user.username }),
      content: t('common.irreversibleAction'),
      okText: t('common.delete'),
      okType: 'danger',
      cancelText: t('common.cancel'),
      onOk: async () => {
        try {
          await api.delete(`/users/${user.id}`);
          message.success(t('admin.user.deleted'));
          fetchUsers();
        } catch (err: any) {
          message.error(err.response?.data?.detail || t('common.error'));
        }
      },
    });
  };

  const handleUnlock = async (user: UserRow) => {
    try {
      await api.put(`/users/${user.id}`, { unlock: true });
      message.success(t('admin.user.unlocked', { username: user.username }));
      fetchUsers();
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('common.error'));
    }
  };

  const handleSaveSession = async () => {
    try {
      const values = await sessionForm.validateFields();
      setSavingSession(true);
      const resp = await api.put('/settings/session', values);
      setSessionSettings(resp.data);
      message.success(t('admin.user.sessionSaved'));
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('admin.user.validationError'));
    } finally {
      setSavingSession(false);
    }
  };

  const columns: ColumnsType<UserRow> = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: t('admin.user.username'), dataIndex: 'username' },
    {
      title: t('admin.user.displayName'), key: 'display_name', width: 180,
      render: (_: any, record: UserRow) => {
        const name = [record.first_name, record.last_name].filter(Boolean).join(' ');
        return name || '—';
      },
    },
    {
      title: t('admin.user.profile'), dataIndex: 'profile_name', width: 120,
      render: (name: string) => {
        const colors: Record<string, string> = {
          admin: 'red', user: 'blue', monitoring: 'green',
        };
        return <Tag color={colors[name] || 'default'}>{name}</Tag>;
      },
    },
    {
      title: t('admin.user.authType'), dataIndex: 'auth_type', width: 80,
      render: (authType: string) => <Tag>{authType}</Tag>,
    },
    {
      title: t('admin.user.activeLabel'), dataIndex: 'is_active', width: 70,
      render: (v: boolean) => (
        <Tag color={v ? 'success' : 'default'}>{v ? t('common.yes') : t('common.no')}</Tag>
      ),
    },
    {
      title: t('admin.user.lockStatus'), key: 'lock_status', width: 130,
      render: (_: any, record: UserRow) => (
        <Space size="small">
          {record.is_locked && <Tag color="red">{t('admin.user.locked')}</Tag>}
          {!record.is_locked && record.failed_login_attempts > 0 && (
            <Tag color="orange">{t('admin.user.failedAttempts', { count: record.failed_login_attempts })}</Tag>
          )}
          {!record.is_locked && record.failed_login_attempts === 0 && (
            <Tag color="green">OK</Tag>
          )}
        </Space>
      ),
    },
    {
      title: t('admin.user.lastLogin'), dataIndex: 'last_login', width: 170,
      render: (v: string | null) => v || '—',
    },
    {
      title: t('common.actions'), key: 'actions', width: 150,
      render: (_: any, record: UserRow) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          {record.is_locked && (
            <Button
              size="small"
              icon={<UnlockOutlined />}
              onClick={() => handleUnlock(record)}
              title={t('admin.user.unlock')}
            />
          )}
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)} />
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Session settings card */}
      <Card title={t('admin.user.sessionSettings')} size="small">
        <Form
          form={sessionForm}
          layout="inline"
          initialValues={sessionSettings}
        >
          <Form.Item
            name="timeout_minutes"
            label={t('admin.user.timeoutLabel')}
            rules={[{ required: true }]}
          >
            <InputNumber min={5} max={1440} />
          </Form.Item>
          <Form.Item
            name="warning_minutes"
            label={t('admin.user.warningLabel')}
            rules={[{ required: true }]}
          >
            <InputNumber min={1} max={60} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" onClick={handleSaveSession} loading={savingSession}>
              {t('common.save')}
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* Users table */}
      <Card
        title={t('admin.user.management')}
        extra={
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              {t('admin.user.newUser')}
            </Button>
            <Button icon={<ReloadOutlined />} onClick={fetchUsers} loading={loading}>
              {t('common.refresh')}
            </Button>
          </Space>
        }
      >
        <Table<UserRow>
          dataSource={users}
          columns={columns}
          rowKey="id"
          loading={loading}
          size="small"
          pagination={{
            current: page,
            total,
            pageSize: 20,
            showSizeChanger: false,
            onChange: setPage,
          }}
        />
      </Card>

      <Modal
        title={editing ? t('admin.user.editUser', { username: editing.username }) : t('admin.user.newUser')}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText={editing ? t('common.save') : t('common.create')}
        cancelText={t('common.cancel')}
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <Form.Item
              name="username"
              label={t('admin.user.username')}
              rules={[{ required: true, message: t('admin.user.usernameRequired') }]}
            >
              <Input />
            </Form.Item>
          )}
          <Form.Item name="first_name" label={t('admin.user.firstName')}>
            <Input />
          </Form.Item>
          <Form.Item name="last_name" label={t('admin.user.lastName')}>
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label={editing ? t('admin.user.newPassword') : t('admin.user.password')}
            rules={editing ? [] : [{ required: true, message: t('admin.user.passwordRequired') }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="profile_id"
            label={t('admin.user.profile')}
            rules={[{ required: true, message: t('admin.user.profileRequired') }]}
          >
            <Select>
              {profiles.map((p) => (
                <Select.Option key={p.id} value={p.id}>
                  {p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          {editing && (
            <>
              <Form.Item name="is_active" label={t('admin.user.activeLabel')} valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item
                name="must_change_password"
                label={t('admin.user.forceChangePassword')}
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </div>
  );
}
