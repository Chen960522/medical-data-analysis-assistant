import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
const { Text } = Typography;
/** Tag descriptor distinguishing system vs user dimensions (Req 9.22). */
function dimensionTag(type) {
    return type === 'system' ? (_jsx(Tag, { color: "blue", children: "\u7CFB\u7EDF" })) : (_jsx(Tag, { color: "green", children: "\u81EA\u5B9A\u4E49" }));
}
export function DimensionList({ dimensions, onRemove, removingId }) {
    if (dimensions.length === 0) {
        return (_jsx(Text, { type: "secondary", children: "\u6682\u65E0\u5206\u6790\u7EF4\u5EA6\u3002\u5B8C\u6210\u5206\u6790\u540E\u5C06\u5C55\u793A\u7CFB\u7EDF\u751F\u6210\u7684\u9ED8\u8BA4\u7EF4\u5EA6\uFF0C\u60A8\u4E5F\u53EF\u4EE5\u901A\u8FC7\u5BF9\u8BDD\u6DFB\u52A0\u81EA\u5B9A\u4E49\u7EF4\u5EA6\u3002" }));
    }
    return (_jsx(List, { size: "small", dataSource: dimensions, renderItem: (dimension) => {
            const isUser = dimension.dimension_type === 'user';
            const isRemoving = removingId === dimension.id;
            return (_jsx(List.Item, { actions: isUser && onRemove
                    ? [
                        _jsx(Tooltip, { title: "\u79FB\u9664\u8BE5\u7EF4\u5EA6", children: _jsx(Button, { type: "text", danger: true, size: "small", icon: _jsx(DeleteOutlined, {}), loading: isRemoving, onClick: () => onRemove(dimension), "aria-label": `移除维度：${dimension.name}` }) }, "remove"),
                    ]
                    : undefined, children: _jsxs(Space, { size: SPACING.sm, wrap: true, children: [dimensionTag(dimension.dimension_type), _jsx(Text, { children: dimension.name })] }) }, dimension.id));
        } }));
}
export default DimensionList;
