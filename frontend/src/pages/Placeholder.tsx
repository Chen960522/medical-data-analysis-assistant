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

export interface PlaceholderProps {
  title: string;
  description?: string;
}

export function Placeholder({ title, description }: PlaceholderProps) {
  return (
    <PageContainer title={title} description={description}>
      <Empty description="该功能模块将在后续任务中实现" />
    </PageContainer>
  );
}

export default Placeholder;
