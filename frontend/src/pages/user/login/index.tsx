import { LockOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons';
import { LoginForm, ProFormText } from '@ant-design/pro-components';
import { Helmet, history, useModel } from '@umijs/max';
import { App, Button } from 'antd';
import React, { startTransition } from 'react';
import { Footer } from '@/components';
import { login } from '@/services/auth';
import { storeToken } from '@/utils/token';
import Settings from '../../../../config/defaultSettings';

/**
 * 校验回跳地址，仅允许同源相对路径，防止开放重定向。
 */
const getSafeRedirectUrl = (redirect: string | null): string => {
  if (!redirect?.startsWith('/') || redirect.startsWith('//')) {
    return '/';
  }
  try {
    const parsed = new URL(redirect, window.location.origin);
    if (parsed.origin !== window.location.origin) {
      return '/';
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return '/';
  }
};

const Login: React.FC = () => {
  const { initialState, setInitialState } = useModel('@@initialState');
  const { message } = App.useApp();

  const handleSubmit = async (values: API.LoginParams) => {
    try {
      const result = await login({
        email: values.email.trim(),
        password: values.password,
      });
      storeToken(result.access_token);
      message.success('登录成功');
      const userInfo = await initialState?.fetchUserInfo?.();
      if (userInfo) {
        startTransition(() => {
          setInitialState((s) => ({ ...s, currentUser: userInfo }));
        });
      }
      const urlParams = new URL(window.location.href).searchParams;
      window.location.href = getSafeRedirectUrl(urlParams.get('redirect'));
      return;
    } catch (error: any) {
      const serverMessage =
        error?.response?.data?.detail?.error?.message ||
        error?.response?.data?.detail;
      message.error(
        typeof serverMessage === 'string' && serverMessage.trim()
          ? serverMessage
          : '登录失败，请稍后重试。',
      );
    }
  };

  const handleGuestBrowse = () => {
    // 访客入口：公开页免登录，直接进入态势总览（受保护页仍会按守卫跳回登录）
    history.push('/dashboard');
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'auto',
        background: '#f0f2f5',
      }}
    >
      <Helmet>
        <title>登录 - {Settings.title}</title>
      </Helmet>
      <div style={{ flex: '1', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '32px 0' }}>
        <LoginForm
          contentStyle={{ minWidth: 280, maxWidth: '75vw' }}
          logo={<img alt="logo" src="/logo.svg" />}
          title={Settings.title}
          subTitle="车联网威胁情报统一运营入口"
          initialValues={{ remember: true }}
          onFinish={async (values) => {
            await handleSubmit(values as API.LoginParams);
          }}
        >
          <ProFormText
            name="email"
            fieldProps={{
              size: 'large',
              prefix: <UserOutlined />,
            }}
            placeholder="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '邮箱格式不正确' },
            ]}
          />
          <ProFormText.Password
            name="password"
            fieldProps={{
              size: 'large',
              prefix: <LockOutlined />,
            }}
            placeholder="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          />
          <div style={{ marginBottom: 24, color: 'rgba(0,0,0,0.45)', fontSize: 12 }}>
            <SafetyCertificateOutlined style={{ marginRight: 6 }} />
            访问受审计保护，登录行为将被记录。
          </div>
          <div style={{ textAlign: 'center' }}>
            <Button type="link" htmlType="button" onClick={handleGuestBrowse}>
              以访客身份浏览 →
            </Button>
          </div>
        </LoginForm>
      </div>
      <Footer />
    </div>
  );
};

export default Login;
