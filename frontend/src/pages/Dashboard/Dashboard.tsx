/**
 * Main dashboard page.
 *
 * Landing page after login. Provides the data upload entry point and a brief
 * orientation to the platform's primary modules. Full analytics widgets are
 * added in later tasks; this establishes the framework and demonstrates the
 * shared design-system components.
 */

import { Button, Card, Col, Row, Space } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';

import { PageContainer } from '../../components/Common';
import { FileUpload } from '../../components/Upload/FileUpload';
import { SPACING } from '../../theme/tokens';

export function Dashboard() {
  const navigate = useNavigate();

  return (
    <PageContainer
      title="仪表盘"
      description="欢迎使用医学数据分析助手。上传数据文件开始 AI 智能分析。"
    >
      <Row gutter={[SPACING.lg, SPACING.lg]}>
        <Col xs={24} lg={14}>
          <Card title="上传医学数据" variant="outlined">
            <FileUpload onUploaded={() => navigate('/analysis')} />
            <Space style={{ marginTop: SPACING.md }}>
              <Button
                type="primary"
                icon={<ArrowRightOutlined />}
                onClick={() => navigate('/analysis')}
              >
                前往数据分析
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="快速开始" variant="outlined">
            <ul style={{ paddingInlineStart: SPACING.lg, margin: 0, lineHeight: 2 }}>
              <li>上传 CSV、Excel 或 JSON 格式的医学数据</li>
              <li>由 AI 自动进行多维度统计分析</li>
              <li>查看可视化图表并导出分析报告</li>
              <li>检索 CNKI / PubMed 文献并翻译 PDF 文献</li>
            </ul>
          </Card>
        </Col>
      </Row>
    </PageContainer>
  );
}

export default Dashboard;
