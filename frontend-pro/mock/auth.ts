import type { Request, Response } from 'express';

/** mock 用户对象结构与后端 /auth/me 响应一致 */
interface MockUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

/**
 * 认证接口本地 mock：与后端 /auth 契约保持一致，
 * 仅用于无后端环境的前端开发验证，账号密码为演示占位值。
 */
const DEMO_EMAIL = 'admin@sentineldrive.local';
const DEMO_PASSWORD = 'SentinelDemo2026';

const DEMO_USER: MockUser = {
  id: '00000000-0000-0000-0000-000000000001',
  email: DEMO_EMAIL,
  display_name: '演示管理员',
  is_active: true,
  is_admin: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  last_login_at: '2026-01-01T00:00:00Z',
};

const UNAUTHORIZED_BODY = {
  detail: {
    error: {
      code: 'invalid_credentials',
      message: '邮箱或密码无效。',
    },
  },
};

const issuedTokens = new Set<string>();

function bearerOf(req: Request): string | null {
  const header = req.headers.authorization || '';
  const match = header.match(/^Bearer (.+)$/);
  return match ? match[1] : null;
}

export default {
  'POST /api/auth/login': async (req: Request, res: Response) => {
    const { email, password } = req.body || {};
    if (email !== DEMO_EMAIL || password !== DEMO_PASSWORD) {
      res.status(401).json(UNAUTHORIZED_BODY);
      return;
    }
    const token = `mock-token-${Date.now()}`;
    issuedTokens.add(token);
    res.json({
      access_token: token,
      token_type: 'bearer',
    });
  },

  'GET /api/auth/me': (req: Request, res: Response) => {
    const token = bearerOf(req);
    if (!token || !issuedTokens.has(token)) {
      res.status(401).json(UNAUTHORIZED_BODY);
      return;
    }
    res.json(DEMO_USER);
  },

  'POST /api/auth/logout': (req: Request, res: Response) => {
    const token = bearerOf(req);
    if (token) {
      issuedTokens.delete(token);
    }
    res.json({ status: 'ok' });
  },
};
