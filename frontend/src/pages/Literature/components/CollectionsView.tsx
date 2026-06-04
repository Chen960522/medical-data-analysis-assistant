/**
 * Literature collections view (我的收藏).
 *
 * Lists the user's collections (newest first, Req 10.38), each showing its
 * folders and saved items grouped by folder. Supports creating collections and
 * folders (Req 10.36, 10.39), filtering items by data source (Req 10.40),
 * searching within collections by title/keyword (Req 10.42), removing items
 * (Req 10.41) and deleting collections (with confirmation).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Collapse,
  Empty,
  Input,
  List,
  Segmented,
  Space,
  Tag,
  Typography,
} from 'antd';
import {
  DeleteOutlined,
  FolderOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';

import { LoadingIndicator } from '../../../components/Common';
import { useConfirm } from '../../../hooks/useConfirm';
import { useNotify } from '../../../hooks/useNotify';
import { literatureService } from '../../../services/literatureService';
import type {
  CollectedLiterature,
  Collection,
  DataSourceId,
} from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';

const { Text, Paragraph, Link } = Typography;

/** Source filter for collection items (Req 10.40). */
type CollectionSourceFilter = 'all' | DataSourceId;

export interface CollectionsViewProps {
  /** Bumped by the parent to trigger a reload (e.g. after a save). */
  reloadToken?: number;
}

/** Tag color for a saved item's source label (lower/upper tolerated). */
function itemSourceColor(source: string): string {
  return source.toLowerCase() === 'pubmed' ? 'geekblue' : 'volcano';
}

export function CollectionsView({ reloadToken = 0 }: CollectionsViewProps) {
  const notify = useNotify();
  const confirm = useConfirm();

  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState<CollectionSourceFilter>('all');
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');

  /** Load collections applying the active source/search filters (Req 10.40, 10.42). */
  const loadCollections = useCallback(async () => {
    setLoading(true);
    try {
      const response = await literatureService.listCollections({
        source: sourceFilter === 'all' ? undefined : sourceFilter,
        q: search.trim() || undefined,
      });
      setCollections(response.collections);
    } catch (err) {
      notify.error('无法加载文献收藏', err instanceof Error ? err.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [sourceFilter, search, notify]);

  useEffect(() => {
    void loadCollections();
  }, [loadCollections, reloadToken]);

  /** Create a new (empty) collection (Req 10.36). */
  const handleCreateCollection = useCallback(async () => {
    const name = newCollectionName.trim();
    if (!name) {
      return;
    }
    setCreating(true);
    try {
      await literatureService.createCollection({ name });
      notify.success('收藏夹已创建');
      setNewCollectionName('');
      await loadCollections();
    } catch (err) {
      notify.error('创建收藏夹失败', err instanceof Error ? err.message : undefined);
    } finally {
      setCreating(false);
    }
  }, [newCollectionName, notify, loadCollections]);

  /** Delete a collection after confirmation (Req 10.41). */
  const handleDeleteCollection = useCallback(
    async (collection: Collection) => {
      const confirmed = await confirm({
        title: '删除收藏夹',
        content: `确定要删除「${collection.name}」吗？其中的所有文件夹和收藏文献都将被移除。`,
        danger: true,
      });
      if (!confirmed) {
        return;
      }
      try {
        await literatureService.deleteCollection(collection.id);
        notify.success('收藏夹已删除');
        await loadCollections();
      } catch (err) {
        notify.error('删除收藏夹失败', err instanceof Error ? err.message : undefined);
      }
    },
    [confirm, notify, loadCollections],
  );

  /** Remove a saved item from its collection (Req 10.41). */
  const handleRemoveItem = useCallback(
    async (collection: Collection, item: CollectedLiterature) => {
      const confirmed = await confirm({
        title: '移除收藏',
        content: `确定要从「${collection.name}」中移除该文献吗？`,
        danger: true,
      });
      if (!confirmed) {
        return;
      }
      try {
        await literatureService.removeItem(collection.id, item.id);
        notify.success('已移除收藏');
        await loadCollections();
      } catch (err) {
        notify.error('移除失败', err instanceof Error ? err.message : undefined);
      }
    },
    [confirm, notify, loadCollections],
  );

  const totalItems = useMemo(
    () => collections.reduce((sum, collection) => sum + collection.items.length, 0),
    [collections],
  );

  /** Render the saved-item list, grouped by folder then unfiled. */
  const renderItems = (collection: Collection) => {
    if (collection.items.length === 0) {
      return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="该收藏夹暂无文献" />;
    }

    const folderName = new Map(collection.folders.map((f) => [f.id, f.name]));
    const grouped = new Map<string, CollectedLiterature[]>();
    for (const item of collection.items) {
      const key = item.folder_id ?? '__unfiled__';
      const list = grouped.get(key) ?? [];
      list.push(item);
      grouped.set(key, list);
    }

    const renderItemList = (items: CollectedLiterature[]) => (
      <List<CollectedLiterature>
        size="small"
        dataSource={items}
        renderItem={(item) => (
          <List.Item
            actions={[
              <Button
                key="remove"
                type="text"
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={() => void handleRemoveItem(collection, item)}
                aria-label={`移除收藏：${item.title}`}
              />,
            ]}
          >
            <List.Item.Meta
              title={
                <Space size={SPACING.xs} wrap>
                  <Tag color={itemSourceColor(item.source)}>{item.source.toUpperCase()}</Tag>
                  {item.doi ? (
                    <Link href={`https://doi.org/${item.doi}`} target="_blank" rel="noreferrer">
                      {item.title}
                    </Link>
                  ) : (
                    <Text>{item.title}</Text>
                  )}
                </Space>
              }
              description={
                <Space direction="vertical" size={0} style={{ width: '100%' }}>
                  <Text type="secondary">{item.authors || '未知作者'}</Text>
                  {item.journal || item.publication_date ? (
                    <Text type="secondary">
                      {[item.journal, item.publication_date].filter(Boolean).join(' · ')}
                    </Text>
                  ) : null}
                  {item.abstract ? (
                    <Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
                      {item.abstract}
                    </Paragraph>
                  ) : null}
                </Space>
              }
            />
          </List.Item>
        )}
      />
    );

    return (
      <Space direction="vertical" size={SPACING.sm} style={{ width: '100%' }}>
        {[...grouped.entries()].map(([key, items]) => (
          <div key={key}>
            {key !== '__unfiled__' ? (
              <Text strong>
                <FolderOutlined /> {folderName.get(key) ?? '文件夹'}
              </Text>
            ) : grouped.size > 1 ? (
              <Text strong>未分类</Text>
            ) : null}
            {renderItemList(items)}
          </div>
        ))}
      </Space>
    );
  };

  return (
    <Space direction="vertical" size={SPACING.lg} style={{ width: '100%' }}>
      {/* Toolbar: create collection, search, source filter, refresh. */}
      <Card variant="outlined">
        <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
          <Space wrap>
            <Space.Compact>
              <Input
                value={newCollectionName}
                onChange={(event) => setNewCollectionName(event.target.value)}
                placeholder="新建收藏夹名称"
                onPressEnter={() => void handleCreateCollection()}
                style={{ width: 220 }}
              />
              <Button
                type="primary"
                icon={<PlusOutlined />}
                loading={creating}
                disabled={!newCollectionName.trim()}
                onClick={() => void handleCreateCollection()}
              >
                新建收藏夹
              </Button>
            </Space.Compact>
            <Button icon={<ReloadOutlined />} onClick={() => void loadCollections()}>
              刷新
            </Button>
          </Space>

          <Space size={SPACING.md} wrap>
            <Input.Search
              allowClear
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onSearch={() => void loadCollections()}
              placeholder="按标题或关键词搜索收藏"
              style={{ width: 280 }}
            />
            <Space size={SPACING.xs}>
              <Text type="secondary">数据源：</Text>
              <Segmented<CollectionSourceFilter>
                value={sourceFilter}
                onChange={(value) => setSourceFilter(value as CollectionSourceFilter)}
                options={[
                  { label: '全部', value: 'all' },
                  { label: 'CNKI', value: 'cnki' },
                  { label: 'PubMed', value: 'pubmed' },
                ]}
              />
            </Space>
          </Space>
        </Space>
      </Card>

      {loading ? (
        <LoadingIndicator tip="正在加载文献收藏…" />
      ) : collections.length === 0 ? (
        <Empty description="暂无收藏夹，请先新建一个收藏夹并从搜索结果中收藏文献" />
      ) : (
        <>
          <Text type="secondary">
            共 {collections.length} 个收藏夹 · {totalItems} 篇文献
          </Text>
          <Collapse
            defaultActiveKey={collections.map((c) => c.id)}
            items={collections.map((collection) => ({
              key: collection.id,
              label: (
                <Space>
                  <Text strong>{collection.name}</Text>
                  <Tag>{collection.items.length} 篇</Tag>
                </Space>
              ),
              extra: (
                <Button
                  type="text"
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={(event) => {
                    event.stopPropagation();
                    void handleDeleteCollection(collection);
                  }}
                  aria-label={`删除收藏夹：${collection.name}`}
                />
              ),
              children: renderItems(collection),
            }))}
          />
        </>
      )}
    </Space>
  );
}

export default CollectionsView;
