/**
 * Save-to-collection modal.
 *
 * Lets the user save a `LiteratureRecord` to a collection (Req 10.36): pick an
 * existing collection or create a new one, optionally choose a folder within
 * it, then save (`POST .../collections/{id}/items`). The data-source label is
 * preserved with the saved record. A confirmation message is shown on success
 * (Req 10.37).
 *
 * When the user has no collection yet, the modal supports creating one inline
 * (Req 10.36). It also supports creating a new folder within the selected
 * collection (Req 10.39).
 */

import { useEffect, useMemo, useState } from 'react';
import { Button, Divider, Form, Input, Modal, Select, Space, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

import { useNotify } from '../../../hooks/useNotify';
import { literatureService } from '../../../services/literatureService';
import type { Collection, LiteratureRecord } from '../../../types/literature';
import { SPACING } from '../../../theme/tokens';

const { Text } = Typography;

export interface SaveToCollectionModalProps {
  open: boolean;
  record: LiteratureRecord | null;
  collections: Collection[];
  onClose: () => void;
  /** Invoked after a successful save / collection mutation so the parent refreshes. */
  onSaved: () => void;
}

export function SaveToCollectionModal({
  open,
  record,
  collections,
  onClose,
  onSaved,
}: SaveToCollectionModalProps) {
  const notify = useNotify();

  const [collectionId, setCollectionId] = useState<string | undefined>(undefined);
  const [folderId, setFolderId] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  // Inline new-collection / new-folder inputs.
  const [newCollectionName, setNewCollectionName] = useState('');
  const [creatingCollection, setCreatingCollection] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [creatingFolder, setCreatingFolder] = useState(false);

  // Default the selected collection to the first available one when opened.
  useEffect(() => {
    if (open) {
      setCollectionId(collections[0]?.id);
      setFolderId(undefined);
      setNewCollectionName('');
      setNewFolderName('');
    }
  }, [open, collections]);

  const selectedCollection = useMemo(
    () => collections.find((c) => c.id === collectionId) ?? null,
    [collections, collectionId],
  );

  /** Create a new collection inline (Req 10.36). */
  const handleCreateCollection = async () => {
    const name = newCollectionName.trim();
    if (!name) {
      return;
    }
    setCreatingCollection(true);
    try {
      const created = await literatureService.createCollection({ name });
      notify.success('收藏夹已创建');
      setNewCollectionName('');
      setCollectionId(created.id);
      setFolderId(undefined);
      onSaved();
    } catch (err) {
      notify.error('创建收藏夹失败', err instanceof Error ? err.message : undefined);
    } finally {
      setCreatingCollection(false);
    }
  };

  /** Create a new folder within the selected collection (Req 10.39). */
  const handleCreateFolder = async () => {
    const name = newFolderName.trim();
    if (!name || !collectionId) {
      return;
    }
    setCreatingFolder(true);
    try {
      const folder = await literatureService.createFolder({ collection_id: collectionId, name });
      notify.success('文件夹已创建');
      setNewFolderName('');
      setFolderId(folder.id);
      onSaved();
    } catch (err) {
      notify.error('创建文件夹失败', err instanceof Error ? err.message : undefined);
    } finally {
      setCreatingFolder(false);
    }
  };

  /** Save the record into the chosen collection/folder (Req 10.36, 10.37). */
  const handleSave = async () => {
    if (!record || !collectionId) {
      return;
    }
    setSaving(true);
    try {
      await literatureService.saveItem(collectionId, {
        title: record.title,
        authors: record.authors,
        journal: record.journal ?? undefined,
        publication_date: record.publication_date ?? undefined,
        abstract: record.abstract ?? undefined,
        doi: record.doi ?? undefined,
        source: record.data_source,
        external_id: record.external_id ?? undefined,
        folder_id: folderId ?? undefined,
      });
      notify.success('已收藏到文献收藏夹');
      onSaved();
      onClose();
    } catch (err) {
      notify.error('收藏失败', err instanceof Error ? err.message : undefined);
    } finally {
      setSaving(false);
    }
  };

  const hasCollections = collections.length > 0;

  return (
    <Modal
      title="收藏文献"
      open={open}
      onCancel={onClose}
      onOk={() => void handleSave()}
      okText="保存"
      cancelText="取消"
      okButtonProps={{ disabled: !collectionId, loading: saving }}
      confirmLoading={saving}
    >
      {record ? (
        <Space direction="vertical" size={SPACING.md} style={{ width: '100%' }}>
          <Text type="secondary" ellipsis>
            {record.title}
          </Text>

          <Form layout="vertical">
            {hasCollections ? (
              <Form.Item label="选择收藏夹" style={{ marginBottom: SPACING.sm }}>
                <Select
                  value={collectionId}
                  onChange={(value) => {
                    setCollectionId(value);
                    setFolderId(undefined);
                  }}
                  options={collections.map((c) => ({ value: c.id, label: c.name }))}
                  placeholder="请选择收藏夹"
                />
              </Form.Item>
            ) : (
              <Text type="secondary">您还没有收藏夹，请先创建一个。</Text>
            )}

            {/* Create a new collection inline (Req 10.36). */}
            <Form.Item label="新建收藏夹" style={{ marginBottom: SPACING.sm }}>
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  value={newCollectionName}
                  onChange={(event) => setNewCollectionName(event.target.value)}
                  placeholder="输入新收藏夹名称"
                  onPressEnter={() => void handleCreateCollection()}
                />
                <Button
                  icon={<PlusOutlined />}
                  loading={creatingCollection}
                  disabled={!newCollectionName.trim()}
                  onClick={() => void handleCreateCollection()}
                >
                  创建
                </Button>
              </Space.Compact>
            </Form.Item>

            {/* Folder selection + creation within the selected collection (Req 10.39). */}
            {selectedCollection ? (
              <>
                <Divider style={{ margin: `${SPACING.sm}px 0` }} />
                <Form.Item label="选择文件夹（可选）" style={{ marginBottom: SPACING.sm }}>
                  <Select
                    allowClear
                    value={folderId}
                    onChange={(value) => setFolderId(value)}
                    options={selectedCollection.folders.map((f) => ({
                      value: f.id,
                      label: f.name,
                    }))}
                    placeholder="不分类（默认）"
                  />
                </Form.Item>
                <Form.Item label="新建文件夹" style={{ marginBottom: 0 }}>
                  <Space.Compact style={{ width: '100%' }}>
                    <Input
                      value={newFolderName}
                      onChange={(event) => setNewFolderName(event.target.value)}
                      placeholder="输入新文件夹名称"
                      onPressEnter={() => void handleCreateFolder()}
                    />
                    <Button
                      icon={<PlusOutlined />}
                      loading={creatingFolder}
                      disabled={!newFolderName.trim()}
                      onClick={() => void handleCreateFolder()}
                    >
                      创建
                    </Button>
                  </Space.Compact>
                </Form.Item>
              </>
            ) : null}
          </Form>
        </Space>
      ) : null}
    </Modal>
  );
}

export default SaveToCollectionModal;
