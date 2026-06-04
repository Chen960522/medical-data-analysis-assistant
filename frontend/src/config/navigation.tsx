/**
 * Primary navigation configuration.
 *
 * Defines the persistent main navigation structure giving access to all primary
 * functional modules within 2 clicks (Req 12.18). Each item carries an icon from
 * a single unified icon set (outline style, Req 12.12) and a route path used for
 * active-item highlighting (Req 12.19) and breadcrumbs (Req 12.20).
 */

import {
  DashboardOutlined,
  BarChartOutlined,
  BookOutlined,
  TranslationOutlined,
  HistoryOutlined,
  FileSyncOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';

export interface NavItem {
  key: string;
  /** Route path used by react-router. */
  path: string;
  /** Human-readable label (also used in breadcrumbs). */
  label: string;
  icon: ReactNode;
}

export const NAV_ITEMS: NavItem[] = [
  {
    key: 'dashboard',
    path: '/dashboard',
    label: '仪表盘',
    icon: <DashboardOutlined />,
  },
  {
    key: 'analysis',
    path: '/analysis',
    label: '数据分析',
    icon: <BarChartOutlined />,
  },
  {
    key: 'literature',
    path: '/literature',
    label: '文献检索',
    icon: <BookOutlined />,
  },
  {
    key: 'translation',
    path: '/translation',
    label: 'PDF 翻译',
    icon: <TranslationOutlined />,
  },
  {
    key: 'history',
    path: '/history',
    label: '分析历史',
    icon: <HistoryOutlined />,
  },
  {
    key: 'translation-history',
    path: '/translation-history',
    label: '翻译历史',
    icon: <FileSyncOutlined />,
  },
];

/** Lookup map from route path to its human-readable label (for breadcrumbs). */
export const PATH_LABEL_MAP: Record<string, string> = NAV_ITEMS.reduce<Record<string, string>>(
  (acc, item) => {
    acc[item.path] = item.label;
    return acc;
  },
  {},
);
