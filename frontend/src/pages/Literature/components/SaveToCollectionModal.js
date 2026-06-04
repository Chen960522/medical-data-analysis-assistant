import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
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
import { SPACING } from '../../../theme/tokens';
const { Text } = Typography;
export function SaveToCollectionModal({ open, record, collections, onClose, onSaved, }) {
    const notify = useNotify();
    const [collectionId, setCollectionId] = useState(undefined);
    const [folderId, setFolderId] = useState(undefined);
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
    const selectedCollection = useMemo(() => collections.find((c) => c.id === collectionId) ?? null, [collections, collectionId]);
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
        }
        catch (err) {
            notify.error('创建收藏夹失败', err instanceof Error ? err.message : undefined);
        }
        finally {
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
        }
        catch (err) {
            notify.error('创建文件夹失败', err instanceof Error ? err.message : undefined);
        }
        finally {
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
        }
        catch (err) {
            notify.error('收藏失败', err instanceof Error ? err.message : undefined);
        }
        finally {
            setSaving(false);
        }
    };
    const hasCollections = collections.length > 0;
    return (_jsx(Modal, { title: "\u6536\u85CF\u6587\u732E", open: open, onCancel: onClose, onOk: () => void handleSave(), okText: "\u4FDD\u5B58", cancelText: "\u53D6\u6D88", okButtonProps: { disabled: !collectionId, loading: saving }, confirmLoading: saving, children: record ? (_jsxs(Space, { direction: "vertical", size: SPACING.md, style: { width: '100%' }, children: [_jsx(Text, { type: "secondary", ellipsis: true, children: record.title }), _jsxs(Form, { layout: "vertical", children: [hasCollections ? (_jsx(Form.Item, { label: "\u9009\u62E9\u6536\u85CF\u5939", style: { marginBottom: SPACING.sm }, children: _jsx(Select, { value: collectionId, onChange: (value) => {
                                    setCollectionId(value);
                                    setFolderId(undefined);
                                }, options: collections.map((c) => ({ value: c.id, label: c.name })), placeholder: "\u8BF7\u9009\u62E9\u6536\u85CF\u5939" }) })) : (_jsx(Text, { type: "secondary", children: "\u60A8\u8FD8\u6CA1\u6709\u6536\u85CF\u5939\uFF0C\u8BF7\u5148\u521B\u5EFA\u4E00\u4E2A\u3002" })), _jsx(Form.Item, { label: "\u65B0\u5EFA\u6536\u85CF\u5939", style: { marginBottom: SPACING.sm }, children: _jsxs(Space.Compact, { style: { width: '100%' }, children: [_jsx(Input, { value: newCollectionName, onChange: (event) => setNewCollectionName(event.target.value), placeholder: "\u8F93\u5165\u65B0\u6536\u85CF\u5939\u540D\u79F0", onPressEnter: () => void handleCreateCollection() }), _jsx(Button, { icon: _jsx(PlusOutlined, {}), loading: creatingCollection, disabled: !newCollectionName.trim(), onClick: () => void handleCreateCollection(), children: "\u521B\u5EFA" })] }) }), selectedCollection ? (_jsxs(_Fragment, { children: [_jsx(Divider, { style: { margin: `${SPACING.sm}px 0` } }), _jsx(Form.Item, { label: "\u9009\u62E9\u6587\u4EF6\u5939\uFF08\u53EF\u9009\uFF09", style: { marginBottom: SPACING.sm }, children: _jsx(Select, { allowClear: true, value: folderId, onChange: (value) => setFolderId(value), options: selectedCollection.folders.map((f) => ({
                                            value: f.id,
                                            label: f.name,
                                        })), placeholder: "\u4E0D\u5206\u7C7B\uFF08\u9ED8\u8BA4\uFF09" }) }), _jsx(Form.Item, { label: "\u65B0\u5EFA\u6587\u4EF6\u5939", style: { marginBottom: 0 }, children: _jsxs(Space.Compact, { style: { width: '100%' }, children: [_jsx(Input, { value: newFolderName, onChange: (event) => setNewFolderName(event.target.value), placeholder: "\u8F93\u5165\u65B0\u6587\u4EF6\u5939\u540D\u79F0", onPressEnter: () => void handleCreateFolder() }), _jsx(Button, { icon: _jsx(PlusOutlined, {}), loading: creatingFolder, disabled: !newFolderName.trim(), onClick: () => void handleCreateFolder(), children: "\u521B\u5EFA" })] }) })] })) : null] })] })) : null }));
}
export default SaveToCollectionModal;
