/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** API 基础地址 */
  readonly VITE_API_BASE_URL: string
  /** WebSocket 地址 */
  readonly VITE_WS_URL: string
  /** 应用标题 */
  readonly VITE_APP_TITLE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
