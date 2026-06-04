/**
 * Analysis dimension list.
 *
 * Lists all active analysis dimensions, distinguishing system-generated default
 * dimensions from user-requested custom dimensions via a colored tag
 * (系统 / 自定义) so meaning is never conveyed by color alone (Req 9.19, 9.22).
 * Each row offers a remove action (Req 9.20); removal is confirmed by the caller
 * before invoking `onRemove`.
 *
 * Since the backend has no dedicated "list dimensions" endpoint, the dimension
 * set is maintained in the parent page's state: seeded from the analysis result
 * types (system dimensions) and appended to when the user adds custom dimensions
 * through the chat/dimension flow.
 */

import { Button, List, Space, Tag, Tooltip, Typography } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';

import { SPACING } from '../../../theme/tokens';
import type { Dimension } from '../../../types/analysis';

const { Text } = Typography;

export interface DimensionListProps {
  dimensions: Dimension[];
  /** Remove a dimension by id. Only user dimensions are removable. */
  onRemove?: (dimension: Dimension) => void;
  /** Id of a dimension currently being removed (shows a loading state). */
  removingId?: string | null;
}

/** Tag descriptor distinguishing system vs user dimensions (Req 9.22). */
function dimensionTag(type: Dimension['dimension_type']) {
  return type === 'system' ? (
    <Tag color="blue">系统</Tag>
  ) : (
    <Tag color="green">自定义</Tag>
  );
}

export function DimensionList({ dimensions, onRemove, removingId }: DimensionListProps) {
  if (dimensions.length === 0) {
    return (
      <Text type="secondary">
        暂无分析维度。完成分析后将展示系统生成的默认维度，您也可以通过对话添加自定义维度。
      </Text>
    );
  }

  return (
    <List<Dimension>
      size="small"
      dataSource={dimensions}
      renderItem={(dimension) => {
        const isUser = dimension.dimension_type === 'user';
        const isRemoving = removingId === dimension.id;
        return (
          <List.Item
            key={dimension.id}
            actions={
              isUser && onRemove
                ? [
                    <Tooltip key="remove" title="移除该维度">
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={isRemoving}
                        onClick={() => onRemove(dimension)}
                        aria-label={`移除维度：${dimension.name}`}
                      />
                    </Tooltip>,
                  ]
                : undefined
            }
          >
            <Space size={SPACING.sm} wrap>
              {dimensionTag(dimension.dimension_type)}
              <Text>{dimension.name}</Text>
            </Space>
          </List.Item>
        );
      }}
    />
  );
}

export default DimensionList;
