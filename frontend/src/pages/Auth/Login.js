import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
export function Login() {
    const navigate = useNavigate();
    const location = useLocation();
    const login = useAuthStore((state) => state.login);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const redirectTo = location.state?.from?.pathname ?? '/dashboard';
    const handleSubmit = async (values) => {
        setError(null);
        setSubmitting(true);
        try {
            await login(values);
            navigate(redirectTo, { replace: true });
        }
        catch (err) {
            if (err instanceof ApiError && err.status === 423) {
                setError('账户已被临时锁定，请稍后再试。');
            }
            else if (err instanceof Error) {
                setError(err.message);
            }
            else {
                setError('登录失败，请稍后重试。');
            }
        }
        finally {
            setSubmitting(false);
        }
    };
    return (_jsxs(AuthLayout, { title: "\u767B\u5F55", subtitle: "\u533B\u5B66\u6570\u636E\u5206\u6790\u52A9\u624B", children: [error ? (_jsx(Alert, { type: "error", message: error, showIcon: true, closable: true, style: { marginBottom: SPACING.md }, onClose: () => setError(null) })) : null, _jsxs(Form, { layout: "vertical", requiredMark: false, onFinish: handleSubmit, disabled: submitting, children: [_jsx(Form.Item, { label: "\u90AE\u7BB1", name: "email", rules: [
                            { required: true, message: '请输入邮箱地址' },
                            { type: 'email', message: '邮箱格式不正确' },
                        ], children: _jsx(Input, { prefix: _jsx(MailOutlined, {}), placeholder: "you@example.com", autoComplete: "email", size: "large" }) }), _jsx(Form.Item, { label: "\u5BC6\u7801", name: "password", rules: [{ required: true, message: '请输入密码' }], children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "\u8BF7\u8F93\u5165\u5BC6\u7801", autoComplete: "current-password", size: "large" }) }), _jsx(Form.Item, { style: { marginBottom: SPACING.sm }, children: _jsx(Button, { type: "primary", htmlType: "submit", block: true, size: "large", loading: submitting, children: "\u767B\u5F55" }) })] }), _jsxs("div", { style: { textAlign: 'center' }, children: ["\u8FD8\u6CA1\u6709\u8D26\u6237\uFF1F", _jsx(Link, { to: "/register", children: "\u7ACB\u5373\u6CE8\u518C" })] })] }));
}
export default Login;
