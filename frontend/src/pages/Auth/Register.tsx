/**
 * Registration page.
 *
 * Accepts email, password, and password confirmation. Enforces the same
 * password complexity policy as the backend (Req 8.4) with a live strength
 * meter, validates email format (Req 8.2), and surfaces conflict errors such as
 * an already-registered email (Req 8.3). On success the user is directed to the
 * login page with the verification-email notice (Req 8.5).
 */

import { useState } from 'react';
import { Alert, Button, Form, Input } from 'antd';
import { LockOutlined, MailOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';

import { AuthLayout } from './AuthLayout';
import { PasswordStrengthMeter } from '../../components/Auth/PasswordStrengthMeter';
import { authService } from '../../services/authService';
import { useNotify } from '../../hooks/useNotify';
import { isPasswordComplex } from '../../utils/validation';
import { SPACING } from '../../theme/tokens';

interface RegisterFormValues {
  email: string;
  password: string;
  confirmPassword: string;
}

export function Register() {
  const navigate = useNavigate();
  const notify = useNotify();
  const [form] = Form.useForm<RegisterFormValues>();
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (values: RegisterFormValues) => {
    setError(null);
    setSubmitting(true);
    try {
      const response = await authService.register({
        email: values.email,
        password: values.password,
      });
      notify.success(response.message ?? '注册成功，请查收验证邮件。');
      navigate('/login', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : '注册失败，请稍后重试。');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthLayout title="注册" subtitle="创建您的医学数据分析助手账户">
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

      <Form
        form={form}
        layout="vertical"
        requiredMark={false}
        onFinish={handleSubmit}
        disabled={submitting}
      >
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
          rules={[
            { required: true, message: '请输入密码' },
            {
              validator: (_, value: string) =>
                !value || isPasswordComplex(value)
                  ? Promise.resolve()
                  : Promise.reject(new Error('密码需至少 8 位，并包含大小写字母、数字和特殊字符')),
            },
          ]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="请设置密码"
            autoComplete="new-password"
            size="large"
            onChange={(e) => setPassword(e.target.value)}
          />
        </Form.Item>

        <PasswordStrengthMeter password={password} />

        <Form.Item
          label="确认密码"
          name="confirmPassword"
          dependencies={['password']}
          style={{ marginTop: SPACING.md }}
          rules={[
            { required: true, message: '请再次输入密码' },
            ({ getFieldValue }) => ({
              validator(_, value: string) {
                if (!value || getFieldValue('password') === value) {
                  return Promise.resolve();
                }
                return Promise.reject(new Error('两次输入的密码不一致'));
              },
            }),
          ]}
        >
          <Input.Password
            prefix={<LockOutlined />}
            placeholder="请再次输入密码"
            autoComplete="new-password"
            size="large"
          />
        </Form.Item>

        <Form.Item style={{ marginBottom: SPACING.sm }}>
          <Button type="primary" htmlType="submit" block size="large" loading={submitting}>
            注册
          </Button>
        </Form.Item>
      </Form>

      <div style={{ textAlign: 'center' }}>
        已有账户？<Link to="/login">返回登录</Link>
      </div>
    </AuthLayout>
  );
}

export default Register;
