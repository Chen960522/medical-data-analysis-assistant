/**
 * Password strength meter.
 *
 * Visualizes how well a password meets the complexity policy (Req 8.4) and
 * lists each rule with a pass/fail indicator. Status is conveyed with both an
 * icon and text, not color alone (Req 12.34).
 */

import { Progress, Space, Typography } from 'antd';
import { CheckCircleTwoTone, CloseCircleOutlined } from '@ant-design/icons';

import { PASSWORD_MIN_LENGTH, checkPassword, passwordStrength } from '../../utils/validation';
import type { PasswordStrength } from '../../utils/validation';
import { SPACING } from '../../theme/tokens';

const { Text } = Typography;

const STRENGTH_META: Record<PasswordStrength, { percent: number; color: string; label: string }> = {
  weak: { percent: 33, color: '#ff4d4f', label: '弱' },
  medium: { percent: 66, color: '#faad14', label: '中' },
  strong: { percent: 100, color: '#52c41a', label: '强' },
};

export interface PasswordStrengthMeterProps {
  password: string;
}

function Rule({ ok, text }: { ok: boolean; text: string }) {
  return (
    <Space size={4}>
      {ok ? (
        <CheckCircleTwoTone twoToneColor="#52c41a" />
      ) : (
        <CloseCircleOutlined style={{ color: '#bfbfbf' }} />
      )}
      <Text type={ok ? 'success' : 'secondary'} style={{ fontSize: 12 }}>
        {text}
      </Text>
    </Space>
  );
}

export function PasswordStrengthMeter({ password }: PasswordStrengthMeterProps) {
  if (!password) {
    return null;
  }

  const checks = checkPassword(password);
  const meta = STRENGTH_META[passwordStrength(password)];

  return (
    <div style={{ marginTop: SPACING.sm }} aria-live="polite">
      <Progress
        percent={meta.percent}
        strokeColor={meta.color}
        showInfo={false}
        size="small"
        aria-label={`密码强度：${meta.label}`}
      />
      <Text style={{ fontSize: 12 }} type="secondary">
        密码强度：{meta.label}
      </Text>
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: `${SPACING.xs}px ${SPACING.md}px`,
          marginTop: SPACING.xs,
        }}
      >
        <Rule ok={checks.length} text={`至少 ${PASSWORD_MIN_LENGTH} 个字符`} />
        <Rule ok={checks.uppercase} text="含大写字母" />
        <Rule ok={checks.lowercase} text="含小写字母" />
        <Rule ok={checks.digit} text="含数字" />
        <Rule ok={checks.special} text="含特殊字符" />
      </div>
    </div>
  );
}

export default PasswordStrengthMeter;
