import {
  ModalForm,
  ProCard,
  ProFormDigit,
  ProFormSelect,
  ProFormText,
  ProFormTextArea,
} from '@ant-design/pro-components';
import { App, Button } from 'antd';
import React, { useState } from 'react';
import {
  attackSurfaceOptions,
  confidenceOptions,
  exploitStatusOptions,
  manualCategoryOptions,
  riskLevelOptions,
  severityOptions,
  vehicleComponentOptions,
} from '@/constants/labels';
import { createManualEntry } from '@/services/manualEntries';

export interface ManualEntryCreateButtonProps {
  /** 按钮文案 */
  text?: string;
  type?: 'primary' | 'default' | 'dashed';
  icon?: React.ReactNode;
  /** 创建成功后的回调（如刷新列表） */
  onSuccess?: () => void;
}

const initialValues: Partial<API.ManualEntryCreateParams> = {
  category: 'vulnerability',
  severity: 'unknown',
  exploit_status: 'unknown',
  confidence: 'medium',
  risk_level: 'info',
};

/**
 * 手工录入创建表单（弹窗）：字段分组与校验对齐后端 manual-entries 契约。
 */
const ManualEntryCreateButton: React.FC<ManualEntryCreateButtonProps> = ({
  text = '手工录入',
  type = 'primary',
  icon,
  onSuccess,
}) => {
  const { message } = App.useApp();
  const [open, setOpen] = useState(false);

  const handleSubmit = async (values: API.ManualEntryCreateParams) => {
    if (!values.source_name && !values.source_url) {
      message.error('来源名称与来源 URL 至少填写一项');
      return false;
    }
    try {
      const created = await createManualEntry({
        ...initialValues,
        ...values,
        tags: values.tags ?? [],
      } as API.ManualEntryCreateParams);
      message.success(`手工录入「${created.title}」提交成功`);
      onSuccess?.();
      return true;
    } catch {
      message.error('提交失败，请检查字段后重试。');
      return false;
    }
  };

  return (
    <ModalForm<API.ManualEntryCreateParams>
      title="新建手工录入"
      width={760}
      trigger={
        <Button type={type} icon={icon}>
          {text}
        </Button>
      }
      open={open}
      onOpenChange={setOpen}
      modalProps={{ destroyOnHidden: true }}
      initialValues={initialValues}
      onFinish={handleSubmit}
      layout="horizontal"
      labelCol={{ span: 6 }}
      wrapperCol={{ span: 16 }}
    >
      <ProCard style={{ marginBottom: 16 }}>
        <ProFormSelect
          name="category"
          label="类别"
          options={manualCategoryOptions.map(([value, label]) => ({
            value,
            label,
          }))}
          rules={[{ required: true, message: '请选择类别' }]}
        />
        <ProFormText
          name="title"
          label="标题"
          placeholder="至少 3 个字符"
          rules={[
            { required: true, message: '请输入标题' },
            { min: 3, message: '标题至少 3 个字符' },
            { max: 500, message: '标题最多 500 个字符' },
          ]}
        />
        <ProFormTextArea
          name="summary"
          label="摘要"
          placeholder="一句话概述该情报的核心内容"
          fieldProps={{ rows: 3 }}
          rules={[{ required: true, message: '请输入摘要' }]}
        />
        <ProFormSelect
          name="status"
          label="状态"
          placeholder="默认有效"
          allowClear
          options={[
            ['active', '有效'],
            ['under_review', '复核中'],
            ['resolved', '已解决'],
            ['dismissed', '已忽略'],
          ].map(([value, label]) => ({ value, label }))}
        />
      </ProCard>

      <ProCard style={{ marginBottom: 16 }} title="来源归因" headerBordered>
        <ProFormText
          name="source_name"
          label="来源名称"
          placeholder="厂商公告、内部分析"
          rules={[{ max: 160, message: '来源名称最多 160 个字符' }]}
        />
        <ProFormText
          name="source_url"
          label="来源 URL"
          placeholder="https://example.test/advisory"
          rules={[
            {
              validator: (_, value) => {
                // 后端要求来源名称与 URL 至少提供其一
                if (!value) {
                  return Promise.resolve();
                }
                if (
                  /\s/.test(String(value)) ||
                  !String(value).includes('://')
                ) {
                  return Promise.reject(
                    new Error('来源 URL 必须是绝对地址且不含空格'),
                  );
                }
                return Promise.resolve();
              },
            },
            { max: 1000, message: '来源 URL 最多 1000 个字符' },
          ]}
        />
      </ProCard>

      <ProCard style={{ marginBottom: 16 }} title="漏洞标识" headerBordered>
        <ProFormText
          name="cve_id"
          label="CVE"
          placeholder="CVE-2026-0001"
          rules={[
            {
              pattern: /^CVE-\d{4}-\d{4,}$/i,
              message: 'CVE 编号需符合 CVE-YYYY-NNNN 格式',
            },
          ]}
        />
        <ProFormText name="cwe_id" label="CWE" placeholder="CWE-79" />
        <ProFormDigit
          name="cvss_score"
          label="CVSS 分"
          placeholder="0-10"
          fieldProps={{ precision: 1 }}
          min={0}
          max={10}
        />
        <ProFormText
          name="cvss_vector"
          label="CVSS 向量"
          placeholder="CVSS:3.1/..."
        />
      </ProCard>

      <ProCard style={{ marginBottom: 16 }} title="影响范围" headerBordered>
        <ProFormText name="affected_vendor" label="厂商" placeholder="厂商" />
        <ProFormText
          name="affected_product"
          label="产品"
          placeholder="产品或系统"
        />
        <ProFormText
          name="affected_version"
          label="版本"
          placeholder="版本范围"
        />
        <ProFormSelect
          name="vehicle_component"
          label="车辆组件"
          allowClear
          options={vehicleComponentOptions.map(([value, label]) => ({
            value,
            label,
          }))}
        />
        <ProFormSelect
          name="attack_surface"
          label="攻击面"
          allowClear
          options={attackSurfaceOptions.map(([value, label]) => ({
            value,
            label,
          }))}
        />
      </ProCard>

      <ProCard title="风险评估" headerBordered>
        <ProFormSelect
          name="severity"
          label="严重度"
          options={severityOptions.map(([value, label]) => ({ value, label }))}
        />
        <ProFormSelect
          name="exploit_status"
          label="利用状态"
          options={exploitStatusOptions.map(([value, label]) => ({
            value,
            label,
          }))}
        />
        <ProFormSelect
          name="confidence"
          label="可信度"
          options={confidenceOptions.map(([value, label]) => ({
            value,
            label,
          }))}
        />
        <ProFormDigit
          name="risk_score"
          label="风险分"
          placeholder="0-100"
          min={0}
          max={100}
        />
        <ProFormSelect
          name="risk_level"
          label="风险等级"
          options={riskLevelOptions.map(([value, label]) => ({ value, label }))}
        />
        <ProFormSelect
          name="tags"
          label="标签"
          mode="tags"
          placeholder="回车添加标签，不要填写密钥"
          fieldProps={{ tokenSeparators: [','] }}
        />
      </ProCard>
    </ModalForm>
  );
};

export default ManualEntryCreateButton;
