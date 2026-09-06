declare namespace API {
  interface LoginParams {
    email: string;
    password: string;
  }

  interface LoginResult {
    access_token: string;
    token_type: string;
  }

  interface CurrentUser {
    id: string;
    email: string;
    display_name: string | null;
    is_active: boolean;
    is_admin: boolean;
    created_at: string;
    updated_at: string;
    last_login_at: string | null;
  }

  interface UserCreateParams {
    email: string;
    password: string;
    display_name?: string | null;
    is_admin?: boolean;
  }

  interface UserStatusUpdateParams {
    is_active: boolean;
  }
}
