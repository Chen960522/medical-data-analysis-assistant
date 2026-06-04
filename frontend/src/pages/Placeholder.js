import { jsx as _jsx } from "react/jsx-runtime";
/**
 * Generic placeholder page.
 *
 * Used for primary modules whose full UIs are implemented in later tasks
 * (data analysis dashboard, literature search, PDF translation, history). It
 * keeps the navigation, routing, and layout fully functional now while clearly
 * marking work that is still pending.
 */
import { Empty } from 'antd';
import { PageContainer } from '../components/Common';
export function Placeholder({ title, description }) {
    return (_jsx(PageContainer, { title: title, description: description, children: _jsx(Empty, { description: "\u8BE5\u529F\u80FD\u6A21\u5757\u5C06\u5728\u540E\u7EED\u4EFB\u52A1\u4E2D\u5B9E\u73B0" }) }));
}
export default Placeholder;
