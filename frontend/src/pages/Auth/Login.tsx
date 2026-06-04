/**
 * Login page.
 *
 * Accepts email + password credentials, shows generic error feedback
 * (the backend deliberately does not reveal which field is wrong, Req 8.9),
 * and links to the registration page. On success the user is redirected to the
 * originally requested page or the dashboard (Req 8.8).
 */

import { useState } from 'react';
import { Alert, Button, Form, Input } from 'antd';
import { LockOutlined, MailOutlined } from '@ant-design/icons';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { AuthLayout } from './AuthLayout';
import { useAuthStore } from '../../stores/authStore';
import { ApiError } from '../../services/apiClient';
import { SPACING } from '../../theme/tokens';
import type { LoginRequest } from '../../types/auth';

interface LocationState {
  from?: { pathname: string };
}

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectTo = (location.state as LocationState | null)?.from?.pathname ?? '/dashboard';

  const handleSubmit = async (values: LoginRequest) => {
    setError(null);
    setSubmitting(true);
    try {
      await login(values);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) {
        setError('账户已被临时锁定，请稍后再试。');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('登录失败，请稍后重试。');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="登录" subtitle="医学数据分析助手">
      {error ? (
        <Alert
          type="error"
          message={error}
          showIcon
          closable
          style={{ marginBottom: SPACING.md }}
          onClose={() => setError(null)}
        />
      ) : null}

      <Form layout="vertical" requiredMark={false} onFinish={handleSubmit} disabled={submitting}>
        <Form.Item
          label="邮箱"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱地址' },
            { type: 'email', message: '邮箱格式不正确' },
          ]}
        >
          <Input
            prefix={<MailOutlined />}
            placeholder="you@example.com"
            autoComplete="email"
            size="large"
          />
        </Form.Item>

        <Form.Item
          label="密码"
          name="password"
          rules={[{ required: true, message: '请输入密码' }]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="请输入密码"
            autoComplete="current-password"
            size="large"
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: SPACING.sm }}>
          <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
            登录
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: 'center' }}>
        还没有账户？<Link to="/register">立即注册</Link>
      </div>
    </AuthLayout>
  );
}

export default Login;
