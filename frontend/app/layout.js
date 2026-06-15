import "./globals.css";
import { AuthProvider } from "./components/AuthProvider";

export const metadata = {
  title: "SentinelDrive",
  description: "车联网威胁情报工作台"
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
