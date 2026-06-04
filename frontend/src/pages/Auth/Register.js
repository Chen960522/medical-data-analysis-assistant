import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
export function Register() {
    const navigate = useNavigate();
    const notify = useNotify();
    const [form] = Form.useForm();
    const [password, setPassword] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);
    const handleSubmit = async (values) => {
        setError(null);
        setSubmitting(true);
        try {
            const response = await authService.register({
                email: values.email,
                password: values.password,
            });
            notify.success(response.message ?? '注册成功，请查收验证邮件。');
            navigate('/login', { replace: true });
        }
        catch (err) {
            setError(err instanceof Error ? err.message : '注册失败，请稍后重试。');
        }
        finally {
            setSubmitting(false);
        }
    };
    return (_jsxs(AuthLayout, { title: "\u6CE8\u518C", subtitle: "\u521B\u5EFA\u60A8\u7684\u533B\u5B66\u6570\u636E\u5206\u6790\u52A9\u624B\u8D26\u6237", children: [error ? (_jsx(Alert, { type: "error", message: error, showIcon: true, closable: true, style: { marginBottom: SPACING.md }, onClose: () => setError(null) })) : null, _jsxs(Form, { form: form, layout: "vertical", requiredMark: false, onFinish: handleSubmit, disabled: submitting, children: [_jsx(Form.Item, { label: "\u90AE\u7BB1", name: "email", rules: [
                            { required: true, message: '请输入邮箱地址' },
                            { type: 'email', message: '邮箱格式不正确' },
                        ], children: _jsx(Input, { prefix: _jsx(MailOutlined, {}), placeholder: "you@example.com", autoComplete: "email", size: "large" }) }), _jsx(Form.Item, { label: "\u5BC6\u7801", name: "password", rules: [
                            { required: true, message: '请输入密码' },
                            {
                                validator: (_, value) => !value || isPasswordComplex(value)
                                    ? Promise.resolve()
                                    : Promise.reject(new Error('密码需至少 8 位，并包含大小写字母、数字和特殊字符')),
                            },
                        ], children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "\u8BF7\u8BBE\u7F6E\u5BC6\u7801", autoComplete: "new-password", size: "large", onChange: (e) => setPassword(e.target.value) }) }), _jsx(PasswordStrengthMeter, { password: password }), _jsx(Form.Item, { label: "\u786E\u8BA4\u5BC6\u7801", name: "confirmPassword", dependencies: ['password'], style: { marginTop: SPACING.md }, rules: [
                            { required: true, message: '请再次输入密码' },
                            ({ getFieldValue }) => ({
                                validator(_, value) {
                                    if (!value || getFieldValue('password') === value) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject(new Error('两次输入的密码不一致'));
                                },
                            }),
                        ], children: _jsx(Input.Password, { prefix: _jsx(LockOutlined, {}), placeholder: "\u8BF7\u518D\u6B21\u8F93\u5165\u5BC6\u7801", autoComplete: "new-password", size: "large" }) }), _jsx(Form.Item, { style: { marginBottom: SPACING.sm }, children: _jsx(Button, { type: "primary", htmlType: "submit", block: true, size: "large", loading: submitting, children: "\u6CE8\u518C" }) })] }), _jsxs("div", { style: { textAlign: 'center' }, children: ["\u5DF2\u6709\u8D26\u6237\uFF1F", _jsx(Link, { to: "/login", children: "\u8FD4\u56DE\u767B\u5F55" })] })] }));
}
export default Register;
